"""Smoke tests - checks the model runs end-to-end without errors."""

from pathlib import Path

from ambdes import ArrivalConfig, Model, ModelConfig, Runner, SimConfig

INPUT = Path(__file__).parent.joinpath("input_data")

ARRIVALS = INPUT / "arrivals.csv"
TIMES = INPUT / "param_times.json"
MODEL = INPUT / "param_model.csv"


def test_model_runs():
    """Model completes a short run successfully."""
    arrival_config = ArrivalConfig(arrival_csv=ARRIVALS)
    model_config = ModelConfig(param_csv=MODEL)
    config = SimConfig(
        arrival_config=arrival_config,
        times_json=TIMES,
        model_config=model_config,
    )
    config.n_ambulances = 1
    model = Model(run_number=0, config=config)
    model.run()
    assert len(model.patients) > 0


def test_runner_parallel():
    """Check some short runs in parallel via Runner are successful."""
    arrival_config = ArrivalConfig(arrival_csv=ARRIVALS)
    model_config = ModelConfig(param_csv=MODEL)
    config = SimConfig(
        arrival_config=arrival_config,
        times_json=TIMES,
        model_config=model_config,
    )
    config.n_ambulances = 1

    # Set to run in parallel
    config.cores = -1

    runner = Runner(config=config)
    results = runner.run_reps()
    assert len(results["patients"]) > 0
