"""Tests for runner module."""

import pandas as pd
import pytest

from ambdes import Runner, SimConfig

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


@pytest.mark.system
def test_run_single():
    """run_single returns patients and run DataFrames for one run."""
    # Run single
    config = SimConfig(ambsys_data=AMBSYS_DATA, run_length=200)
    runner = Runner(config=config)
    results = runner.run_single(run_number=0)
    # Check results
    assert set(results.keys()) == {"patients", "run"}
    assert isinstance(results["patients"], pd.DataFrame)
    assert isinstance(results["run"], pd.DataFrame)
    assert len(results["run"].index) == 4


@pytest.mark.system
def test_run_reps():
    """run_reps combines results across multiple runs."""
    # Run replications
    config = SimConfig(ambsys_data=AMBSYS_DATA, run_length=200, n_reps=3)
    runner = Runner(config=config)
    results = runner.run_reps()
    # Check results
    patients = results["patients"]
    run = results["run"]
    overall = results["overall"]
    assert patients["run"].nunique() == 3
    assert run["run"].nunique() == 3
    assert len(run.index) == 12
    assert len(overall.index) == 4
    assert isinstance(patients, pd.DataFrame)
    assert isinstance(run, pd.DataFrame)
    assert isinstance(overall, pd.DataFrame)
