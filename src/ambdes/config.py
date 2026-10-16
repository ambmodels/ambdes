"""Model configuration."""

import json
from pathlib import Path

import pandas as pd


def resolve_dict(value):
    """Return a dictionary unchanged, or load one from a JSON file path.

    Parameters
    ----------
    value : dict | str | Path
        Dictionary, or path to a JSON file containing a dictionary.

    Returns
    -------
    dict
        The supplied dictionary or the dictionary loaded from the file.

    """
    if isinstance(value, (str, Path)):
        with open(value, encoding="utf-8") as f:
            return json.load(f)
    return value


def convert_keys_to_int(input_dict):
    """Convert dictionary keys to int.

    Parameters
    ----------
    input_dict : dict
        Dictionary with keys that can be converted to integers.

    Returns
    -------
    dict
        A new dictionary containing the original values and integer keys.

    """
    return {int(key): value for key, value in input_dict.items()}


class SimConfig:
    """Configuration for a simulation run.

    Stores input data and run settings used by the model.

    Attributes
    ----------
    dist_config : dict
        Dictionary with all distribution settings, in required format for
        sim-tools DistributionRegistry.
    warm_up_period : int
        Duration of the warm-up period in minutes.
    data_collection_period : int
        Duration of the data collection period in minutes.
    n_reps : int
        Number of replications to run.
    cores : int
        Number of CPU cores for parallel execution. Use `-1` for all
        available cores and `1` for sequential execution.
    n_ambulances : int
        Number of ambulances in the resource pool.
    ambulance_schedule : dict
        Used to mimic ambulance shifts or varying resource over time. The
        dictionary keys should be time (int, in minutes) and values are
        `n_ambulances` for that time period.
    restricted_send_schedule : dict
        Dictionary containing the count of ambulances over time that are in
        restricted send.
    ambulance_schedule_period : int
        Required if ambulance_schedule is provided. Defines the end time
        for the schedule, at which point it should run again, on loop.

    """

    def __init__(
        self,
        arrivals_config,
        times_config,
        warm_up_period,
        data_collection_period,
        n_reps,
        cores=-1,
        n_ambulances=None,
        ambulance_schedule=None,
        restricted_send_schedule=None,
        ambulance_schedule_period=None,
    ):
        """Initialise simulation configuration.

        Parameters
        ----------
        arrivals_config : dict | str | Path
            Dictionary or path to JSON file containing arrival distribution
            configuration.
        times_config : dict | str | Path
            Dictionary or path to JSON file containing time distribution
            configuration.
        warm_up_period : int
            Duration of the warm-up period in minutes.
        data_collection_period : int
            Duration of the data collection period in minutes.
        n_reps : int
            Number of replications to run.
        cores : int
            Number of CPU cores for parallel execution. Use `-1` for all
            available cores and `1` for sequential execution.
        n_ambulances : int
            Number of ambulances in the resource pool.
        ambulance_schedule : dict | str | Path | None
            Dictionary or path to a JSON file containing ambulance availability
            over time. Keys are times in minutes and values are the number of
            ambulances available from that time. Provide exactly one of
            `n_ambulances` or `ambulance_schedule`.
        restricted_send_schedule : dict | str | Path | None
            Dictionary or path to a JSON file containing the count of
            ambulances over time that are in restricted send. In this model,
            meal breaks cannot overlap restricted send - should be one or the
            other.
        ambulance_schedule_period : int | None
            Required if ambulance_schedule is provided. Defines the end time
            for the schedule, at which point it should run again, on loop.

        """
        # Load dictionaries from JSON paths, unless have directly provided
        # a dictionary - in which case, leave unchanged
        arrivals_config = resolve_dict(arrivals_config)
        times_config = resolve_dict(times_config)
        self.ambulance_schedule = resolve_dict(ambulance_schedule)
        self.restricted_send_schedule = resolve_dict(restricted_send_schedule)

        # Ensure times are int (as might e.g., read in as strings)
        if self.ambulance_schedule is not None:
            self.ambulance_schedule = convert_keys_to_int(
                self.ambulance_schedule
            )
        if self.restricted_send_schedule is not None:
            self.restricted_send_schedule = convert_keys_to_int(
                self.restricted_send_schedule
            )

        # Convert the call_arrival NSPPThinning parameters into a DataFrame
        # (as sim-tools requires a dataframe, but had to use lists for JSON)
        arrivals_config["call_arrival"]["params"] = {
            "data": pd.DataFrame(
                {
                    "t": arrivals_config["call_arrival"]["params"]["t"],
                    "mean_iat": arrivals_config["call_arrival"]["params"][
                        "mean_iat"
                    ],
                }
            )
        }

        # Combine configs into a single dictionary
        self.dist_config = {
            **arrivals_config,
            **times_config,
        }

        # Create permit schedule. This maps between the restricted send
        # schedule and ambulance schedule to create a new schedule which
        # reflects the number of ambulances eligible for C2-C4 (i.e.,
        # ambulances with no restrictions)
        if self.restricted_send_schedule is None:
            self.permit_schedule = None
        else:
            self.permit_schedule = self.create_permit_schedule()

        # Set the other model parameters as attributes
        self.warm_up_period = warm_up_period
        self.data_collection_period = data_collection_period
        self.n_reps = int(n_reps)
        self.cores = int(cores)
        self.n_ambulances = n_ambulances
        self.ambulance_schedule_period = ambulance_schedule_period

        self.validate_inputs()

    def create_permit_schedule(self):
        """Calculate the number of ambulances eligible for C2-C4.

        Returns
        -------
        permit_schedule : dict
            Count of ambulances over time that are eligible for C2-C4.

        """
        # Get the unique times from each schedule
        times = sorted(
            set(self.ambulance_schedule) | set(self.restricted_send_schedule)
        )

        permit_schedule = {}

        n_ambulances = None
        n_restricted = None

        # At each timepoint, check if the number of ambulances on shift or in
        # restricted send changes
        for time in times:
            if time in self.ambulance_schedule:
                n_ambulances = self.ambulance_schedule[time]
            if time in self.restricted_send_schedule:
                n_restricted = self.restricted_send_schedule[time]

            # The number of ambulances permitted for C2-C4 is the current
            # number on shift minus the number in restricted send (C1 only)
            n_permits = n_ambulances - n_restricted
            if n_permits < 0:
                raise ValueError(
                    "Restricted-send capacity exceeds ambulance capacity."
                )

            permit_schedule[time] = n_permits

        return permit_schedule

    def validate_inputs(self):
        """Validate inputs to SimConfig."""
        if (self.n_ambulances is None) == (self.ambulance_schedule is None):
            raise ValueError(
                "Provide exactly one of `n_ambulances` or "
                "`ambulance_schedule`."
            )

        if self.ambulance_schedule is not None:
            if 0 not in self.ambulance_schedule:
                raise ValueError(
                    "`ambulance_schedule` must contain a value at time 0."
                )
            if self.ambulance_schedule_period is None:
                raise ValueError(
                    "Must provide `ambulance_schedule_period` when using "
                    "`ambulance_schedule`."
                )
            if self.ambulance_schedule_period <= max(
                self.ambulance_schedule.keys()
            ):
                raise ValueError(
                    "`ambulance_schedule_period` must be greater than the "
                    "last time in `ambulance_schedule`."
                )

        if self.restricted_send_schedule is not None:
            if self.ambulance_schedule is None:
                raise ValueError(
                    "`restricted_send_schedule` requires `ambulance_schedule`."
                )
            if 0 not in self.restricted_send_schedule:
                raise ValueError(
                    "`restricted_send_schedule` must contain value at time 0."
                )
            if self.ambulance_schedule_period <= max(
                self.restricted_send_schedule.keys()
            ):
                raise ValueError(
                    "`ambulance_schedule_period` must be greater than the "
                    "last time in `restricted_send_schedule`."
                )


def convert_resource_hours_to_ambulances(resource_hours_per_week):
    """Convert resource hours per week to a fixed number of ambulances.

    Convert total weekly ambulance-hours into an equivalent number of
    resources. One ambulance available for a week contributes 168 hours
    (24 x 7), so we approximate the number of ambulances as
    resource_hours_per_week / 168.

    Parameters
    ----------
    resource_hours_per_week : int
        Total ambulance resource-hours available per week.

    Returns
    -------
    float
        Equivalent number of ambulance resources, available 24 x 7.

    """
    return resource_hours_per_week / 168
