"""Tests for config module."""

import pytest

from ambdes import SimConfig

# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

AMBSYS_DATA = {
    "mean_iat_min": {"C1": 60.0, "C2": 30.0, "C3": 20.0, "C4": 15.0},
    "mean_handover_time_min": 20.0,
    "p90_handover_time_min": 45.0,
    "sd_handover_time_min": 15.0,
}


@pytest.fixture
def config():
    """Return a SimConfig instance with minimal AMBSYS_DATA."""
    return SimConfig(ambsys_data=AMBSYS_DATA)


# -----------------------------------------------------------------------------
# dist_config
# -----------------------------------------------------------------------------


@pytest.mark.unit
def test_dist_config_keys(config):
    """dist_config has the expected top-level keys."""
    assert set(config.dist_config.keys()) == {
        "call",
        "time_to_scene",
        "handover_time",
        "time_to_hospital",
    }


@pytest.mark.unit
def test_dist_config_call_categories(config):
    """Call distributions are created for each category in ambsys_data."""
    assert set(config.dist_config["call"].keys()) == {"C1", "C2", "C3", "C4"}


@pytest.mark.unit
def test_dist_config_call_mean_passthrough(config):
    """Call distribution means matches mean_iat_min from ambsys_data."""
    for cat, mean_iat in AMBSYS_DATA["mean_iat_min"].items():
        assert config.dist_config["call"][cat]["params"]["mean"] == mean_iat


# -----------------------------------------------------------------------------
# n_ambulances
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "resource_hours_per_week, expected_n",
    [
        (52000, round(52000 / 168)),  # 52,000 hours (default)
        (168, 1),  # Exactly one ambulance
        (169, 1),  # Rounds down
        (252, 2),  # Rounds up (252/168 = 1.5 -> 2)
    ],
)
def test_n_ambulances(resource_hours_per_week, expected_n):
    """Check ambulance count calculation and rounding are correct."""
    config = SimConfig(
        ambsys_data=AMBSYS_DATA,
        resource_hours_per_week=resource_hours_per_week,
    )
    assert config.n_ambulances == expected_n
