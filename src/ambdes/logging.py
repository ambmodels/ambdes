import logging
from rich.console import Console
from rich.logging import RichHandler


class Logger:
    """
    Provides log of events as the simulation runs.

    Attributes
    ----------
    verbose : bool
        Whether to print messages as simulation runs.
    """
    def __init__(self, verbose):
        """
        Initialise logging class.

        Parameters
        ----------
        verbose : bool
            Whether to print messages as simulation runs.
        """
        self.verbose = verbose
        if self.verbose:
            self.logger = logging.getLogger(__name__)
            self._configure_logging()

    def _configure_logging(self):
        """
        Configure the logger.
        """
        # Ensure any existing handlers are removed to avoid duplication
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # Configure RichHandler without INFO/ERROR labels, times or paths
        # to log message. Set up console with jupyter-specific behaviour
        # disabled to prevent large gaps between each log message on ipynb.
        console = Console()
        console.is_jupyter = False
        rich_handler = RichHandler(
            console=console, show_time=False,
            show_level=False, show_path=False
        )

        # Add handler to the logger
        self.logger.addHandler(rich_handler)

        # Set logging level and format. If don't set level info, it would
        # only show log messages which are warning, error or critical.
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter("%(message)s")
        rich_handler.setFormatter(formatter)

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
        if self.verbose:
            if sim_time is not None:
                self.logger.info("%0.3f: %s", sim_time, msg)
            else:
                self.logger.info(msg)
