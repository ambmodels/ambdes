"""Test model configuration."""

from ambdes import SimConfig

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def make_arrivals_config():
    """Minimal arrivals config for SimConfig tests."""
    return {
        "call_arrival": {
            "params": {
                "t": [0],
                "mean_iat": [10],
            }
        }
    }


def make_times_config():
    """Minimal times config for SimConfig tests."""
    return {}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_create_permit_schedule():
    """Permit schedule should equal ambulances minus restricted send."""
    config = SimConfig(
        arrivals_config=make_arrivals_config(),
        times_config=make_times_config(),
        warm_up_period=0,
        data_collection_period=100,
        n_reps=1,
        n_ambulances=None,
        ambulance_schedule={
            0: 10,
            60: 12,
            120: 8,
        },
        restricted_send_schedule={
            0: 2,
            90: 3,
        },
        ambulance_schedule_period=180,
    )

    expected = {
        0: 8,  # 10 - 2
        60: 10,  # 12 - 2
        90: 9,  # 12 - 3
        120: 5,  # 8 - 3
    }

    assert config.permit_schedule == expected
