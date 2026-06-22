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
        resource_hours_per_week=52000,
        mean_time_to_scene=10,
        on_scene_time=44,
        mean_time_to_hospital=10,
        mean_handover_time=30,
        sd_handover_time=11.4,
        wrap_up_time=14,
        warm_up_period=100,
        data_collection_period=100,
        n_reps=5,
    ):
        """Initialise simulation configuration.

        Parameters
        ----------
        arrival_config : ArrivalConfig
            Arrival input configuration containing the response category
            proportions and non-stationary arrival schedule.
        resource_hours_per_week : int
            Ambulance resource hours per week.
        mean_time_to_scene : float
            Mean time from ambulance assignment to arrival on scene in minutes.
        on_scene_time : float
            Fixed time in minutes spent on scene before transport.
        mean_time_to_hospital : float
            Mean time from leaving scene to arriving at hospital in minutes.
        mean_handover_time : float
            Mean time from arrival at hospital to handover in minutes.
        sd_handover_time : float
            Standard deviation of time from arrival at hospital to handover
            in minutes.
        wrap_up_time : float
            Fixed time in minutes for post-handover wrap-up before the
            ambulance becomes available again.
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
            "time_to_scene": {
                "class_name": "Exponential",
                "params": {"mean": mean_time_to_scene},
            },
            "handover_time": {
                "class_name": "Lognormal",
                "params": {
                    "mean": mean_handover_time,
                    "stdev": sd_handover_time,
                },
            },
            "time_to_hospital": {
                "class_name": "Exponential",
                "params": {"mean": mean_time_to_hospital},
            },
        }

        # Convert total weekly ambulance-hours into an equivalent constant
        # fleet size, assuming a fixed 24/7 resource pool with no shift
        # pattern. One always-available ambulance provides 168 hours of
        # capacity per week (24 × 7), so we approximate the number of
        # ambulances as resource_hours_per_week / 168.
        self.n_ambulances = round(resource_hours_per_week / 168)

        self.on_scene_time = on_scene_time
        self.wrap_up_time = wrap_up_time
        self.warm_up_period = warm_up_period
        self.data_collection_period = data_collection_period
        self.n_reps = n_reps


class ArrivalConfig:
    """Prepare arrival inputs for the simulation.

    Attributes
    ----------
    arrival_df : pd.DataFrame
        Mean arrival counts by day of week and response category.
    variation_df : pd.DataFrame
        Summary of variation in category proportions across days of the week.
    category_proportions : pd.Series
        Mean proportion of arrivals in each response category across the week.
    nspp_df : pd.DataFrame
        Arrival schedule in the format required by `sim_tools` `NSPPThinning`.

    """

    def __init__(self, arrival_df):
        """Initialise ArrivalConfig.

        Parameters
        ----------
        arrival_df : str | Path | pd.DataFrame
            Arrival counts by day of week and response category.

        """
        # Import arrivals dataframe
        if isinstance(arrival_df, (str, Path)):
            self.arrival_df = pd.read_csv(arrival_df, index_col=0)
        else:
            self.arrival_df = arrival_df

        # Convert to proportion by response category for each day
        proportion_df = self.arrival_df.div(
            self.arrival_df.sum(axis=1), axis=0
        )

        # Summarise the variations in proportions by day of week
        self.variation_df = pd.DataFrame(
            {
                "mean": proportion_df.mean(axis=0),
                "min": proportion_df.min(axis=0),
                "max": proportion_df.max(axis=0),
                "range": proportion_df.max(axis=0) - proportion_df.min(axis=0),
                "sd": proportion_df.std(axis=0),
            }
        )

        # Get overall mean proportion by response category
        self.category_proportions = proportion_df.mean(axis=0)

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
