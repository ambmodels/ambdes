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
    n_ambulances : int
        Size of ambulance resource pool.
    warm_up_period : int
        Duration of the warm-up period in minutes.
    data_collection_period : int
        Duration of the data collection period in minutes.
    n_reps : int
        Number of replications to run.
    cores : int
        Number of CPU cores to use for parallel execution. To use all
        available cores, set to -1. For sequential execution, set to -1.
    """

    def __init__(
        self,
        arrivals_json,
        times_json,
        param_csv,
    ):
        """Initialise simulation configuration.

        Parameters
        ----------
        arrivals_json : str | Path
            Path to JSON file containing arrival distribution configuration.
        times_json : str | Path
            Path to JSON file containing time distribution configuration.
        param_csv : str | Path
            Path to CSV containing model parameters.

        """
        # Load ready-made distribution configs from JSON
        with open(arrivals_json, encoding="utf-8") as f:
            arrivals_config = json.load(f)
        with open(times_json, encoding="utf-8") as f:
            times_config = json.load(f)

        # Convert the call_arrival NSPPThinning parameters into a DataFrame
        # (as sim-tools requires a dataframe, but had to use lists for JSON)
        arrivals_config["call_arrival"]["params"] = {
            "data": pd.DataFrame({
                "t": arrivals_config["call_arrival"]["params"]["t"],
                "mean_iat": arrivals_config["call_arrival"]["params"]["mean_iat"],
            })
        }
        self.dist_config = {
            **arrivals_config,
            **times_config,
        }

        # Import model parameter CSV and convert to dict
        param_df = pd.read_csv(param_csv)
        params = param_df.set_index("parameter")["value"].to_dict()

        # Convert total weekly ambulance-hours into an equivalent constant
        # fleet size, assuming a fixed 24/7 resource pool with no shift
        # pattern. One always-available ambulance provides 168 hours of
        # capacity per week (24 × 7), so we approximate the number of
        # ambulances as resource_hours_per_week / 168.
        self.n_ambulances = round(params["resource_hours_per_week"] / 168)

        # Set the other model parameters as attributes
        self.warm_up_period = params["warm_up_period"]
        self.data_collection_period = params["data_collection_period"]
        self.n_reps = params["n_reps"]
        self.cores = params["cores"]
