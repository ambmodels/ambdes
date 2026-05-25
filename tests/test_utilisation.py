"""Test equivalence of time-weighted utilisation calculation.

Compares:
  1. MonitoredResource area-under-curve approach from pydesrap_mms.
  2. Vidigi event log method from current repository.
"""

import numpy as np
import pytest
import simpy
from vidigi.logging import EventLogger
from vidigi.resources import VidigiStore

from ambdes import Results

# ---------------------------------------------------------------------------
# MonitoredResource (copied from pythonhealthdatascience/pydesrap_mms)
#
# Heather, A. Monks, T. (2025). Simple M/M/s queuing model: Python DES RAP.
# GitHub. https://github.com/pythonhealthdatascience/pydesrap_mms.
#
# Acknowledgements
# ----------------
# The MonitoredResource class is based on Tom Monks, Alison Harper and Amy
# Heather (2025) An introduction to Discrete-Event Simulation (DES) using Free
# and Open Source Software
# (https://github.com/pythonhealthdatascience/intro-open-sim/tree/main)
# (MIT Licence). They based it on the method described in Law. Simulation
# Modeling and Analysis 4th Ed. Pages 14 - 17.
# ---------------------------------------------------------------------------


class MonitoredResource(simpy.Resource):
    """Subclass of simpy.Resource used to monitor resource usage during the run.

    Calculates resource utilisation and the queue length during the model run.

    Attributes
    ----------
    time_last_event : list
        Time of last resource request or release.
    area_n_in_queue : list
        Time that patients have spent queueing for the resource
        (i.e. sum of the times each patient spent waiting). Used to
        calculate the average queue length.
    area_resource_busy : list
        Time that resources have been in use during the simulation
        (i.e. sum of the times each individual resource was busy). Used
        to calculated utilisation.

    Notes
    -----
    Class adapted from Monks, Harper and Heather 2025.

    """

    def __init__(self, *args, **kwargs):
        """Initialises MonitoredResource.

        Involves initialising a SimPy resource and resetting monitoring
        attributes.

        Parameters
        ----------
        *args :
            Positional arguments to be passed to the parent class.
        **kwargs :
            Keyword arguments to be passed to the parent class.

        """
        # Initialise a SimPy Resource
        super().__init__(*args, **kwargs)
        # Run the init_results() method
        self.init_results()

    def init_results(self):
        """Resets monitoring attributes to initial values."""
        self.time_last_event = [self._env.now]
        self.area_n_in_queue = [0.0]
        self.area_resource_busy = [0.0]

    def request(self, *args, **kwargs):
        """Requests a resource, but updates time-weighted statistics BEFORE
        making the request.

        Parameters
        ----------
        *args :
            Positional arguments to be passed to the parent class.
        **kwargs :
            Keyword arguments to be passed to the parent class.

        Returns
        -------
        simpy.events.Event
            Event representing the request.

        """
        # Update time-weighted statistics
        self.update_time_weighted_stats()
        # Request a resource
        return super().request(*args, **kwargs)

    def release(self, *args, **kwargs):
        """Releases a resource, but updates time-weighted statistics BEFORE
        releasing it.

        Parameters
        ----------
        *args :
            Positional arguments to be passed to the parent class.
        **kwargs :
            Keyword arguments to be passed to the parent class.

        Returns
        -------
        simpy.events.Event
            Event representing the request.

        """
        # Update time-weighted statistics
        self.update_time_weighted_stats()
        # Release a resource
        return super().release(*args, **kwargs)

    def update_time_weighted_stats(self):
        """Update the time-weighted statistics for resource usage.

        Between every request or release of the resource, it calculates the
        relevant statistics - e.g.:
        - Total queue time (number of requests in queue * time)
        - Total resource use (number of resources in use * time)

        These are summed to return the totals from across the whole simulation.

        Notes
        -----
        - These sums can be referred to as "the area under the curve".
        - They are called "time-weighted" statistics as they account for how
          long certain events or states (such as resource use or queue length)
          persist over time.

        """
        # Calculate time since last event
        time_since_last_event = self._env.now - self.time_last_event[-1]

        # Add record of current time
        self.time_last_event.append(self._env.now)

        # Add "area under curve" of people in queue
        # len(self.queue) is the number of requests queued
        self.area_n_in_queue.append(len(self.queue) * time_since_last_event)

        # Add "area under curve" of resources in use
        # self.count is the number of resources in use
        self.area_resource_busy.append(self.count * time_since_last_event)


# ---------------------------------------------------------------------------
# Stubs for Results interface
# ---------------------------------------------------------------------------


class StubConfig:
    """Minimal config stub satisfying the Results interface."""

    def __init__(self, n_ambulances, warm_up_period, data_collection_period):
        self.n_ambulances = n_ambulances
        self.warm_up_period = warm_up_period
        self.data_collection_period = data_collection_period


class StubModel:
    """Minimal model stub satisfying the Results interface."""

    def __init__(self, config, logger, run_number=0):
        self.config = config
        self.logger = logger
        self.run_number = run_number
        self.patients = []


# ---------------------------------------------------------------------------
# Simulation parameters
# ---------------------------------------------------------------------------

N_AMBULANCES = 3
WARM_UP = 100.0
DATA_PERIOD = 500.0
RUN_LENGTH = WARM_UP + DATA_PERIOD
MEAN_IAT = 10.0
MEAN_SERVICE = 25.0


# ---------------------------------------------------------------------------
# Simulation run functions
# ---------------------------------------------------------------------------


def run_monitored_resource(
    seed,
    mean_iat=MEAN_IAT,
    mean_service=MEAN_SERVICE,
    n_ambulances=N_AMBULANCES,
    warm_up=WARM_UP,
    data_period=DATA_PERIOD,
):
    """Run simulation using MonitoredResource.

    Parameters
    ----------
    seed : int
        Random seed.
    mean_iat : float
        Mean inter-arrival time.
    mean_service : float
        Mean service time.
    n_ambulances : int
        Number of ambulances (resource capacity).
    warm_up : float
        Warm-up period duration.
    data_period : float
        Data collection period duration.

    Returns
    -------
    float
        Time-weighted resource utilisation.

    """
    run_length = warm_up + data_period
    rng = np.random.default_rng(seed)
    env = simpy.Environment()
    monitored = MonitoredResource(env, capacity=n_ambulances)

    def attend(patient_id):
        """Request ambulance and sample time with ambulance."""
        with monitored.request() as req:
            yield req
            yield env.timeout(rng.exponential(mean_service))

    def generate():
        """Generate new patient arrivals."""
        pid = 0
        while True:
            yield env.timeout(rng.exponential(mean_iat))
            pid += 1
            env.process(attend(pid))

    def warm_up_reset():
        """Reset results at end of warm-up period."""
        yield env.timeout(warm_up)
        monitored.init_results()

    env.process(generate())
    env.process(warm_up_reset())
    env.run(until=run_length)

    # Close the final open interval
    monitored.update_time_weighted_stats()

    return sum(monitored.area_resource_busy) / (n_ambulances * data_period)


def run_vidigi_store(
    seed,
    mean_iat=MEAN_IAT,
    mean_service=MEAN_SERVICE,
    n_ambulances=N_AMBULANCES,
    warm_up=WARM_UP,
    data_period=DATA_PERIOD,
):
    """Run simulation using VidigiStore + EventLogger.

    Parameters
    ----------
    seed : int
        Random seed.
    mean_iat : float
        Mean inter-arrival time.
    mean_service : float
        Mean service time.
    n_ambulances : int
        Number of ambulances (resource capacity).
    warm_up : float
        Warm-up period duration.
    data_period : float
        Data collection period duration.

    Returns
    -------
    float
        Time-weighted resource utilisation.

    """
    run_length = warm_up + data_period
    rng = np.random.default_rng(seed)
    env = simpy.Environment()
    config = StubConfig(n_ambulances, warm_up, data_period)
    vidigi_store = VidigiStore(env, num_resources=n_ambulances)
    logger = EventLogger(env=env, run_number=0)

    def attend(patient_id):
        """Request ambulance and sample time with ambulance."""
        with vidigi_store.request() as req:
            vehicle = yield req
            logger.log_resource_use_start(
                entity_id=patient_id,
                event="ambulance_assigned",
                resource_id=vehicle.id_attribute,
            )
            yield env.timeout(rng.exponential(mean_service))
            logger.log_resource_use_end(
                entity_id=patient_id,
                event="ambulance_available",
                resource_id=vehicle.id_attribute,
            )

    def generate():
        """Generate new patient arrivals."""
        pid = 0
        while True:
            yield env.timeout(rng.exponential(mean_iat))
            pid += 1
            env.process(attend(pid))

    # No warm_up_reset needed: Results.utilisation_df() clips the event log
    # to the data collection period internally.
    env.process(generate())
    env.run(until=run_length)

    return Results(StubModel(config=config, logger=logger)).utilisation()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


SCENARIOS = {
    "low_demand": dict(
        mean_iat=500,
        mean_service=5,
        n_ambulances=3,
        warm_up=100,
        data_period=500,
    ),
    "near_saturation": dict(
        mean_iat=5,
        mean_service=25,
        n_ambulances=3,
        warm_up=100,
        data_period=500,
    ),
    "zero_warmup": dict(
        mean_iat=10,
        mean_service=25,
        n_ambulances=3,
        warm_up=0,
        data_period=500,
    ),
    "long_warmup": dict(
        mean_iat=10,
        mean_service=25,
        n_ambulances=3,
        warm_up=1000,
        data_period=100,
    ),
    "short_data": dict(
        mean_iat=10,
        mean_service=5,
        n_ambulances=3,
        warm_up=100,
        data_period=10,
    ),
    "single_ambulance": dict(
        mean_iat=10,
        mean_service=25,
        n_ambulances=1,
        warm_up=100,
        data_period=500,
    ),
}


@pytest.mark.parametrize("scenario", SCENARIOS.values(), ids=SCENARIOS.keys())
@pytest.mark.parametrize("seed", [0, 42])
def test_utilisation_equivalence(scenario, seed):
    """Test equivalence of time-weighted utilisation calculations."""
    u_old = run_monitored_resource(seed, **scenario)
    u_new = run_vidigi_store(seed, **scenario)
    assert u_old == pytest.approx(u_new, abs=1e-9), (
        f"{scenario}, seed={seed}: old={u_old:.10f}, new={u_new:.10f}"
    )
