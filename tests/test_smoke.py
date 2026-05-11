"""Smoke tests - checks the model runs end-to-end without errors."""

import pytest
from ambdes import Model, SimConfig

AMBSYS_DATA = {
    "mean_iat_min": {"C1": 60.0, "C2": 30.0, "C3": 20.0, "C4": 15.0},
    "mean_response_time_min": {"C1": 8.0, "C2": 18.0, "C3": 60.0, "C4": 90.0},
    "p90_response_time_min": {
        "C1": 15.0,
        "C2": 40.0,
        "C3": 120.0,
        "C4": 180.0,
    },
    "sd_response_time_min": {"C1": 5.0, "C2": 12.0, "C3": 40.0, "C4": 60.0},
    "mean_handover_time_min": 20.0,
    "p90_handover_time_min": 45.0,
    "sd_handover_time_min": 15.0,
}


@pytest.mark.integration
@pytest.mark.parametrize(
    "log_to_console",
    [
        (True),
        (False),
    ],
)
def test_model_runs_without_error(log_to_console):
    """Model completes a short run (with/without logs) successfully."""
    config = SimConfig(
        ambsys_data=AMBSYS_DATA, run_length=100, log_to_console=log_to_console
    )
    model = Model(run_number=0, config=config)
    model.run()
    assert len(model.patients) > 0
