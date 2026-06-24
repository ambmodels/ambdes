"""Smoke tests - checks the model runs end-to-end without errors."""

from pathlib import Path
from ambdes import ArrivalConfig, Model, ModelConfig, SimConfig, TimesConfig


ARRIVALS = Path(__file__).parent.joinpath("data/param_arrivals.csv")
TIMES = Path(__file__).parent.joinpath("data/param_times.csv")
MODEL = Path(__file__).parent.joinpath("data/param_model.csv")


def test_model_runs():
    """Model completes a short run successfully."""
    arrival_config = ArrivalConfig(arrival_csv=ARRIVALS)
    times_config = TimesConfig(times_csv=TIMES)
    model_config = ModelConfig(param_csv=MODEL)
    config = SimConfig(
        arrival_config=arrival_config,
        times_config=times_config,
        model_config=model_config,
    )
    config.n_ambulances = 1
    model = Model(run_number=0, config=config)
    model.run()
    assert len(model.patients) > 0
