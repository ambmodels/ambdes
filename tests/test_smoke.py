"""Smoke tests - checks the model runs end-to-end without errors."""

from pathlib import Path

from ambdes import Model, Runner, SimConfig

INPUT = Path(__file__).parent.joinpath("input_data")

ARRIVALS = INPUT / "param_arrivals.json"
TIMES = INPUT / "param_times.json"

WARM_UP_PERIOD = 10
DATA_COLLECTION_PERIOD = 400
N_REPS = 5
CORES = 1
N_AMBULANCES = 1


def make_config():
    """Create a standard simulation config for regression tests."""
    return SimConfig(
        arrivals_json=ARRIVALS,
        times_json=TIMES,
        warm_up_period=WARM_UP_PERIOD,
        data_collection_period=DATA_COLLECTION_PERIOD,
        n_reps=N_REPS,
        cores=CORES,
        n_ambulances=N_AMBULANCES,
    )


def test_model_runs():
    """Model completes a short run successfully."""
    config = make_config()
    model = Model(run_number=0, config=config)
    model.run()
    assert len(model.patients) > 0


def test_runner_parallel():
    """Check some short runs in parallel via Runner are successful."""
    config = make_config()

    # Set to run in parallel
    config.cores = -1

    runner = Runner(config=config)
    results = runner.run_reps()
    assert len(results["patients"]) > 0
