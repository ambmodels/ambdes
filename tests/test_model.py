"""Tests for model logic."""

from pathlib import Path

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
        arrivals_json=ARRIVALS,
        times_json=TIMES,
        warm_up_period=WARM_UP_PERIOD,
        data_collection_period=DATA_COLLECTION_PERIOD,
        n_reps=N_REPS,
        cores=CORES,
        planned_n_ambulances=N_AMBULANCES,
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
