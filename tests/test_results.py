"""Tests for results module."""

import pandas as pd
import pytest
import simpy
from conftest import StubConfig, StubModel
from vidigi.logging import EventLogger

from ambdes.patient import Patient
from ambdes.results import Results


def make_results(patients, run_number):
    """Wrap patient list in the stubs Results expects."""
    env = simpy.Environment()
    logger = EventLogger(env=env, run_number=run_number)
    config = StubConfig(
        n_ambulances=2,
        warm_up_period=0.0,
        data_collection_period=100.0,
    )
    model = StubModel(config=config, logger=logger, run_number=run_number)
    model.patients = patients
    results = Results(model)
    return results


@pytest.mark.integration
def test_patients():
    """patient_df has expected columns and run value."""
    # Generate patient dataframe from mini patient list
    patients = [
        Patient(patient_id=1, category="C1", call_timestamp=0.0),
        Patient(patient_id=2, category="C2", call_timestamp=5.0),
    ]
    df = make_results(patients, run_number=3).patient_df()

    # Confirm patient dataframe is as expected
    assert df.columns.tolist() == [
        "run",
        "patient_id",
        "category",
        "call_timestamp",
        "response_time",
    ]
    assert df["run"].unique().tolist() == [3]
    assert df["patient_id"].tolist() == [1, 2]
    assert df["category"].tolist() == ["C1", "C2"]
    assert df["response_time"].isna().all()
    assert len(df) == 2


@pytest.mark.integration
def test_summary():
    """summary_df reports run number and patient count correctly."""
    # Generate summary dataframe from mini patient list
    patients = [
        Patient(patient_id=1, category="C1", call_timestamp=0.0),
        Patient(patient_id=2, category="C2", call_timestamp=5.0),
        Patient(patient_id=3, category="C1", call_timestamp=10.0),
    ]
    df = make_results(patients, run_number=7).summary_df()

    # Confirm summary dataframe is as expected
    assert list(df.columns) == [
        "category",
        "n_patients",
        "mean_response_time",
        "run",
        "mean_utilisation",
    ]
    assert len(df.index) == 3

    category_rows = df[df["category"] != "all"].reset_index(drop=True)
    assert category_rows.iloc[0]["run"] == 7
    assert category_rows.iloc[0]["n_patients"] == 2
    assert category_rows.iloc[1]["n_patients"] == 1

    all_row = df[df["category"] == "all"].iloc[0]
    assert all_row["run"] == 7
    assert all_row["n_patients"] is pd.NA or pd.isna(all_row["n_patients"])
