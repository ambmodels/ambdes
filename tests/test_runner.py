"""Tests for runner module."""

import pandas as pd
import pytest

from ambdes import Runner, SimConfig

AMBSYS_DATA = {
    "mean_iat_min": {"C1": 60.0, "C2": 30.0, "C3": 20.0, "C4": 15.0},
    "mean_handover_time_min": 20.0,
    "p90_handover_time_min": 45.0,
    "sd_handover_time_min": 15.0,
}


# -----------------------------------------------------------------------------
# Checking the basics - that Runner works as expected
# -----------------------------------------------------------------------------

@pytest.mark.system
def test_run_single():
    """run_single returns patients and run DataFrames for one run."""
    # Run single
    config = SimConfig(ambsys_data=AMBSYS_DATA, run_length=200)
    runner = Runner(config=config)
    results = runner.run_single(run_number=0)
    # Check results
    assert set(results.keys()) == {"model", "patients", "run"}
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


# -----------------------------------------------------------------------------
# Checking the results from running different scenarios
# -----------------------------------------------------------------------------

def test_n_ambulance_response_times():
    """Reducing n_ambulances results in increased response times."""
    levels = [10, 8, 6, 4]
    category_means = {cat: [] for cat in ["C1", "C2", "C3", "C4"]}

    for n in levels:
        config = SimConfig(ambsys_data=AMBSYS_DATA, run_length=1000)
        config.n_ambulances = n
        result = Runner(config).run_single(run_number=0)["run"]

        for cat in category_means:
            mean_rt = result.loc[
                result["category"] == cat, "mean_response_time"
            ].iloc[0]
            category_means[cat].append(mean_rt)

    for cat, values in category_means.items():
        assert values[0] < values[1] < values[2] < values[3], (
            f"Expected RT[10] < RT(8) < RT(6) < RT(4) for {cat}, "
            f"got {values}"
        )
