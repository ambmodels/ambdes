"""Code for prepare shift inputs for model."""

import json

import matplotlib.pyplot as plt
import pandas as pd

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------

WEEKDAYS = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}

AREAS = {
    "BNSSG": "bnssg",
    "Devon": "devon",
    "BSW": "bsw",
    "Dorset": "dorset",
    "Cornwall": "cornwall",
    "Cornwall/IOS": "cornwall",
    "Somerset": "somerset",
    "Gloucestershire": "gloucestershire",
}

EVENT_TYPES = {
    "Allocated": "allocated",
    "Available": "available",
    "Rest Break": "rest_break",
    "Restricted Send": "restricted_send",
    "Unavailable": "unavailable",
}

DAY_MINUTES = 24 * 60
WEEK_MINUTES = 7 * DAY_MINUTES

# ----------------------------------------------------------------------------
# Importing and cleaning data
# ----------------------------------------------------------------------------


def load_shifts(path):
    """Load shifts and calculate their start and end minutes within a week.

    Parameters
    ----------
    path : str | pathlib.Path
        Path to the shift CSV file.

    Returns
    -------
    shifts : pd.DataFrame
        Shift data with added columns including `icb`, `shift_start` and
        `shift_end`.

    """
    # Import data
    shifts = pd.read_csv(path)

    # Add standardised ICB names
    shifts["icb"] = shifts["County"].map(AREAS)

    # Convert weekday from string to numeric
    shifts["weekday_num"] = shifts["Weekday"].map(WEEKDAYS)

    # Convert shift start time to minutes within a day (0-1440)
    shifts["day_start_min"] = (
        pd.to_timedelta(shifts["ShiftStart_t"])
        .dt.total_seconds()
        .div(60)
        .astype(int)
    )

    # Convert shift start time to minutes within a week
    # (0 - 1440 - 2880 - 4320 - etc.)
    shifts["shift_start"] = (shifts["weekday_num"] * DAY_MINUTES) + shifts[
        "day_start_min"
    ]

    # Calculate each shift's end time
    shifts["shift_end"] = shifts["shift_start"] + (
        shifts["VehicleHoursWithBreaks"] * 60
    )

    return shifts


def load_resources(path):
    """Load resources and convert hourly resource use to vehicle counts.

    Parameters
    ----------
    path : str | pathlib.Path
        Path to the resources CSV file.

    Returns
    -------
    resources : pd.DataFrame
        Resource data with added columns including `icb`, `time` and
        `vehicles`.

    """
    # Import data
    resources = pd.read_csv(path)

    # Add standardised/simplified ICB and event type names
    resources["icb"] = resources["CountyCommander"].map(AREAS)
    resources["EventTypeGrouped"] = resources["EventTypeGrouped"].map(
        EVENT_TYPES
    )

    # Set datetime columns
    for col in ["start_hour", "end_hour"]:
        resources[col] = pd.to_datetime(
            resources[col], format="%d/%m/%Y %H:%M"
        )

    # Calculate time in minutes in a week (0 - 1440 - 2880 - 4320 - etc.)
    # This combines:
    # - Numeric weekday (Monday = 0, Sunday = 6) * minutes in a day
    # - Hour of day (0-23) * minutes in an hour
    resources["time"] = (resources["start_hour"].dt.weekday * DAY_MINUTES) + (
        resources["start_hour"].dt.hour * 60
    )
    assert resources["time"].between(0, WEEK_MINUTES - 1).all(), (
        "Resource times must be within one week."
    )

    # Replace NA with 0 and convert to minutes
    resources["event_time_min"] = (
        resources["event_time_seconds"].fillna(0) / 60
    )

    # Each row represents an hour of data, with the resources represented as
    # time in minutes. If we divide this by 60, we get a rough approximation
    # of the number of vehicles, assuming all vehicles were on shift for the
    # full 60 min
    resources["vehicles"] = resources["event_time_min"] / 60

    return resources[
        [
            "CountyCommander",
            "icb",
            "EventTypeGrouped",
            "start_hour",
            "end_hour",
            "time",
            "vehicles",
        ]
    ]


# ----------------------------------------------------------------------------
# Creating individual schedules
# ----------------------------------------------------------------------------


def create_weekly_schedule(shifts):
    """Convert shifts into a repeating weekly vehicle count schedule.

    Parameters
    ----------
    shifts : pd.DataFrame
        Shifts dataframe containing `shift_start` and `shift_end` columns,
        measured in minutes from Monday 00:00. End times should be unwrapped,
        so Sunday shifts may end beyond `WEEK_MINUTES`.

    Returns
    -------
    pd.DataFrame
        Schedule with `time` and `vehicle` columns. Includes Monday 00:00 and
        subsequent times when the vehicle count changes.

    """
    events = pd.concat(
        [
            # Create +1 for start events and -1 for end events
            # If intervals falls after end of week, then % will return the
            # division remainder, so essentially just subtract WEEK_MINUTES
            # from the time in those cases.
            pd.DataFrame(
                {
                    "time": shifts["shift_start"] % WEEK_MINUTES,
                    "change": 1,
                }
            ),
            pd.DataFrame(
                {"time": shifts["shift_end"] % WEEK_MINUTES, "change": -1}
            ),
            # Include Monday 00:00 with 0 change just to ensure that the
            # output has a Monday 00:00 row
            pd.DataFrame({"time": [0], "change": [0]}),
        ]
    )

    # Combine events occurring at the same time
    schedule = (
        events.groupby("time", as_index=False)["change"]
        .sum()
        .sort_values("time")
        .reset_index(drop=True)
    )

    # Count intervals already active at Monday 00:00
    carried_into_monday = (
        (shifts["shift_start"] < WEEK_MINUTES)
        & (shifts["shift_end"] >= WEEK_MINUTES)
    ).sum()

    # Create cumlative count of vehicles, initialising count with carried
    # into monday + change at time 0, then continuing with cumulative from
    # then (e.g., if next time -5 then reduce by 5, and so on)
    schedule["vehicles"] = carried_into_monday + schedule["change"].cumsum()

    # Keep Monday 00:00 and times when capacity actually changes
    keep = (schedule["time"] == 0) | (schedule["change"] != 0)
    return schedule.loc[keep, ["time", "vehicles"]].reset_index(drop=True)


def create_availability_schedule(resources):
    """Calculate mean vehicle counts by minute of week and event type.

    Parameters
    ----------
    resources : pd.DataFrame
        Resources data.

    Returns
    -------
    availability : pd.DataFrame
        Schedule with a time column and one column per observed event type.
        Values are summed within each actual hour, then averaged across
        occurrences of that hour of the week. Missing rest_break values are
        filled with zero.

    """
    # Sum all rows for each actual hour and event type.
    # For trust input this combines areas; for area input it stays within area.
    hourly_totals = resources.groupby(
        ["start_hour", "time", "EventTypeGrouped"],
        as_index=False,
    )["vehicles"].sum()

    # Average actual hourly totals across weeks
    availability = (
        hourly_totals.groupby(
            ["time", "EventTypeGrouped"],
            as_index=False,
        )["vehicles"]
        .mean()
        .pivot(
            index="time",
            columns="EventTypeGrouped",
            values="vehicles",
        )
        .reset_index()
    )

    # Some NA where rest break didn't have two times from elsewhere - set to 0
    availability["rest_break"] = availability["rest_break"].fillna(0)

    return availability


def subtract_unavailability(schedule, availability, event):
    """Subtract one event's vehicle counts from a schedule.

    Parameters
    ----------
    schedule : pd.DataFrame
        Vehicle schedule contain `time` and `vehicle` columns.
    availability : pd.DataFrame
        Availability schedule containing time and the specified event column.
    event : str
        Column to subtract, such as "unavailable" or "rest_break".

    Returns
    -------
    pd.DataFrame
        Adjusted schedule with time and vehicle columns. Includes timestamps
        from both inputs, with values carried forward between changes.

    """
    # Outer merge so keep all rows from each, then use ffill which will use
    # last observation to fill NA - so where they have different timestamps,
    # the other is still just the same as it was at it's last timestamp
    combined = (
        schedule.merge(availability[["time", event]], on="time", how="outer")
        .sort_values("time")
        .ffill()
    )

    # Subtract that usage from the vehicles on shift
    combined["vehicles"] -= combined[event]

    return combined[["time", "vehicles"]].reset_index(drop=True)


def create_schedules(shifts, resources):
    """Create the four schedule variants.

    Parameters
    ----------
    shifts : pd.DataFrame
        Prepared shifts data, for the selected area or whole trust.
    resources : pd.DataFrame
        Prepared resources data, for the selected area or whole trust.

    Returns
    -------
    dict[str, pd.DataFrame]
        Schedules with time and vehicles columns.

    """
    availability = create_availability_schedule(resources)

    # Schedule simply based on the shift plan
    simple = create_weekly_schedule(shifts)

    # Schedule accounting for vehicle time unavailable due to problems on the
    # day. In theory, vacant shifts caused by annual leave, training and long
    # term sickness should be filled by planned relief so they don't lose
    # resource. However, short-term problems will reduce resource sent out to
    # below planned - and these include on-the-day sickness, vehicle or
    # equipment faults, contaminated uniform, welfare, etc. The unavailability
    # data used here is the sum of time spent in any of those states.
    unavailable = subtract_unavailability(
        schedule=simple, availability=availability, event="unavailable"
    )

    # Schedule accounting for unavailability and rest breaks
    rest_breaks = subtract_unavailability(
        schedule=unavailable, availability=availability, event="rest_break"
    )

    # Restricted send schedule
    restricted = availability[["time", "restricted_send"]].rename(
        columns={"restricted_send": "vehicles"}
    )

    return {
        "simple": simple,
        "unavailable": unavailable,
        "rest_breaks": rest_breaks,
        "restricted": restricted,
    }


# ----------------------------------------------------------------------------
# Visualise and save schedules
# ----------------------------------------------------------------------------


def plot_schedule(schedule, title):
    """Plot vehicle counts over the week.

    Parameters
    ----------
    schedule : pd.DataFrame
        Dataframe with two columns: time and vehicles.
    title : str
        Plot title.

    """
    fig, ax = plt.subplots(figsize=(14, 5))

    # "where" defines where the steps are placed. "post" means it is to
    # the right of every x position
    ax.step(
        schedule["time"],
        schedule["vehicles"],
        where="post",
    )

    ax.set(
        title=title,
        xlabel="Minute of week",
        ylabel="Number of ambulances",
    )

    plt.show()


def save_schedule(schedule, save_path, round_values=False):
    """Convert schedule to a dictionary and save as json file.

    Parameters
    ----------
    schedule : pd.DataFrame
        Dataframe with two columns: `time` and `vehicles`.
    save_path : str | Path
        Path to save JSON file.
    round_values : bool
        Whether to round columns and convert to integers before saving.

    """
    if round_values:
        schedule = schedule.round().astype(int)

    schedule_dict = schedule.set_index("time")["vehicles"].to_dict()

    with open(save_path, "w") as fp:
        json.dump(schedule_dict, fp, indent=2)


def plot_and_save_schedules(schedules, area, save_folder):
    """Plot and save schedules for an area.

    Parameters
    ----------
    schedules : dict[str, pd.DataFrame]
        Schedule variants returned by create_schedules().
    area : str
        Area name used in plot titles and output filenames.
    save_folder : str | Pathlib.Path
        Folder to save schedules to.

    """
    outputs = [
        (
            "simple",
            "ambschedule",
            "Ambulances on shift",
            False,
        ),
        (
            "unavailable",
            "ambschedule_unavailable",
            "Ambulances on shift (accounts for unavailability)",
            True,
        ),
        (
            "rest_breaks",
            "ambschedule_unavailable_restbreaks",
            (
                "Ambulances on shift (accounts for unavailability and rest "
                + "breaks)"
            ),
            True,
        ),
        (
            "restricted",
            "restricted_send_schedule",
            "Restricted send",
            True,
        ),
    ]

    for name, filename, title, round_values in outputs:
        schedule = schedules[name]

        plot_schedule(schedule, f"{area} - {title}")

        save_schedule(
            schedule,
            save_folder / f"{filename}_{area}.json",
            round_values=round_values,
        )
