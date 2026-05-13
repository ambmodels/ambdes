"""Model configuration."""



class SimConfig:
    """Configuration for a simulation run.

    Stores input data and run settings used by the model.
    """

    def __init__(
        self,
        ambsys_data,
        resource_hours_per_week=52000,
        mean_time_to_scene=10,
        on_scene_time=44,
        mean_time_to_hospital=10,
        wrap_up_time=14,
        run_length=100,
        n_reps=5,
    ):
        """Initialise simulation configuration.

        Parameters
        ----------
        ambsys_data : dict
            Input data containing mean and SD of timings for the simulation.
        resource_hours_per_week : int
            Ambulance resource hours per week.
        mean_time_to_scene : float
            Mean time from ambulance assignment to arrival on scene in minutes.
        on_scene_time : float
            Fixed time in minutes spent on scene before transport.
        mean_time_to_hospital : float
            Mean time from leaving scene to arriving at hospital in minutes.
        wrap_up_time : float
            Fixed time in minutes for post-handover wrap-up before the
            ambulance becomes available again.
        run_length : float
            Duration of the simulation run.
        n_reps : int
            Number of replications to run.

        """
        # Set up parameters for distributions in required format for
        # sim-tools DistributionsRegistry
        self.dist_config = {
            "call": {
                category: {
                    "class_name": "Exponential",
                    "params": {"mean": mean_iat},
                }
                for category, mean_iat in ambsys_data["mean_iat_min"].items()
            },
            "time_to_scene": {
                "class_name": "Exponential",
                "params": {"mean": mean_time_to_scene},
            },
            "handover_time": {
                "class_name": "Lognormal",
                "params": {
                    "mean": ambsys_data["mean_handover_time_min"],
                    "stdev": ambsys_data["sd_handover_time_min"],
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
        self.run_length = run_length
        self.n_reps = n_reps
