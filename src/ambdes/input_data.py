"""Input modelling: functions for importing and processing raw data."""

import numpy as np
import pandas as pd

from ambdes.constants import AREA_NAME_MAP, DAY_MINUTES, WEEK_MINUTES

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------

YEAR = 2025

# "IFT Level 3" and "Other" are marked as C3 as, when we do that, it matches
# up with the original count of Category 3 patients we used to have, when a
# different column with just four groups was provided
CATEGORIES = {
    "Category 1": "C1",
    "Category 2": "C2",
    "Category 3": "C3",
    "IFT Level 3": "C3",
    "Other": "C3",
    "Category 4": "C4",
    "Category 4 999": "C4",
}

EVENT_TYPES = {
    "Allocated": "allocated",
    "Available": "available",
    "Rest Break": "rest_break",
    "Restricted Send": "restricted_send",
    "Unavailable": "unavailable",
}

WEEKDAYS = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}

TIME_COLUMNS = [
    "AddedToStack_Duration",
    "C0001_Mobilisation_Duration",
    "C0004_MobilisationToScene_Duration",
    "C0007_OnScene_Duration",
    "C0172_SceneToDestination_Duration",
    "C0012_Handover_Duration",
    "C0171_WrapUp_Duration",
]

# ----------------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------------


def map_labels(
    original_series,
    mapping_dict,
    name,
    allow_missing=False,
    allow_unmapped=(),
):
    """Map labels, rejecting missing and unexpected values by default.

    Parameters
    ----------
    original_series : pd.Series
        Raw column.
    mapping_dict : dict
        Mapping from raw labels to the standardised simplified values.
    name : str
        Label used in success, warning and error messages.
    allow_missing : bool
        Whether missing values are permitted in `original_series`.
    allow_unmapped : tuple
        Additional labels permitted in `original_series` without a mapped
        value in `mapping_dict`.

    Returns
    -------
    pd.Series
        Mapped values.

    """
    mapped = original_series.map(mapping_dict)

    # Identify exceptions from `allow_unmapped`
    # Also allow missing values if set to True
    permitted = original_series.isin(allow_unmapped)
    if allow_missing:
        permitted = permitted | original_series.isna()

    # Reject any other missing or unmapped values
    invalid = mapped.isna() & ~permitted

    if invalid.any():
        raise ValueError(
            f"Missing or unexpected {name} labels:\n"
            f"{original_series[invalid].value_counts(dropna=False)}"
        )

    print("--------------------------------------------------------------")
    print(f"Mapping {name}")
    print(f"Successfully mapped {mapped.notna().sum()} rows")

    if permitted.any():
        print(
            f"Warning: {permitted.sum()} rows have permitted missing "
            f"or unknown {name} labels in the raw data. These were:\n"
            f"{original_series[permitted].value_counts(dropna=False).to_string()}"
        )

    print("--------------------------------------------------------------")

    return mapped


def map_icb(original_series):
    """Map ICB names.

    Parameters
    ----------
    original_series : pd.Series
        Raw column.

    Returns
    -------
    pd.Series
        Mapped values.

    """
    return map_labels(
        original_series=original_series,
        mapping_dict=AREA_NAME_MAP,
        name="ICB",
        allow_missing=True,
        allow_unmapped=("Unknown ICB",),
    )


def map_categories(original_series):
    """Map response categories.

    Parameters
    ----------
    original_series : pd.Series
        Raw column.

    Returns
    -------
    pd.Series
        Mapped values.

    """
    return map_labels(
        original_series=original_series,
        mapping_dict=CATEGORIES,
        name="category",
    )


# ----------------------------------------------------------------------------
# Functions for importing and cleaning data
# ----------------------------------------------------------------------------


def prepare_time_data(path, year=YEAR):
    """Import and clean time data.

    Parameters
    ----------
    path : str | Path
        Path to time data CSV file.
    year : int
        Year the provided data is from.

    Returns
    -------
    time_data : pd.DataFrame
        Processed time data.

    """
    # Import raw time data
    time_data = pd.read_csv(path)

    # Group "See & Convey non ED" and "See & Convey ED" into a single column
    time_data["outcome"] = np.where(
        time_data["C0660_CallOutcomeDetail"] == "See & Treat",
        "see_and_treat",
        np.where(
            time_data["C0660_CallOutcomeDetail"].isin(
                ["See & Convey ED", "See & Convey non ED"]
            ),
            "see_and_convey",
            time_data["C0660_CallOutcomeDetail"],
        ),
    )

    # Add weekday column (0=Monday, 6=Sunday)
    time_data["weekday"] = pd.to_datetime(
        dict(
            year=year,
            month=time_data["IncidentMonth"],
            day=time_data["IncidentDay"],
        )
    ).dt.weekday

    # Add simplified ICB names
    time_data["icb"] = map_icb(time_data["C0722_ICBforCommisisonersReports"])

    # Add simplified category names
    time_data["category"] = map_categories(
        time_data["ResponseCategoryGroupLevel2"]
    )

    # Convert times from seconds to minutes
    time_data[TIME_COLUMNS] = time_data[TIME_COLUMNS] / 60

    print("--------------------------------------------------------------")
    print("Time columns converted from seconds to minutes.")

    # Report numeric columns that were not converted
    unconverted = [
        col
        for col in time_data.select_dtypes(include="number").columns
        if col not in TIME_COLUMNS
    ]
    if unconverted:
        print(
            "Numeric columns not converted: "
            f"{', '.join(unconverted)}\n"
            "If any of these contain times in seconds, you must add them to "
            "TIME_COLUMNS in prepare_time_data."
        )

    print("--------------------------------------------------------------")

    return time_data


def prepare_resources_per_incident(path):
    """Import and clean data on resources per incident.

    Parameters
    ----------
    path : str | Path
        Path to the CSV file containing counts of resources per incident.

    Returns
    -------
    resources : pd.DataFrame
        Processed data on resources per incident.

    """
    # Import raw data on resources per incident
    resources = pd.read_csv(path)

    # Add simplified ICB names
    resources["icb"] = map_icb(resources["C0722_ICBforCommisisonersReports"])

    # Add simplified category names
    resources["category"] = map_categories(
        resources["ResponseCategoryGroupLevel2"]
    )

    # Exact number of days represented by data
    # (This assumes a single year of data)
    days = len(resources[["IncidentMonth", "IncidentDay"]].drop_duplicates())
    if days != 365:
        raise ValueError(
            f"Expected 365 distinct incident dates in resources data, "
            f"but found {days}."
        )

    return resources


def prepare_shifts(path):
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
    shifts["icb"] = map_icb(shifts["County"])

    # Convert weekday from string to numeric
    shifts["weekday_num"] = map_labels(
        original_series=shifts["Weekday"],
        mapping_dict=WEEKDAYS,
        name="weekday",
    )

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


def prepare_resources(path):
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
    resources["icb"] = map_icb(resources["CountyCommander"])
    resources["EventTypeGrouped"] = map_labels(
        original_series=resources["EventTypeGrouped"],
        mapping_dict=EVENT_TYPES,
        name="event type",
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
