"""Tests for input_arrivals.py."""

import pandas as pd
import pytest

from ambdes.input_arrivals import build_arrival_config, get_mean_arrivals


def test_arrival_config_with_unequal_arrivals():
    """Category proportions should weight by arrivals per day."""
    # Previous code summed by day then did mean across days - meaning it
    # equally weighted each day, even if one had lots of arrivals and one had
    # few. That code has been changed to just sum across whole dataset, but
    # this is a test for that previous issue.

    # Build a synthetic patient dataframe where one day has high arrivals
    # and rest are lower
    rows = []
    for day in range(7):
        counts = (90, 10) if day == 0 else (1, 9)
        for category, count in zip(("C1", "C2"), counts, strict=True):
            rows.append(
                dict(
                    weekday=day,
                    category=category,
                    outcome="see_and_treat",
                    count=count,
                )
            )

    settings = build_arrival_config(pd.DataFrame(rows))
    params = settings["call_category"]["params"]
    proportions = dict(zip(params["values"], params["freq"], strict=True))

    # Check proportions match the overall proportion in the whole dataset
    assert proportions["C1"] == pytest.approx(96 / 160)
    assert proportions["C2"] == pytest.approx(64 / 160)


def test_mean_arrivals_with_zeroes():
    """Mean arrivals should include zero counts."""
    # Create dataframe with four rows:
    # - First Monday : C1
    # - First Monday : C1
    # - First Monday : C2
    # - Second Monday : C2
    # So totals are:
    # - First Monday : 2 x C1 and 1 x C2
    # - Seconday Monday : 0 x C1 and 1 x C2
    patients = pd.DataFrame(
        [
            {
                "IncidentMonth": 1,
                "IncidentDay": day,
                "weekday": 0,
                "IncidentHour": 9,
                "category": category,
                "outcome": "see_and_treat",
            }
            for day, category in [
                (1, "C1"),
                (1, "C1"),
                (1, "C2"),
                (8, "C2"),
            ]
        ]
    )

    # Expected means: 1 and 1
    result = get_mean_arrivals(time_df=patients)
    for cat in ["C1", "C2"]:
        cat_result = result.loc[result["category"].eq(cat), "count"]
        assert len(cat_result) == 1
        assert cat_result.iloc[0] == 1.0


def test_arrival_config_with_zeroes():
    """Arrival config should use 0."""
    # Create dataframe with 7 weekdays with mean arrival count for each
    # Category 1 see and convey or see and treat
    # Category 2 just see and treat
    arrivals = pd.DataFrame([
        {
            "weekday": day,
            "category": category,
            "outcome": outcome,
            "count": count,
        }
        for day in range(7)
        for category, outcome, count in [
            ("C1", "see_and_convey", 9 if day == 0 else 1),
            ("C1", "see_and_treat", 1),
            ("C2", "see_and_treat", 2),
        ]
    ])

    config = build_arrival_config(arrivals)

    def probabilities(category):
        """Get probabilities from config as a dict."""
        params = config["call_outcome"][category]["params"]
        return dict(zip(
            params["values"], params["freq"], strict=True
        ))

    assert probabilities("C1") == pytest.approx({
        "see_and_convey": 15 / 22,
        "see_and_treat": 7 / 22,
    })
    assert probabilities("C2") == pytest.approx({
        "see_and_convey": 0.0,
        "see_and_treat": 1.0,
    })
