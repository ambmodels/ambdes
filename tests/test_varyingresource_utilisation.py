"""Test utilisation calculations are valid when varying resource."""

import pandas as pd

from ambdes import UtilisationCalculator


def usage_log(*intervals):
    """Create ambulance event log from named interval dictionaries."""
    records = []
    for interval in intervals:
        records.append(
            {
                "entity_id": interval["entity_id"],
                "event": "ambulance_assigned",
                "event_type": "resource_use",
                "time": float(interval["start"]),
            }
        )

        if interval["end"] is not None:
            records.append(
                {
                    "entity_id": interval["entity_id"],
                    "event": "ambulance_available",
                    "event_type": "resource_use_end",
                    "time": float(interval["end"]),
                }
            )

    return pd.DataFrame(records)


def test_utilisation_with_varying_resource():
    """Check utilisation looks correct when resource varies."""
    amb_log = usage_log(
        {"entity_id": 1, "start": 1, "end": 5},
        {"entity_id": 2, "start": 3, "end": 9},
    )

    capacity_log = [
        {"time": 0.0, "capacity": 2},
        {"time": 5.0, "capacity": 1},
        {"time": 7.0, "capacity": 2},
    ]

    exp_util_df = pd.DataFrame(
        [
            {
                "time": 0,
                "busy": 0,
                "capacity": 2,
                "interval_duration": 1,
                "utilisation": 0,
            },
            {
                "time": 1,
                "busy": 1,
                "capacity": 2,
                "interval_duration": 2,
                "utilisation": 0.5,
            },
            {
                "time": 3,
                "busy": 2,
                "capacity": 2,
                "interval_duration": 2,
                "utilisation": 1,
            },
            {
                "time": 5,
                "busy": 1,
                "capacity": 1,
                "interval_duration": 2,
                "utilisation": 1,
            },
            {
                "time": 7,
                "busy": 1,
                "capacity": 2,
                "interval_duration": 2,
                "utilisation": 0.5,
            },
            {
                "time": 9,
                "busy": 0,
                "capacity": 2,
                "interval_duration": 1,
                "utilisation": 0,
            },
        ]
    )
    exp_util_df = exp_util_df.astype(
        {
            "time": float,
            "interval_duration": float,
        }
    )

    calc = UtilisationCalculator(
        log=amb_log,
        warm_up_period=0,
        data_collection_period=10,
        capacity_log=capacity_log,
    )

    pd.testing.assert_frame_equal(calc.create_util_df(), exp_util_df)


def test_last_capacity_used():
    """Several individual removals at one time should form one final state."""
    amb_log = usage_log({"entity_id": 1, "start": 0, "end": 10})

    capacity_log = [
        {"time": 0.0, "capacity": 3},
        {"time": 0.0, "capacity": 2},
        {"time": 0.0, "capacity": 1},
    ]

    calc = UtilisationCalculator(
        log=amb_log,
        warm_up_period=0,
        data_collection_period=10,
        capacity_log=capacity_log,
    )

    assert calc.mean_utilisation() == 1
    assert calc.create_util_df()["capacity"].tolist() == [1.0]


def test_no_capacity_excluded():
    """Periods with no operational ambulances should be excluded."""
    amb_log = usage_log(
        {"entity_id": 1, "start": 0, "end": 4},
        {"entity_id": 2, "start": 6, "end": 10},
    )
    capacity_log = [
        # One ambulance in pool (and in use)
        {"time": 0, "capacity": 1},
        # No ambulances in pool
        {"time": 4, "capacity": 0},
        # Ambulance returned to pool (and in use))
        {"time": 6, "capacity": 1},
    ]

    calc = UtilisationCalculator(
        log=amb_log,
        warm_up_period=0,
        data_collection_period=10,
        capacity_log=capacity_log,
    )
    assert calc.mean_utilisation() == 1.0
    assert (calc.create_util_df()["capacity"] > 0).all()
