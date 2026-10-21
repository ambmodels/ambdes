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

    # Convert wide-to-long dataframe of key event timestamps
    patient_events = patient_df[
        ["call_timestamp", "allocation_timestamp", "amb_release_timestamp"]
    ].copy()
    patient_events = patient_events.melt(
        var_name="patient_event", value_name="time"
    ).sort_values("time")

    # Get the event log
    amb_events = model.logger.to_dataframe()
    amb_events = amb_events[["time", "event"]].rename(
        columns={"event": "amb_event"}
    )

    event_pairs = [
        ("call_timestamp", "arrival"),
        ("allocation_timestamp", "ambulance_assigned"),
        ("amb_release_timestamp", "ambulance_available"),
        ("amb_release_timestamp", "depart"),
    ]

    for patient_event, amb_event in event_pairs:

        # Get all the times for that event pair
        patient_times = patient_events.loc[
            patient_events["patient_event"] == patient_event, "time"
        ]
        amb_times = amb_events.loc[
            amb_events["amb_event"] == amb_event, "time"
        ].to_numpy()

        # Check each patient time has a matching ambulance-event time
        matched = patient_times.apply(
            lambda time, amb_times=amb_times: np.isclose(
                amb_times,
                time,
                rtol=0,
                atol=1e-9,
            ).any()
        )

        missing = patient_times[~matched]

        assert missing.empty, (
            f"{patient_event} has no matching {amb_event} "
            f"at these times:\n{missing}"
        )
