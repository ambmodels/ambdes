"""Tests for model logic."""

from pathlib import Path

import numpy as np
import pandas as pd

from ambdes import Model, Results, SimConfig

INPUT = Path(__file__).parent.joinpath("input_data")

ARRIVALS = INPUT / "param_arrivals.json"
TIMES = INPUT / "param_times.json"

WARM_UP_PERIOD = 100
DATA_COLLECTION_PERIOD = 500
N_REPS = 5
CORES = 1
N_AMBULANCES = 150


def test_no_duplicate_patient_ids():
    """Patient IDs must be unique for the whole run."""
    # Run model with a warm-up period
    config = SimConfig(
        arrivals_config=ARRIVALS,
        times_config=TIMES,
        warm_up_period=WARM_UP_PERIOD,
        data_collection_period=DATA_COLLECTION_PERIOD,
        n_reps=N_REPS,
        cores=CORES,
        n_ambulances=N_AMBULANCES,
    )
    model = Model(run_number=0, config=config)
    model.run()

    # All patients (warm-up or not) will be in the log. Check IDs are unique.
    log = model.logger.to_dataframe()
    entity_id = log[log["event"] == "arrival"]["entity_id"]

    # Entity IDs are reused
    n_total = len(entity_id)
    n_unique = len(entity_id.unique())
    assert n_total == n_unique, (
        "Each ID should only correspond to 1 arrival, but there are ",
        f"{n_total - n_unique} ID corresponding to 2+ arrivals.",
    )

    # When entity IDs are reused, we might then see unusual utilisation
    util_col = Results(model).utilisation_df()["utilisation"]
    util_min = util_col.min()
    assert util_min >= 0 and util_min <= 1, (
        f"Minimum utilisation must be between 0 and 1, but is: {util_min}"
    )
    util_max = util_col.max()
    assert util_max >= 0 and util_max <= 1, (
        f"Minimum utilisation must be between 0 and 1, but is: {util_max}"
    )


def test_patients_matches_log():
    """Check resource use timestamps in patients matches those in log."""
    config = SimConfig(
        arrivals_config=ARRIVALS,
        times_config=TIMES,
        warm_up_period=0,
        data_collection_period=DATA_COLLECTION_PERIOD,
        n_reps=N_REPS,
        cores=CORES,
        n_ambulances=N_AMBULANCES,
    )

    model = Model(run_number=0, config=config)
    model.run()

    # Get the dataframe of times for each patient
    patient_df = pd.DataFrame([vars(p) for p in model.patients])

    # Filter just to complete patients
    patient_df = patient_df[patient_df["wrap_up_time"].notna()]

    # Calculate time patient spends with the ambulance
    patient_df["ambulance_time"] = patient_df[
        [
            "mobilisation_time",
            "time_to_scene",
            "on_scene_time",
            "time_to_hospital",
            "handover_time",
            "wrap_up_time",
        ]
    ].sum(axis=1)

    # Calculate the timestamps for key events (rather than length of time)
    patient_df["allocation_timestamp"] = patient_df[
        ["call_timestamp", "allocation_time"]
    ].sum(axis=1)
    patient_df["amb_release_timestamp"] = patient_df[
        ["allocation_timestamp", "ambulance_time"]
    ].sum(axis=1)

    # Remove patients if they complete after the collection period ends
    patient_df = patient_df.loc[
        patient_df["amb_release_timestamp"] < model.env.now
    ].copy()

    # Get the event log and change ID name to match patients
    amb_events = model.logger.to_dataframe().rename(
        columns={"entity_id": "patient_id"}
    )

    # Reshape from long to wide
    amb_events = amb_events.pivot(
        columns="event", index="patient_id", values="time"
    ).reset_index()

    # Match the completed patients to their logged events
    comparison = patient_df.merge(
        amb_events,
        on="patient_id",
        how="left",
        validate="one_to_one",
    )

    event_pairs = [
        ("call_timestamp", "arrival"),
        ("allocation_timestamp", "ambulance_assigned"),
        ("amb_release_timestamp", "ambulance_available"),
        ("amb_release_timestamp", "depart"),
    ]

    for patient_event, amb_event in event_pairs:
        matched = np.isclose(
            comparison[patient_event],
            comparison[amb_event],
            rtol=0,
            atol=1e-9,
            equal_nan=False,
        )

        mismatches = comparison.loc[
            ~matched,
            ["patient_id", patient_event, amb_event],
        ]

        assert mismatches.empty, (
            f"{patient_event} does not match {amb_event}:\n{mismatches}"
        )
