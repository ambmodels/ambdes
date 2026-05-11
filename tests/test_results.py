"""Tests for results module."""

import pytest

from ambdes.patient import Patient
from ambdes.results import Results


@pytest.mark.integration
def test_patients():
    """patient_df has expected columns and run value."""
    # Generate patient dataframe from mini patient list
    patients = [
        Patient(patient_id=1, category="C1", call_timestamp=0.0),
        Patient(patient_id=2, category="C2", call_timestamp=5.0),
    ]
    results = Results(patients=patients, run_number=3)
    df = results.patient_df()

    # Confirm patient dataframe is as expected
    assert df.columns.tolist() == [
        "run",
        "patient_id",
        "category",
        "call_timestamp",
        "response_time",
        "travel_time_to_hospital",
        "handover_time",
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
    results = Results(patients=patients, run_number=7)
    df = results.summary_df()

    # Confirm summary dataframe is as expected
    assert list(df.columns) == ["run", "n_patients"]
    assert len(df) == 1
    row = df.iloc[0]
    assert row["run"] == 7
    assert row["n_patients"] == len(patients)
