from itertools import cycle
import simpy
from vidigi.logging import EventLogger
from vidigi.resources import VidigiStore
import pandas as pd
import matplotlib.pyplot as plt

class Model:
    def __init__(self):
        """Initialise Model."""
        self.env = simpy.Environment()
        self.n_ambulances = 20
        self.logger = EventLogger(env=self.env)
        self.ambulance = VidigiStore(
            env=self.env,
            num_resources=self.n_ambulances,
            label="ambulance",
            logger=self.logger
        )
        self.patient_count = 0
        self.abstracted_units = []
        self.capacity_log = [
            {
                "time": 0.0,
                "action": "initial",
                "resource_id": None,
                "target_removed": 0,
                "abstracted": 0,
                "capacity": self.n_ambulances,
            }
        ]

    def log_capacity_change(self, action, unit, target_removed):
        """Record a change in operational ambulance capacity."""
        self.capacity_log.append(
            {
                "time": self.env.now,
                "action": action,
                "resource_id": unit.unique_id_attribute,
                "target_removed": target_removed,
                "abstracted": len(self.abstracted_units),
                "capacity": self.ambulance.num_resources,
            }
        )

    def generate_patients(self):
        """Generate patients."""
        while True:
            # Pass time between arrivals
            yield self.env.timeout(1.11111)

            # Print time and ID of new arrival
            self.patient_count += 1
            print(f"{self.env.now}: Patient {self.patient_count} arrived")

            # Log call time
            self.logger.log_arrival(entity_id=self.patient_count)

            # Request an ambulance
            self.env.process(self.request_ambulance(self.patient_count))

    def request_ambulance(self, patient_id):
        """Request ambulance."""
        self.logger.log_queue(entity_id=patient_id, event="ambulance_wait_begins")
        with self.ambulance.request(
            entity_id=patient_id,
            start_event="ambulance_assigned",
            end_event="ambulance_available"
        ) as req:
            # Once an ambulance is available, assign to the patient
            vehicle = yield req
            print(
                f"{self.env.now}: Patient {patient_id} allocated ambulance." +
                f" Now there are {len(self.ambulance.items)} available " +
                "ambulances"
            )

            # Patient spends 3 minutes with ambulance then it is released
            yield self.env.timeout(3)
            print(f"{self.env.now}: Patient {patient_id} finished")

        self.logger.log_departure(entity_id=patient_id)

    def abstraction(self):
        """Set a new abstraction target every 10 minutes."""
        # Targets (amounts to remove from maximum overall capacity)
        targets = cycle([17, 20, 10, 5])
        # How often to change targets
        interval = 10

        while True:
            # Get target
            target_removed = next(targets)
            interval_start = self.env.now
            deadline = interval_start + interval

            print(
                f"\n{self.env.now:.2f}: "
                f"New abstraction target={target_removed}; "
                f"currently abstracted={len(self.abstracted_units)}; "
                f"current capacity={self.ambulance.capacity}; "
                f"new target capacity={self.n_ambulances - target_removed}"
            )

            yield from self.apply_abstraction(
                target_removed=target_removed,
                deadline=deadline
            )

            achieved = len(self.abstracted_units)
            shortfall = max(0, target_removed - achieved)

            print(
                f"{self.env.now:.2f}: "
                f"Finished abstraction; "
                f"target={target_removed}, "
                f"achieved={achieved}, "
                f"shortfall={shortfall}, "
                f"capacity={self.ambulance.capacity}, "
                f"busy={self.ambulance.count}, "
                f"available={len(self.ambulance.items)}"
            )

            # If the target was reached early, wait for the remainder
            # of the interval
            remaining_time = deadline - self.env.now

            if remaining_time > 0:
                yield self.env.timeout(remaining_time)

    def apply_abstraction(self, target_removed, deadline):
        """Try to reach the target until the specified deadline."""
        if not 0 <= target_removed <= self.n_ambulances:
            raise ValueError(
                f"target_removed must be between 0 and "
                f"{self.n_ambulances}; received {target_removed}"
            )

        # Return ambulances if the new target is lower than the
        # number currently abstracted.
        while len(self.abstracted_units) > target_removed:
            # Remove final unit from list
            unit = self.abstracted_units.pop()
            # Increment the expected number of objects in the store
            # We alter _n_pool_units as num_resources is not changeable
            self.ambulance._n_pool_units += 1
            # Add the unit to the store
            self.ambulance.put(unit, auto_log=False)
            self.log_capacity_change(
                action="returned",
                unit=unit,
                target_removed=target_removed
            )
            print(
                f"{self.env.now:.2f}: "
                f"Returned {unit.unique_id_attribute}; "
                f"abstracted={len(self.abstracted_units)}, "
                f"capacity={self.ambulance.capacity}, "
                f"available={len(self.ambulance.items)}"
            )

        # Create a deadline event that can be shared by all removal attempts
        # made during this target period
        remaining_time = max(0, deadline - self.env.now)
        deadline_event = self.env.timeout(remaining_time)

        # Attempt to remove additional units
        while len(self.abstracted_units) < target_removed:

            # Do not start another request once the deadline has passed
            if self.env.now >= deadline:
                break

            # Wait for either:
            # 1. An ambulance to become available to remove from store, or-
            # 2. The target interval to end.
            get_event = self.ambulance.get_direct(auto_log=False)
            result = yield get_event | deadline_event

            if get_event in result:
                unit = result[get_event]
                # Add the object to the list of abstracted units
                self.abstracted_units.append(unit)
                # Reduce the expected number of objects in the store
                # We alter _n_pool_units as num_resources is not changeable
                self.ambulance._n_pool_units -= 1
                self.log_capacity_change(
                    action="removed",
                    unit=unit,
                    target_removed=target_removed,
                )
                print(
                    f"{self.env.now}: Ambulance capacity is now " +
                    f"{self.ambulance.capacity}. There are " +
                    f"{len(self.ambulance.items)} available. num_resources is " +
                    f"{self.ambulance.num_resources}"
                )
            else:
                # The deadline occurred first. Cancel the outstanding request
                # so it can't remove an ambulance later
                self.ambulance.cancel_get(get_event)
                print(
                    f"{self.env.now:.2f}: "
                    f"Stopped trying to rfrom vidigi.logging import EventLoggereach target "
                    f"{target_removed}; "
                    f"actually abstracted="
                    f"{len(self.abstracted_units)}"
                )
                break
        
        self.assert_resource_invariants()

    def assert_resource_invariants(self):
        """Check that ambulance resource accounting is consistent."""
        original = self.n_ambulances
        operational = self.ambulance.num_resources
        abstracted = len(self.abstracted_units)
        busy = self.ambulance.count
        available = len(self.ambulance.items)

        assert original == operational + abstracted, {
            "original": original,
            "operational": operational,
            "abstracted": abstracted,
        }

        assert operational == busy + available, {
            "operational": operational,
            "busy": busy,
            "available": available,
        }

        assert 0 <= busy <= operational
        assert 0 <= available <= operational
        assert 0 <= abstracted <= original

    def run(self):
        self.env.process(self.generate_patients())
        self.env.process(self.abstraction())
        self.env.run(50)


model = Model()
model.run()


log = model.logger.to_dataframe()
capacity = model.n_ambulances

# Filter to events marking start and end of ambulance resource use
amb = log.loc[
    log["event"].isin(
        ["ambulance_assigned", "ambulance_available"]
    ),
    ["entity_id", "event_type", "time"],
]

# Create two dataframes - one with start times and one with end times
starts = amb.loc[
    amb["event_type"] == "resource_use", ["entity_id", "time"]
].rename(columns={"time": "start_time"})
ends = amb.loc[
    amb["event_type"] == "resource_use_end", ["entity_id", "time"]
].rename(columns={"time": "end_time"})

# Defensive check: each ID should only correspond to one start
dup_starts = starts.loc[starts["entity_id"].duplicated(), "entity_id"]
dup_ends = ends.loc[ends["entity_id"].duplicated(), "entity_id"]
dup_id = set(dup_starts) | set(dup_ends)
if dup_id:
    raise ValueError(
        "Duplicate entity_id values found in ambulance event log ",
        f"(n={len(dup_id)}). Each entity_id must only appear once ",
        "for one arrival and one departure.",
    )

# Combine these, so each patient has one row with start and end time
intervals = starts.merge(ends, on="entity_id", how="left")

# If end_time is NA, use end of observation window as end time
intervals["end_time"] = intervals["end_time"].fillna(50)
display(intervals)


# Convert intervals into event times: +1 when ambulance becomes busy
# and -1 when ambulance stops being busy
events = pd.concat(
    [
        intervals[["start_time"]]
        .rename(columns={"start_time": "time"})
        .assign(delta=1),
        intervals[["end_time"]]
        .rename(columns={"end_time": "time"})
        .assign(delta=-1),
    ],
    ignore_index=True,
).sort_values("time")
display(events)

# Combine simultaneous changes into +-2/3/4/5...
# TODO: Should I drop rows with 0? It's e.g. +1 and -1 so cancel each other out?
events_summary = events.groupby("time", as_index=False)["delta"].sum()
display(events_summary)

capacity_log = pd.DataFrame(model.capacity_log)

# Keep the last achieved capacity at each timestamp (there can be several
# individual ambulance changes at same time as add or remove each one - just
# need a summary of what capacity became at that timepoint)
capacity_changes = capacity_log[["time", "capacity"]].sort_values("time").drop_duplicates(subset="time", keep="last")

# TODO: Filter to between warm-up and data collection
display(capacity_changes)

# Create a timeline of every point when the number busy changes or the
# operational capacity changes
times = sorted({
    *events_summary["time"].to_list(),
    *capacity_changes["time"].to_list()
})

state_changes = pd.DataFrame({"time": times})

# Add the record of when ambulances were busy/releated by patients
state_changes = state_changes.merge(
    events_summary,
    on="time",
    how="left",
)

# For any timepoints with no change in ambulance use, set to 0
state_changes["delta"] = (
    state_changes["delta"]
    .fillna(0)
    .astype(int)
)

# Add a column with the total number of ambulances busy at each timepoint
state_changes["busy"] = state_changes["delta"].cumsum()
state_changes = state_changes.drop(columns="delta")

# Add the capacity at each timepoint
state_changes = pd.merge_asof(
    state_changes.sort_values("time"),
    capacity_changes.sort_values("time"),
    on="time",
    direction="backward",
)

# Find the time between each row, dropping any with a time of 0
state_changes["interval_duration"] = (
    state_changes["time"].shift(-1)
    - state_changes["time"]
)
state_changes = state_changes.loc[
    state_changes["interval_duration"] > 0
].copy()

# Check that the state is valid
invalid = state_changes.loc[
    state_changes["busy"] > state_changes["capacity"]
]
if not invalid.empty:
    raise ValueError(
        "Reconstructed busy ambulances exceed operational capacity:\n"
        f"{invalid}"
    )

# Filter to where there is non-zero capacity
# (as only relevant to include utilisation if there is any vehicles that
# can possibly be utilised)
state_changes = state_changes.loc[
    state_changes["capacity"] > 0
].copy()

# Calculate utilisation at that timepoint (number of busy units over the
# total capacity at that timepoint)
state_changes["utilisation"] = state_changes["busy"] / state_changes["capacity"]
display(state_changes)

util_df = state_changes.copy()

# Calculate time-weighted mean utilisation
busy_minutes = (util_df["busy"]* util_df["interval_duration"]).sum()
operational_minutes = (util_df["capacity"] * util_df["interval_duration"]).sum()
print(f"Utilisation: {busy_minutes / operational_minutes}")

figs, axes = plt.subplots(nrows=2, ncols=1, figsize=(8, 10))

axes[0].step(
    util_df["time"],
    util_df["busy"],
    color="tab:orange",
    label="Busy ambulances",
)
axes[0].step(
    util_df["time"],
    util_df["capacity"],
    color="tab:blue",
    label="Capacity",
    linestyle="--",
    alpha=0.7
)
axes[0].set_xlabel("Time")
axes[0].set_ylabel("Number of ambulances")
axes[0].legend()
axes[0].set_xlim(xmin=0)
axes[0].set_ylim(ymin=0)

axes[1].step(
    util_df["time"],
    util_df["utilisation"]
)
axes[1].set_xlabel("Time")
axes[1].set_ylabel("Utilisation")
axes[1].set_xlim(xmin=0)
axes[1].set_ylim(ymin=0)

plt.tight_layout()
plt.show()