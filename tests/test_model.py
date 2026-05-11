"""Tests for model module."""

import pytest

from ambdes import Model, SimConfig

# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

AMBSYS_DATA = {
    "mean_iat_min": {"C1": 60.0, "C2": 30.0, "C3": 20.0, "C4": 15.0},
    "mean_response_time_min": {"C1": 8.0, "C2": 18.0, "C3": 60.0, "C4": 90.0},
    "p90_response_time_min": {
        "C1": 15.0,
        "C2": 40.0,
        "C3": 120.0,
        "C4": 180.0,
    },
    "sd_response_time_min": {"C1": 5.0, "C2": 12.0, "C3": 40.0, "C4": 60.0},
    "mean_handover_time_min": 20.0,
    "p90_handover_time_min": 45.0,
    "sd_handover_time_min": 15.0,
}


def make_model(
    run_number=0, run_length=500, resource_hours_per_week=52000, **kwargs
):
    """Create a Model instance with a minimal default configuration.

    Builds a SimConfig from AMBSYS_DATA and the provided parameters, then
    returns an unrun Model. Additional SimConfig keyword arguments can be
    passed via **kwargs.

    Parameters
    ----------
    run_number : int, optional
        Simulation run identifier used to seed distributions.
    run_length : float, optional
        Duration of the simulation run in minutes.
    resource_hours_per_week : int, optional
        Ambulance resource hours per week, used to derive n_ambulances.
    **kwargs
        Additional keyword arguments passed to SimConfig.

    Returns
    -------
    Model
        An initialised but unrun simulation model.

    """
    config = SimConfig(
        ambsys_data=AMBSYS_DATA,
        run_length=run_length,
        resource_hours_per_week=resource_hours_per_week,
        **kwargs,
    )
    return Model(run_number=run_number, config=config)


# -----------------------------------------------------------------------------
# patients
# -----------------------------------------------------------------------------


@pytest.mark.integration
def test_patient_generation():
    """Patients are generated with appropriate attributes."""
    run_length = 500
    model = make_model(run_length=run_length)
    model.run()

    # Patients are generated
    assert len(model.patients) > 0

    # Patient IDs are assigned sequentially starting from 1
    ids = [p.patient_id for p in model.patients]
    assert ids == list(range(1, len(ids) + 1))

    # All patients have recognised response category
    valid = {"C1", "C2", "C3", "C4"}
    assert all(p.category in valid for p in model.patients)

    # All call timestamps are non-negative
    assert all(p.call_timestamp >= 0 for p in model.patients)

    # No patient is recorded with a call timestamp beyond run_length
    assert all(p.call_timestamp <= run_length for p in model.patients)


@pytest.mark.integration
def test_completed_patients():
    """Patients who completed the full pathway have all time attributes."""
    # Use a long run so there is time for patients to complete
    model = make_model(run_length=2000)
    model.run()

    # Check all time attributes are positive.
    for p in model.patients:
        if p.response_time is not None:
            assert p.response_time > 0
        if p.travel_time_to_hospital is not None:
            assert p.travel_time_to_hospital > 0
        if p.handover_time is not None:
            assert p.handover_time > 0

    # Check there is at least 1 patient with all time attributes i.e. complete
    completed = [
        p
        for p in model.patients
        if p.response_time is not None
        and p.travel_time_to_hospital is not None
        and p.handover_time is not None
    ]
    assert len(completed) > 0


# -----------------------------------------------------------------------------
# Tests with very little or very high demand
# -----------------------------------------------------------------------------


@pytest.mark.integration
def test_high_demand():
    """Model completes without error under very high call volume."""
    # Very low inter-arrival time
    high_demand_data = {
        **AMBSYS_DATA,
        "mean_iat_min": {"C1": 1.0, "C2": 1.0, "C3": 1.0, "C4": 1.0},
    }
    config = SimConfig(
        ambsys_data=high_demand_data,
        resource_hours_per_week=168,  # 1 ambulance
        run_length=500,
    )
    model = Model(run_number=0, config=config)
    model.run()
    assert len(model.patients) > 0


@pytest.mark.integration
def test_low_demand():
    """Model completes without error when calls are extremely rare."""
    # Very high inter-arrival time
    low_demand_data = {
        **AMBSYS_DATA,
        "mean_iat_min": {"C1": 1e6, "C2": 1e6, "C3": 1e6, "C4": 1e6},
    }
    config = SimConfig(ambsys_data=low_demand_data, run_length=500)
    model = Model(run_number=0, config=config)
    model.run()
    assert len(model.patients) == 0


# -----------------------------------------------------------------------------
# Reproducibility
# -----------------------------------------------------------------------------


@pytest.mark.integration
def test_same_seed_same_results():
    """Two runs with the same run_number produce identical results."""
    m1 = make_model(run_number=42, run_length=500)
    m2 = make_model(run_number=42, run_length=500)
    m1.run()
    m2.run()
    assert len(m1.patients) == len(m2.patients)
    assert [p.call_timestamp for p in m1.patients] == [
        p.call_timestamp for p in m2.patients
    ]


@pytest.mark.integration
def test_different_seeds_different_results():
    """Two runs with different run_numbers produce different results."""
    m1 = make_model(run_number=0, run_length=500)
    m2 = make_model(run_number=1, run_length=500)
    m1.run()
    m2.run()
    assert [p.call_timestamp for p in m1.patients] != [
        p.call_timestamp for p in m2.patients
    ]
