"""Regression tests - results are consistent over time."""

from pathlib import Path

import pandas as pd

from ambdes import (
    Model,
    Results,
    Runner,
    SimConfig,
    run_warm_up_audit,
)

INPUT = Path(__file__).parent.joinpath("input_data")
OUTPUT = Path(__file__).parent.joinpath("regression_results")

ARRIVALS = INPUT / "param_arrivals.json"
TIMES = INPUT / "param_times.json"

WARM_UP_PERIOD = 10
DATA_COLLECTION_PERIOD = 400
N_REPS = 5
CORES = 1
RESOURCE_HOURS_PER_WEEK = 2000

MODEL_UTIL = OUTPUT / "model_utilisation_df.csv"
MODEL_SUMMARY = OUTPUT / "model_summary_df.csv"
RUNNER_RUN = OUTPUT / "runner_run.csv"
RUNNER_OVERALL = OUTPUT / "runner_overall.csv"
AUDIT = OUTPUT / "audit.csv"


def make_config():
    """Create a standard simulation config for regression tests."""
    return SimConfig(
        arrivals_json=ARRIVALS,
        times_json=TIMES,
        warm_up_period=WARM_UP_PERIOD,
        data_collection_period=DATA_COLLECTION_PERIOD,
        n_reps=N_REPS,
        cores=CORES,
        resource_hours_per_week=RESOURCE_HOURS_PER_WEEK,
    )


def test_model_consistent():
    """Model results are consistent."""
    # Run model
    config = make_config()
    model = Model(run_number=0, config=config)
    model.run()

    # Extract results from model
    util = Results(model).utilisation_df()
    summary = Results(model).summary_df()

    # Import expected results
    exp_util = pd.read_csv(MODEL_UTIL)
    exp_summary = pd.read_csv(MODEL_SUMMARY)

    # Check extracted results match expected
    pd.testing.assert_frame_equal(util, exp_util)
    pd.testing.assert_frame_equal(summary, exp_summary)


def test_runner_consistent():
    """Runner run_reps() results are consistent."""
    # Run replications
    config = make_config()
    results = Runner(config=config).run_reps()

    # Import expected results
    exp_run = pd.read_csv(RUNNER_RUN)
    exp_overall = pd.read_csv(RUNNER_OVERALL)

    # Check extracted results match expected
    pd.testing.assert_frame_equal(results["run"], exp_run)
    pd.testing.assert_frame_equal(results["overall"], exp_overall)


def test_warmup_audit_consistent():
    """Warm-up audit results are consistent."""
    # Run warm-up audit
    config = make_config()
    audit = run_warm_up_audit(config=config, interval=30, n_reps=2)

    # Import expected results
    exp_audit = pd.read_csv(AUDIT)

    # Check extracted results match expected
    pd.testing.assert_frame_equal(audit, exp_audit)
