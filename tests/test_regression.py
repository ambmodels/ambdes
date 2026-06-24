"""Regression tests - results are consistent over time."""

from pathlib import Path

import pandas as pd

from ambdes import (
    ArrivalConfig,
    Model,
    ModelConfig,
    Results,
    Runner,
    SimConfig,
    TimesConfig,
    run_warm_up_audit,
)

INPUT = Path(__file__).parent.joinpath("input_data")
OUTPUT = Path(__file__).parent.joinpath("regression_results")

ARRIVALS = INPUT / "param_arrivals.csv"
TIMES = INPUT / "param_times.csv"
MODEL = INPUT / "param_model.csv"

MODEL_PATIENT = OUTPUT / "model_patient_df.csv"
MODEL_UTIL = OUTPUT / "model_utilisation_df.csv"
MODEL_SUMMARY = OUTPUT / "model_summary_df.csv"
RUNNER_PATIENTS = OUTPUT / "runner_patients.csv"
RUNNER_RUN = OUTPUT / "runner_run.csv"
RUNNER_OVERALL = OUTPUT / "runner_overall.csv"
AUDIT = OUTPUT / "audit.csv"


def make_config():
    """Create a standard simulation config for regression tests."""
    arrival_config = ArrivalConfig(arrival_csv=ARRIVALS)
    times_config = TimesConfig(times_csv=TIMES)
    model_config = ModelConfig(param_csv=MODEL)
    return SimConfig(
        arrival_config=arrival_config,
        times_config=times_config,
        model_config=model_config,
    )


def test_model_consistent():
    """Model results are consistent."""
    # Run model
    config = make_config()
    model = Model(run_number=0, config=config)
    model.run()

    # Extract results from model
    patients = Results(model).patient_df()
    util = Results(model).utilisation_df()
    summary = Results(model).summary_df()

    # Import expected results
    exp_patients = pd.read_csv(MODEL_PATIENT)
    exp_util = pd.read_csv(MODEL_UTIL)
    exp_summary = pd.read_csv(MODEL_SUMMARY)

    # Check extracted results match expected
    pd.testing.assert_frame_equal(patients, exp_patients)
    pd.testing.assert_frame_equal(util, exp_util)
    pd.testing.assert_frame_equal(summary, exp_summary)


def test_runner_consistent():
    """Runner run_reps() results are consistent."""
    # Run replications
    config = make_config()
    results = Runner(config=config).run_reps()

    # Import expected results
    exp_patients = pd.read_csv(RUNNER_PATIENTS)
    exp_run = pd.read_csv(RUNNER_RUN)
    exp_overall = pd.read_csv(RUNNER_OVERALL)

    # Check extracted results match expected
    pd.testing.assert_frame_equal(results["patients"], exp_patients)
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
