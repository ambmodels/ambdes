import logging
import os
from rich.console import Console
from rich.logging import RichHandler
import time


class Logger:
    """
    Provides log of events as the simulation runs.

    Attributes
    ----------
    log_to_console : bool
        Whether to print log messages to the console.
    log_to_file : bool
        Whether to save log to a file.
    file_path : str
        Path to save log to file.
    """
    def __init__(self, config):
        """
        """
        self.config = config

        # If saving to file, check path is valid
        if self.config.log_to_file:
            self._validate_log_path()

        # If logging enabled (either printing to console, file or both), then
        # create logger and configure settings
        if self.config.log_to_console or self.config.log_to_file:
            self.logger = logging.getLogger(__name__)
            self._configure_logging()

    def _validate_log_path(self):
        """
        Validate the log file path.

        Raises
        ------
        ValueError
            If log path is invalid.
        """
        directory = os.path.dirname(self.config.log_file_path)
        if directory and not os.path.exists(directory):
            raise ValueError(
                f"The directory '{directory}' for the log file does not exist."
            )
        if not str(self.config.log_file_path).endswith(".log"):
            raise ValueError(
                f"The log file path '{self.config.log_file_path}' must end with '.log'."
            )

    def _configure_logging(self):
        """
        Configure the logger.
        """
        # Ensure any existing handlers are removed to avoid duplication
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # Add handlers for saving messages to file and/or printing to console
        handlers = []
        if self.config.log_to_file:
            # In write mode, meaning will overwrite existing log of same name
            # (append mode 'a' would add to the end of the log)
            handlers.append(logging.FileHandler(self.config.log_file_path, mode="w"))
        if self.config.log_to_console:
            # Configure RichHandler without INFO/ERROR labels, times or paths
            # to log message. Set up console with jupyter-specific behaviour
            # disabled to prevent large gaps between each log message on ipynb
            console = Console()
            console.is_jupyter = False
            rich_handler = RichHandler(
                console=console, show_time=False,
                show_level=False, show_path=False
            )
            handlers.append(rich_handler)

        # Add handlers directly to the logger
        for handler in handlers:
            self.logger.addHandler(handler)

        # Set logging level and format. If don't set level info, it would
        # only show log messages which are warning, error or critical.
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter("%(message)s")
        for handler in handlers:
            handler.setFormatter(formatter)

    def log(self, msg, sim_time=None):
        """
        Log a message if logging is enabled.

        Parameters
        ----------
        msg : str
            Message to log.
        sim_time : float or None, optional
            Current simulation time. If provided, prints before message.
        """
        if self.config.log_to_console or self.config.log_to_file:
            if sim_time is not None:
                self.logger.info("%0.3f: %s", sim_time, msg)
            else:
                self.logger.info(msg)
