"""Model configuration."""

import time


class SimConfig:
    """Configuration for a simulation run.

    Stores input data, run settings, and logging options used by the model.
    """

    def __init__(
        self,
        ambsys_data,
        run_length=100,
        log_to_console=False,
        log_to_file=False,
        log_file_path=None
    ):
        """Initialise simulation configuration.

        Parameters
        ----------
        ambsys_data : dict
            Input data containing mean timings for the simulation, including
            `mean_iat_min`, `mean_response_time_min`, and
            `mean_handover_time_min`.
        run_length : float, default=100
            Duration of the simulation run.
        log_to_console : bool, default=False
            Whether to write log messages to the console.
        log_to_file : bool, default=False
            Whether to write log messages to a file.
        log_file_path : str, default=None
            Path to the log file.

        """
        if log_file_path is None:
            log_file_path = f"{time.strftime('%Y-%m-%d_%H-%M-%S')}.log"

        self.mean_iat_min = ambsys_data["mean_iat_min"]
        self.mean_response_time_min = ambsys_data["mean_response_time_min"]
        self.mean_handover_time_min = ambsys_data["mean_handover_time_min"]
        self.run_length = run_length
        self.log_to_console = log_to_console
        self.log_to_file = log_to_file
        self.log_file_path = log_file_path

