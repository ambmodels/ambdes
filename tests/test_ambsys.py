"""Tests for ambsys module."""

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.stats import lognorm

from ambdes import Model, SimConfig, ambsys, lognormal_sd_from_mean_p90

# -----------------------------------------------------------------------------
# ambsys unit tests
# -----------------------------------------------------------------------------


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
                "A26": 650,
                "A31": 700,
                "A32": 750,
                "A34": 800,
                "A35": 850,
                "A37": 900,
                "A38": 950,
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


# -----------------------------------------------------------------------------
# lognormal_sd_from_mean_p90 tests
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mean, sd",
    [
        (10, 3),
        (20, 5),
        (5, 2),
    ],
)
def test_known_param(mean, sd):
    """Test returned sd is correct, when have known mean+sd+90th percentile."""
    # Find lognormal distribution mean (mu) and sd (sigma) - formula from
    # sim-tools.distributions.Lognormal.normal_moments_from_lognormal
    m = mean
    v = sd**2
    phi = math.sqrt(v + m**2)
    mu = math.log(m**2 / phi)
    sigma = math.sqrt(math.log(phi**2 / m**2))

    # Find 90th percentile for this lognormal distribution
    scale = np.exp(mu)
    p90 = lognorm.ppf(0.9, s=sigma, scale=scale)

    # Estimate SD from mean and 90th percentile and check it's consistent
    sd_estimate = lognormal_sd_from_mean_p90(mean=mean, p90=p90)
    assert sd == pytest.approx(sd_estimate)


# -----------------------------------------------------------------------------
# integration tests
# -----------------------------------------------------------------------------


@pytest.mark.integration
def test_values_through_workflow(ambsys_csv_path):
    """End-to-end check that mean IAT correct from CSV -> config -> model."""
    # Extract metrics from CSV
    amb_data = ambsys(
        csv_path=str(ambsys_csv_path),
        org_code="ORG1",
        year=2025,
        month=1,
    )

    # Check ambsys mean_iat_min
    # 31 days in Jan 2025 = 44640 minutes
    expected_mean_iat = {
        1: 44640 / 100,  # 446.4
        2: 44640 / 200,  # 223.2
        3: 44640 / 300,  # 148.8
        4: 44640 / 400,  # 111.6
    }
    assert amb_data["mean_iat_min"].keys() == expected_mean_iat.keys()
    for cat, expected in expected_mean_iat.items():
        assert amb_data["mean_iat_min"][cat] == pytest.approx(expected)

    # Build SimConfig and check it carries values through unchanged
    config = SimConfig(
        ambsys_data=amb_data, resource_hours_per_week=50000, run_length=100
    )
    assert config.mean_iat_min.keys() == expected_mean_iat.keys()
    for cat, expected in expected_mean_iat.items():
        assert config.mean_iat_min[cat] == pytest.approx(expected)

    # Build Model and check each distribution has the right mean
    model = Model(run_number=1, config=config)
    assert set(model.call_dists.keys()) == set(expected_mean_iat.keys())
    for cat, dist in model.call_dists.items():
        assert dist.mean == pytest.approx(expected_mean_iat[cat])
