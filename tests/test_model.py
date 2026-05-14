"""Tests for model module."""

import pytest

from ambdes import Model, SimConfig

# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

AMBSYS_DATA = {
    "mean_iat_min": {"C1": 60.0, "C2": 30.0, "C3": 20.0, "C4": 15.0},
    "mean_handover_time_min": 20.0,
    "p90_handover_time_min": 45.0,
    "sd_handover_time_min": 15.0,
}


def make_model(
    run_number=0,
    data_collection_period=500,
    resource_hours_per_week=52000,
    **kwargs,
):
    """Create a Model instance with a minimal default configuration.

    Builds a SimConfig from AMBSYS_DATA and the provided parameters, then
    returns an unrun Model. Additional SimConfig keyword arguments can be
    passed via **kwargs.

    Parameters
    ----------
    run_number : int, optional
        Simulation run identifier used to seed distributions.
    data_collection_period : float, optional
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
        warm_up_period=0,
        data_collection_period=data_collection_period,
        resource_hours_per_week=resource_hours_per_week,
        **kwargs,
    )
    return Model(run_number=run_number, config=config)


# -----------------------------------------------------------------------------
# patients
# -----------------------------------------------------------------------------


@pytest.mark.system
def test_patient_generation():
    """Patients are generated with appropriate attributes."""
    data_collection_period = 500
    model = make_model(data_collection_period=data_collection_period)
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

    # No patient is recorded with a call timestamp beyond run length
    assert all(
        p.call_timestamp <= data_collection_period for p in model.patients
    )


@pytest.mark.system
def test_completed_patients():
    """Patients who completed the full pathway have all time attributes."""
    # Use a long run so there is time for patients to complete
    model = make_model(data_collection_period=2000)
    model.run()

    # Check all time attributes are positive.
    for p in model.patients:
        if p.call_timestamp is not None:
            assert p.call_timestamp > 0
        if p.response_time is not None:
            assert p.response_time > 0

    # Check there is at least 1 patient with all time attributes i.e. complete
    completed = [p for p in model.patients if p.response_time is not None]
    assert len(completed) > 0


# -----------------------------------------------------------------------------
# Tests with very little or very high demand
# -----------------------------------------------------------------------------


@pytest.mark.system
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
        warm_up_period=0,
        data_collection_period=500,
    )
    model = Model(run_number=0, config=config)
    model.run()
    assert len(model.patients) > 0


@pytest.mark.system
def test_low_demand():
    """Model completes without error when calls are extremely rare."""
    # Very high inter-arrival time
    low_demand_data = {
        **AMBSYS_DATA,
        "mean_iat_min": {"C1": 1e6, "C2": 1e6, "C3": 1e6, "C4": 1e6},
    }
    config = SimConfig(
        ambsys_data=low_demand_data,
        warm_up_period=0,
        data_collection_period=500,
    )
    model = Model(run_number=0, config=config)
    model.run()
    assert len(model.patients) == 0


# -----------------------------------------------------------------------------
# Boundary value tests
# -----------------------------------------------------------------------------


@pytest.mark.system
def test_run_for_zero_minutes():
    """Raises ValueError if attempt to run with data_collection_period=0."""
    # SimPy itself should raise an error message
    with pytest.raises(
        ValueError, match="must be greater than the current simulation time"
    ):
        config = SimConfig(
            ambsys_data=AMBSYS_DATA, warm_up_period=0, data_collection_period=0
        )
        model = Model(run_number=0, config=config)
        model.run()


@pytest.mark.system
def test_on_scene_time_zero():
    """on_scene_time=0 is allowed and model still completes."""
    config = SimConfig(
        ambsys_data=AMBSYS_DATA,
        on_scene_time=0,
        warm_up_period=0,
        data_collection_period=500,
    )
    model = Model(run_number=0, config=config)
    model.run()
    assert len(model.patients) > 0


@pytest.mark.system
def test_wrap_up_time_zero():
    """wrap_up_time=0 is allowed and model still completes."""
    config = SimConfig(
        ambsys_data=AMBSYS_DATA,
        wrap_up_time=0,
        warm_up_period=0,
        data_collection_period=500,
    )
    model = Model(run_number=0, config=config)
    model.run()
    assert len(model.patients) > 0


# -----------------------------------------------------------------------------
# Reproducibility
# -----------------------------------------------------------------------------


@pytest.mark.system
def test_same_seed_same_results():
    """Two runs with the same run_number produce identical results."""
    m1 = make_model(run_number=42, data_collection_period=500)
    m2 = make_model(run_number=42, data_collection_period=500)
    m1.run()
    m2.run()
    assert len(m1.patients) == len(m2.patients)
    assert [p.call_timestamp for p in m1.patients] == [
        p.call_timestamp for p in m2.patients
    ]


@pytest.mark.system
def test_different_seeds_different_results():
    """Two runs with different run_numbers produce different results."""
    m1 = make_model(run_number=0, data_collection_period=500)
    m2 = make_model(run_number=1, data_collection_period=500)
    m1.run()
    m2.run()
    assert [p.call_timestamp for p in m1.patients] != [
        p.call_timestamp for p in m2.patients
    ]


# -----------------------------------------------------------------------------
# Warm-up
# -----------------------------------------------------------------------------

def test_warm_up():
    """Patient retained after run are only those generated after warm-up."""
    warm_up_period = 300
    data_collection_period = 400

    config = SimConfig(
        ambsys_data=AMBSYS_DATA,
        warm_up_period=warm_up_period,
        data_collection_period=data_collection_period,
    )
    model = Model(run_number=0, config=config)
    model.run()

    # Only post-warm-up patients should remain
    assert all(p.call_timestamp >= warm_up_period for p in model.patients)

    # Patient list is reset and ID is based on length of list, so the IDs
    # should restart from 1
    ids = [p.patient_id for p in model.patients]
    assert ids == list(range(1, len(ids) + 1))

    # Run ends at warm_up + data_collection
    assert model.env.now == warm_up_period + data_collection_period
