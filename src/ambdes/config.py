"""Model configuration."""

import json

import pandas as pd


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
    ambulance_schedule_period : int
        Required if ambulance_schedule is provided. Defines the end time
        for the schedule, at which point it should run again, on loop.

    """

    def __init__(
        self,
        arrivals_json,
        times_json,
        warm_up_period,
        data_collection_period,
        n_reps,
        cores=-1,
        n_ambulances=None,
        ambulance_schedule=None,
        ambulance_schedule_period=None,
    ):
        """Initialise simulation configuration.

        Parameters
        ----------
        arrivals_json : str | Path
            Path to JSON file containing arrival distribution configuration.
        times_json : str | Path
            Path to JSON file containing time distribution configuration.
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
        ambulance_schedule_period : int
            Required if ambulance_schedule is provided. Defines the end time
            for the schedule, at which point it should run again, on loop.

        """
        # Load ready-made distribution configs from JSON
        with open(arrivals_json, encoding="utf-8") as f:
            arrivals_config = json.load(f)
        with open(times_json, encoding="utf-8") as f:
            times_config = json.load(f)

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

        self.dist_config = {
            **arrivals_config,
            **times_config,
        }

        # Set the other model parameters as attributes
        self.warm_up_period = warm_up_period
        self.data_collection_period = data_collection_period
        self.n_reps = int(n_reps)
        self.cores = int(cores)
        self.n_ambulances = n_ambulances
        self.ambulance_schedule = ambulance_schedule
        self.ambulance_schedule_period = ambulance_schedule_period

        self.validate_inputs()

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
            if (
                self.ambulance_schedule_period <=
                max(self.ambulance_schedule.keys())
            ):
                raise ValueError(
                    "`ambulance_schedule_period` must be greater than the "
                    "last time in `ambulance_schedule`."
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
