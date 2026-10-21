"""Tests for input modelling."""

import pandas as pd
import pytest

from ambdes import build_arrival_config


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
            rows.append(dict(weekday=day, category=category,
                             outcome="see_and_treat", count=count))

    settings = build_arrival_config(pd.DataFrame(rows))
    params = settings["call_category"]["params"]
    proportions = dict(zip(params["values"], params["freq"], strict=True))

    # Check proportions match the overall proportion in the whole dataset
    assert proportions["C1"] == pytest.approx(96 / 160)
    assert proportions["C2"] == pytest.approx(64 / 160)
