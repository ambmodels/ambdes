"""Regression tests - results are consistent over time."""

from pathlib import Path

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

RUN_NUMBER = 0
RUN_LENGTH = 2_000

PATIENTS_PATH = Path(__file__).parent.joinpath("regression/patients.csv")
SUMMARY_PATH = Path(__file__).parent.joinpath("regression/summary.csv")


@pytest.mark.regression
def test_results_match_baseline():
    """Patient-level and summary results match stored baseline."""
    # Run model
    config = SimConfig(ambsys_data=AMBSYS_DATA, run_length=RUN_LENGTH)
    runner = Runner(config=config)
    results = runner.run_single(run_number=RUN_NUMBER)
    # Import stored baseline results
    baseline_patients = pd.read_csv(PATIENTS_PATH)
    baseline_summary = pd.read_csv(SUMMARY_PATH)
    # Check results are consistent
    pd.testing.assert_frame_equal(results["patients"], baseline_patients)
    pd.testing.assert_frame_equal(results["summary"], baseline_summary)
