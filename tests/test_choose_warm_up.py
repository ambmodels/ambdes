"""Tests for choose_warm_up module."""

from types import SimpleNamespace

import numpy as np
import pytest

from ambdes import SimConfig, WarmUpAuditor, run_warm_up_audit

AMBSYS_DATA = {
    "mean_iat_min": {"C1": 60.0, "C2": 30.0, "C3": 20.0, "C4": 15.0},
    "mean_handover_time_min": 20.0,
    "p90_handover_time_min": 45.0,
    "sd_handover_time_min": 15.0,
}


@pytest.mark.unit
def test_get_response_times_returns_mean():
    """_get_response_times returns mean response time by category."""
    patients = [
        SimpleNamespace(category="C1", response_time=10.0),
        SimpleNamespace(category="C1", response_time=20.0),
        SimpleNamespace(category="C2", response_time=30.0),
        SimpleNamespace(category="C3", response_time=None),
    ]
    model = SimpleNamespace(patients=patients)
    auditor = WarmUpAuditor(model=model, interval=10)

    result = auditor._get_response_times()

    assert result["C1"] == 15.0
    assert result["C2"] == 30.0
    assert np.isnan(result["C3"])
    assert np.isnan(result["C4"])


@pytest.mark.unit
def test_to_df_returns_expected_columns():
    """to_df returns audit results with run column."""
    model = SimpleNamespace(run_number=7)
    auditor = WarmUpAuditor(model=model, interval=10)
    auditor.audit_results = [
        {"time": 0, "category": "C1", "response_time": np.nan},
        {"time": 0, "category": "C2", "response_time": 12.0},
    ]

    result = auditor.to_df()

    assert list(result.columns) == ["time", "category", "response_time", "run"]
    assert (result["run"] == 7).all()
    assert len(result) == 2


@pytest.mark.system
def test_run_warm_up_audit_returns_expected_columns():
    """run_warm_up_audit returns audit data for all runs."""
    config = SimConfig(
        ambsys_data=AMBSYS_DATA,
        warm_up_period=0,
        data_collection_period=100,
    )

    result = run_warm_up_audit(config=config, interval=20, n_reps=2)

    assert not result.empty
    assert {"time", "category", "response_time", "run"} <= set(result.columns)
    assert set(result["run"]) == {0, 1}
    assert set(result["category"]) == {"C1", "C2", "C3", "C4"}
