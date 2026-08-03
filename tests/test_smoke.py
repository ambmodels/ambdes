"""Smoke tests - checks the model runs end-to-end without errors."""

from pathlib import Path

from ambdes import Model, Runner, SimConfig

INPUT = Path(__file__).parent.joinpath("input_data")

ARRIVALS = INPUT / "param_arrivals.json"
TIMES = INPUT / "param_times.json"
MODEL = INPUT / "param_model.csv"


def test_model_runs():
    """Model completes a short run successfully."""
    config = SimConfig(
        arrivals_json=ARRIVALS,
        times_json=TIMES,
        param_csv=MODEL,
    )
    config.n_ambulances = 1
    model = Model(run_number=0, config=config)
    model.run()
    assert len(model.patients) > 0


def test_runner_parallel():
    """Check some short runs in parallel via Runner are successful."""
    config = SimConfig(
        arrivals_json=ARRIVALS,
        times_json=TIMES,
        param_csv=MODEL,
    )
    config.n_ambulances = 1

    # Set to run in parallel
    config.cores = -1

    runner = Runner(config=config)
    results = runner.run_reps()
    assert len(results["patients"]) > 0
