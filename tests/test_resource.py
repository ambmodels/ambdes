"""Test resource variation."""

from types import SimpleNamespace

import pytest

from ambdes import Model


@pytest.fixture
def model(monkeypatch):
    """Simplified Model."""
    # Don't run create_batch - just return dict as is
    monkeypatch.setattr(
        "ambdes.model.DistributionRegistry.create_batch",
        lambda *args, **kwargs: {},
    )
    # Create an object that can replace config in Model, which contains fields
    # that Model accesses during construction and when run.
    config = SimpleNamespace(
        n_ambulances=3,
        capacity_interval=None,
        warm_up_period=0,
        data_collection_period=100,
        dist_config={},
    )
    # Return initialised model
    return Model(run_number=0, config=config)


# ---------------------------------------------------------------------------
# Simple resource addition / removal
# ---------------------------------------------------------------------------

def test_remove_idle_ambulances(model):
    """Check idle ambulances are removed immediately."""
    # Run apply_capacity_update
    model.env.process(
        model.apply_capacity_update(
            remove_target=2,
            deadline=10
        ),
    )
    model.env.run()

    # Removed resources
    assert len(model.removed_units) == 2
    # Available resources
    assert model.ambulance.num_resources == 1
    assert model.ambulance._n_pool_units == 1
    assert len(model.ambulance.items) == 1
    # Busy resources
    assert model.ambulance.count == 0

    # Check the capacity log
    expected_log = [
        {
            "time": 0.0,
            "action": "initial",
            "resource_id": None,
            "remove_target": 0,
            "removed": 0,
            "capacity": 3,
        },
        {
            "time": 0.0,
            "action": "removed",
            "resource_id": "ambulance_1",
            "remove_target": 2,
            "removed": 1,
            "capacity": 2,
        },
        {
            "time": 0.0,
            "action": "removed",
            "resource_id": "ambulance_2",
            "remove_target": 2,
            "removed": 2,
            "capacity": 1,
        },
    ]
    for actual, expected in zip(model.capacity_log, expected_log, strict=True):
        assert actual == expected


def test_remove_and_return_idle_ambulances(model):
    """Check idle ambulances are removed and returned as expected."""
    def scenario():
        yield from model.apply_capacity_update(
            remove_target=2,
            deadline=10,
        )

        yield model.env.timeout(5)

        yield from model.apply_capacity_update(
            remove_target=0,
            deadline=15,
        )

        yield model.env.timeout(20)

    model.env.process(scenario())
    model.env.run()

    # As first apply_capacity_update with schedule timeout()
    assert model.env.now == 25
    # Removed resources
    assert len(model.removed_units) == 0
    # Available resources
    assert model.ambulance.num_resources == 3
    assert model.ambulance._n_pool_units == 3
    assert len(model.ambulance.items) == 3
    # Busy resources
    assert model.ambulance.count == 0

    # Check the capacity log
    expected_log = [
        {
            "time": 0.0,
            "action": "initial",
            "resource_id": None,
            "remove_target": 0,
            "removed": 0,
            "capacity": 3,
        },
        {
            "time": 0.0,
            "action": "removed",
            "resource_id": "ambulance_1",
            "remove_target": 2,
            "removed": 1,
            "capacity": 2,
        },
        {
            "time": 0.0,
            "action": "removed",
            "resource_id": "ambulance_2",
            "remove_target": 2,
            "removed": 2,
            "capacity": 1,
        },
        {
            "time": 5.0,
            "action": "returned",
            "resource_id": "ambulance_2",
            "remove_target": 0,
            "removed": 1,
            "capacity": 2,
        },
        {
            "time": 5.0,
            "action": "returned",
            "resource_id": "ambulance_1",
            "remove_target": 0,
            "removed": 0,
            "capacity": 3,
        },
    ]
    for actual, expected in zip(model.capacity_log, expected_log, strict=True):
        assert actual == expected
