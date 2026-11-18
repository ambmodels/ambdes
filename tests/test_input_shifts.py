"""Tests for input_shifts.py."""

import pandas as pd

from ambdes.input_shifts import create_availability_schedule


def test_availability_includes_zero_event_hours():
    """Two vehicles on rest in one week, none in other, should be mean 1."""
    resources = pd.DataFrame(
        {
            "start_hour": pd.to_datetime(
                [
                    "2025-01-06 09:00",  # Monday, week 1
                    "2025-01-06 09:00",
                    "2025-01-13 09:00",  # Monday, week 2
                ]
            ),
            "time": [540, 540, 540],
            "EventTypeGrouped": [
                "available",
                "rest_break",
                "available",
            ],
            "vehicles": [8.0, 2.0, 10.0],
        }
    )

    result = create_availability_schedule(resources).set_index("time")

    assert result.loc[540, "rest_break"] == 1.0
    assert result.loc[540, "available"] == 9.0

    # Event types absent throughout the data still have zero columns.
    assert result.loc[540, "restricted_send"] == 0.0
    assert result.loc[540, "unavailable"] == 0.0
    assert result.loc[540, "allocated"] == 0.0
