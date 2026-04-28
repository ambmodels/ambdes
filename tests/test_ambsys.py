"""Tests for ambsys."""

from pathlib import Path

import pandas as pd
import pytest

from ambdes import ambsys


@pytest.fixture
def ambsys_csv_path(tmp_path) -> Path:
    """Create a minimal AmbSYS CSV file and return its path."""
    df = pd.DataFrame(
        [
            {
                "Org Code": "ORG1",
                "Year": 2025,
                "Month": 1,
                "A8": 100,
                "A10": 200,
                "A11": 300,
                "A12": 400,
                "A25": 600,
                "A31": 700,
                "A34": 800,
                "A37": 900,
                "A142": 120,
            }
        ]
    )

    path = tmp_path / "ambsys.csv"
    df.to_csv(path, index=False)
    return path


@pytest.mark.unit
@pytest.mark.parametrize(
    "year, month",
    [
        (2025, 1),
        ("2025", 1),
        (2025, "1"),
        ("2025", "1"),
    ],
)
def test_int_str_year_month(ambsys_csv_path, year, month):
    """Test it works with int or str for year or month."""
    result = ambsys(
        csv_path=str(ambsys_csv_path),
        org_code="ORG1",
        year=year,
        month=month,
    )
    assert result is not None


@pytest.mark.unit
@pytest.mark.parametrize(
    "org_code, year, month",
    [
        ("OTHER_ORG", 2025, 1),  # missing org
        ("ORG1", 2024, 1),  # missing year
        ("ORG1", 2025, 2),  # missing month
    ],
)
def test_missing_from_ambsys(ambsys_csv_path, org_code, year, month):
    """Test error is raised when provide org code+month+year not in CSV."""
    with pytest.raises(ValueError, match="No AmbSYS data found"):
        ambsys(
            csv_path=str(ambsys_csv_path),
            org_code=org_code,
            year=year,
            month=month,
        )
