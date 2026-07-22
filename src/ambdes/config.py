"""Model configuration."""

import json

import pandas as pd


class SimConfig:
    """Configuration for a simulation run.

    Stores input data and run settings used by the model.
    """

    def __init__(
        self,
        arrival_config,
        times_json,
        model_config,
    ):
        """Initialise simulation configuration.

        Parameters
        ----------
        arrival_config : ArrivalConfig
            Arrival input configuration.
        times_json : str | Path
            Path to JSON file containing time distribution configuration.
        model_config : ModelConfig
            Model-level input parameters.

        """
        # Load ready-made time distribution config from JSON
        with open(times_json, encoding="utf-8") as f:
            times_config = json.load(f)

        # Set up parameters for distributions in required format for
        # sim-tools DistributionsRegistry
        self.dist_config = {
            "call_arrival": {
                "class_name": "NSPPThinning",
                "params": {"data": arrival_config.nspp_df},
            },
            "call_category": {
                "class_name": "DiscreteEmpirical",
                "params": {
                    "values": arrival_config.category_proportions.index,
                    "freq": arrival_config.category_proportions.values,
                },
            },
            **times_config,
        }

        # Convert total weekly ambulance-hours into an equivalent constant
        # fleet size, assuming a fixed 24/7 resource pool with no shift
        # pattern. One always-available ambulance provides 168 hours of
        # capacity per week (24 × 7), so we approximate the number of
        # ambulances as resource_hours_per_week / 168.
        self.n_ambulances = round(model_config.resource_hours_per_week / 168)

        self.warm_up_period = model_config.warm_up_period
        self.data_collection_period = model_config.data_collection_period
        self.n_reps = model_config.n_reps


class ArrivalConfig:
    """Prepare arrival inputs for the simulation.

    Attributes
    ----------
    arrival_df : pd.DataFrame
        Mean arrival counts by day of week and response category.
    proportion_df : pd.DataFrame
        Proportion of arrivals in each response category by day of week.
    variation_df : pd.DataFrame
        Summary of variation in category proportions across days of the week.
    category_proportions : pd.Series
        Mean proportion of arrivals in each response category across the week.
    nspp_df : pd.DataFrame
        Arrival schedule in the format required by `sim_tools` `NSPPThinning`.

    """

    def __init__(self, arrival_csv):
        """Initialise ArrivalConfig.

        Parameters
        ----------
        arrival_csv : str | Path
            Path to CSV containing arrival counts by day of week and response
            category.

        """
        # Import arrivals dataframe
        self.arrival_df = pd.read_csv(arrival_csv, index_col=0)

        # Convert to proportion by response category for each day
        self.proportion_df = self.arrival_df.div(
            self.arrival_df.sum(axis=1), axis=0
        )

        # Summarise the variations in proportions by day of week
        self.variation_df = pd.DataFrame(
            {
                "mean": self.proportion_df.mean(axis=0),
                "min": self.proportion_df.min(axis=0),
                "max": self.proportion_df.max(axis=0),
                "range": (
                    self.proportion_df.max(axis=0)
                    - self.proportion_df.min(axis=0)
                ),
                "sd": self.proportion_df.std(axis=0),
            }
        )

        # Get overall mean proportion by response category
        self.category_proportions = self.proportion_df.mean(axis=0)

        # Get count of total arrivals per day
        arrivals_per_day = self.arrival_df.sum(axis=1)

        # Convert to format required by sim_tools NSPPThinning class
        # It requires a dataframe with columns "t" (timepoint when arrival
        # rate changes) and "mean_iat" (mean inter-arrival time)
        self.nspp_df = pd.DataFrame(
            {
                "t": range(0, 7 * 1440, 1440),
                "mean_iat": 1440 / arrivals_per_day.values,
            }
        )


class ModelConfig:
    """Prepare model-level inputs for the simulation.

    Attributes
    ----------
    resource_hours_per_week : int
        Ambulance resource hours per week.
    warm_up_period : int
        Duration of the warm-up period in minutes.
    data_collection_period : int
        Duration of the data collection period in minutes.
    n_reps : int
        Number of replications to run.

    """

    def __init__(self, param_csv):
        """Initialise ModelConfig.

        Parameters
        ----------
        param_csv : str | Path
            Path to CSV containing model parameters.

        """
        # Import CSV and convert to dict
        param_df = pd.read_csv(param_csv)
        params = param_df.set_index("parameter")["value"].to_dict()

        # Set as attributes
        self.resource_hours_per_week = params["resource_hours_per_week"]
        self.warm_up_period = params["warm_up_period"]
        self.data_collection_period = params["data_collection_period"]
        self.n_reps = params["n_reps"]
