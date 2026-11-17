"""Tests for input_times.py."""

import pandas as pd
import pytest

from ambdes.input_times import prepare_time_data


def test_prepare_time_data_unexpected_icb(tmp_path):
    """Raise ValueError when a source ICB label is not recognised."""
    # Example dataframe with an unrecognised ICB provided
    data = pd.DataFrame({
        "C0660_CallOutcomeDetail": ["See & Treat"],
        "ResponseCategoryGroupLevel2": ["Category 1"],
        "IncidentMonth": [1],
        "IncidentDay": [1],
        "C0722_ICBforCommisisonersReports": ["CornwallRegion"],
    })
    path = tmp_path / "time_data.csv"
    data.to_csv(path, index=False)

    # Check that prepare_time_data raises an error
    with pytest.raises(ValueError, match="Unexpected ICB labels:.*") as exc:
        prepare_time_data(path, year=2025)

    assert "CornwallRegion" in str(exc.value)
