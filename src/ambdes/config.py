"""Model configuration."""

from pathlib import Path

import pandas as pd


class SimConfig:
    """Configuration for a simulation run.

    Stores input data and run settings used by the model.
    """

    def __init__(
        self,
        arrival_config,
        times_config,
        resource_hours_per_week=52000,
        warm_up_period=100,
        data_collection_period=500,
        n_reps=5,
    ):
        """Initialise simulation configuration.

        Parameters
        ----------
        arrival_config : ArrivalConfig
            Arrival input configuration containing the response category
            proportions and non-stationary arrival schedule.
        times_config : TimesConfig
            Time distribution configuration by response category.
        resource_hours_per_week : int
            Ambulance resource hours per week.
        warm_up_period : int
            Duration of the warm-up period in minutes.
        data_collection_period : int
            Duration of the data collection period in minutes.
        n_reps : int
            Number of replications to run.

        """
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
            "time_to_scene": times_config.lognormal_config("travel_to_scene"),
            "on_scene_time": times_config.lognormal_config("on_scene"),
            "time_to_hospital": times_config.lognormal_config("travel_to_hospital"),
            "handover_time": times_config.lognormal_config("handover"),
            "wrap_up_time": times_config.lognormal_config("wrap_up"),
        }

        # Convert total weekly ambulance-hours into an equivalent constant
        # fleet size, assuming a fixed 24/7 resource pool with no shift
        # pattern. One always-available ambulance provides 168 hours of
        # capacity per week (24 × 7), so we approximate the number of
        # ambulances as resource_hours_per_week / 168.
        self.n_ambulances = round(resource_hours_per_week / 168)

        self.warm_up_period = warm_up_period
        self.data_collection_period = data_collection_period
        self.n_reps = n_reps


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
                "range": self.proportion_df.max(axis=0) - self.proportion_df.min(axis=0),
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


class TimesConfig:
    """Prepare time distribution inputs for the simulation.
    
    Attributes
    ----------
    times_df : pd.DataFrame
        Raw time summary dataframe.
    long_df : pd.DataFrame
        Long-form dataframe with columns:
        time, type, category, value.
    """

    def __init__(self, times_csv):
        """Initialise TimesConfig.

        Parameters
        ----------
        times_csv : str | Path
            Path to CSV containing the mean and SD times by category.

        """
        # Import times dataframe
        self.times_df = pd.read_csv(times_csv)

        # Convert to long format
        self.long_df = self.times_df.melt(
            id_vars=["time", "type"],
            value_vars=["C1", "C2", "C3", "C4"],
            var_name="category",
            value_name="value",
        )

        # Convert to tidy format
        self.tidy_df = (
            self.long_df.pivot(
                index=["time", "category"],
                columns="type",
                values="value",
            )
            .reset_index()
            .rename_axis(columns=None)
        )

    def lognormal_config(self, time_name):
        """Create a Lognormal config dict.
        
        Parameters
        ----------
        time_name : str
            Name of time type.

        Returns
        -------
        dict of dict
            Config suitable for sim-tools DistributionRegistry, with one
            config dict per response category.
        """
        subset = self.tidy_df[self.tidy_df["time"] == time_name]

        if subset.empty:
                raise ValueError(
                    f"time_name {time_name!r} not found in times config."
                )

        return {
            row["category"]: {
                "class_name": "Lognormal",
                "params": {
                    "mean": row["mean"],
                    "stdev": row["sd"],
                },
            }
            for _, row in subset.iterrows()
        }

