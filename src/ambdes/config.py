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
    planned_n_ambulances : int
        Number of planned ambulances in the resource pool.
    model_n_ambulances : int
        Actual number of resources used in the simulation model - for example,
        reduced to reflect:
            - Abstraction due to sickness
            - The capacity used by multiple resources attending an incident
              (as the simulation only models one resource per incident).
    warm_up_period : int
        Duration of the warm-up period in minutes.
    data_collection_period : int
        Duration of the data collection period in minutes.
    n_reps : int
        Number of replications to run.
    cores : int
        Number of CPU cores for parallel execution. Use `-1` for all
        available cores and `1` for sequential execution.
    capacity_interval : int
        How frequently to sample and change number of ambulances on shift,
        in minutes.

    """

    def __init__(
        self,
        arrivals_json,
        times_json,
        warm_up_period,
        data_collection_period,
        n_reps,
        cores=-1,
        resource_hours_per_week=None,
        planned_n_ambulances=None,
        capacity_fixed_reduction=0,
        capacity_interval=None,
        capacity_json=None,
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
        resource_hours_per_week : int
            Total ambulance resource-hours available per week, used to derive
            `planned_n_ambulances`. Provide this or `planned_n_ambulances`,
            but not both.
        planned_n_ambulances : int
            Number of planned ambulances in the resource pool. Provide this or
            `resource_hours_per_week`, but not both.
        capacity_fixed_reduction : int
            Fixed reduction in resource pool capacity - will simply be
            subtracted from planned_n_ambulances. This might represent:
              - Abstraction due to sickness
              - The capacity used by multiple resources attending an incident
                (as the simulation only models one resource per incident).
        capacity_interval : int
            How frequently to sample and change number of ambulances on shift,
            in minutes. Required if varying capacity - and must be supplied
            with `capacity_json`.
        capacity_json : str | Path
            Path to JSON containing the time-varying capacity configuration.
            Required if varying capacity - and must be supplied with
            `capacity_interval`.

        """
        if resource_hours_per_week is None and planned_n_ambulances is None:
            raise ValueError(
                "Provide exactly one of resource_hours_per_week "
                "or planned_n_ambulances."
            )
        if (
            resource_hours_per_week is not None
            and planned_n_ambulances is not None
        ):
            raise ValueError(
                "Provide resource_hours_per_week or planned_n_ambulances, "
                "not both."
            )
        if (capacity_interval is None) != (capacity_json is None):
            raise ValueError(
                "Provide capacity_interval and capacity_json together, "
                "or leave both as None."
            )

        # Load ready-made distribution configs from JSON
        with open(arrivals_json, encoding="utf-8") as f:
            arrivals_config = json.load(f)
        with open(times_json, encoding="utf-8") as f:
            times_config = json.load(f)
        if capacity_json is not None:
            with open(capacity_json, encoding="utf-8") as f:
                capacity_config = json.load(f)

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

        if capacity_json is None:
            self.dist_config = {
                **arrivals_config,
                **times_config,
            }
        else:
            self.dist_config = {
                **arrivals_config,
                **times_config,
                **capacity_config,
            }

        # Convert total weekly ambulance-hours into an equivalent number of
        # resources. One ambulance available for a week contributes 168 hours
        # (24 x 7), so we approximate the number of ambulances as
        # resource_hours_per_week / 168.
        if planned_n_ambulances is None:
            self.planned_n_ambulances = round(resource_hours_per_week / 168)
        else:
            self.planned_n_ambulances = planned_n_ambulances

        # This is the reduced number of resources actually used by the model
        self.model_n_ambulances = (
            self.planned_n_ambulances - capacity_fixed_reduction
        )

        # Set the other model parameters as attributes
        self.warm_up_period = warm_up_period
        self.data_collection_period = data_collection_period
        self.n_reps = int(n_reps)
        self.cores = int(cores)
        self.capacity_interval = capacity_interval
