"""Stubs for Results interface."""


class StubConfig:
    """Minimal config stub satisfying the Results interface."""

    def __init__(self, n_ambulances, warm_up_period, data_collection_period):
        """Initialise StubConfig.

        Parameters
        ----------
        n_ambulances : int
            Number of ambulances.
        warm_up_period : float
            Warm-up period duration.
        data_collection_period : float
            Data collection period duration.

        """
        self.n_ambulances = n_ambulances
        self.warm_up_period = warm_up_period
        self.data_collection_period = data_collection_period


class StubModel:
    """Minimal model stub satisfying the Results interface."""

    def __init__(self, config, logger, run_number=0):
        """Initialise StubModel.

        Parameters
        ----------
        config : StubConfig
            Configuration object.
        logger : EventLogger
            Vidigi event logger populated during a simulation run.
        run_number : int, optional
            Run identifier. Defaults to 0.

        """
        self.config = config
        self.logger = logger
        self.run_number = run_number
        self.patients = []
