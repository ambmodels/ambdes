"""Test resource variation."""

from types import SimpleNamespace

import pytest

from ambdes import Model


@pytest.fixture
def n_ambulances(request):
    """Ambulances for the test model."""
    return getattr(request, "param", 3)


@pytest.fixture
def capacity_interval(request):
    """Capacity interval for the test model."""
    return getattr(request, "param", None)


@pytest.fixture
def model(n_ambulances, capacity_interval, monkeypatch):
    """Simplified Model."""
    # Don't run create_batch - just return dict as is
    monkeypatch.setattr(
        "ambdes.model.DistributionRegistry.create_batch",
        lambda *args, **kwargs: {},
    )
    # Create an object that can replace config in Model, which contains fields
    # that Model accesses during construction and when run.
    config = SimpleNamespace(
        n_ambulances=n_ambulances,
        capacity_interval=capacity_interval,
        warm_up_period=0,
        data_collection_period=100,
        dist_config={},
    )
    # Return initialised model
    return Model(run_number=0, config=config)


class SequenceDistribution:
    """Simple fake distribution."""

    def __init__(self, values):
        """Build iterator object for values."""
        self.values = iter(values)

    def sample(self, **kwargs):
        """Return next item from values."""
        return next(self.values)


# ---------------------------------------------------------------------------
# Simple resource addition / removal tests for apply_capacity_update()
# ---------------------------------------------------------------------------


def test_remove_idle_ambulances(model):
    """Check idle ambulances are removed immediately."""
    # Run apply_capacity_update
    model.env.process(
        model.apply_capacity_update(remove_target=2, deadline=10),
    )
    model.env.run()

    # Removed resources
    assert len(model.removed_units) == 2
    # Capacity (busy + available ambulances)
    assert model.ambulance.num_resources == 1
    # Available resources
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
    assert model.capacity_log == expected_log


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

    assert model.env.now == 25
    # Removed resources
    assert len(model.removed_units) == 0
    # Capacity (busy + available ambulances)
    assert model.ambulance.num_resources == 3
    # Available resources
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
    assert model.capacity_log == expected_log


# ---------------------------------------------------------------------------
# Busy resource removal test for apply_capacity_update()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n_ambulances", [2], indirect=True)
def test_wait_before_remove_busy_ambulance(model):
    """Busy ambulance should only be removed once finished with patient."""

    def occupy_ambulance():
        with model.ambulance.request(
            priority=1,
            entity_id=999,
            start_event="ambulance_assigned",
            end_event="ambulance_available",
        ) as req:
            yield req
            yield model.env.timeout(5)

    model.env.process(occupy_ambulance())

    model.env.process(
        model.apply_capacity_update(remove_target=2, deadline=10),
    )

    model.env.run()

    # Removed resources
    assert len(model.removed_units) == 2
    # Capacity (busy + available ambulances)
    assert model.ambulance.num_resources == 0
    # Available resources
    assert len(model.ambulance.items) == 0
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
            "capacity": 2,
        },
        {
            "time": 0.0,
            "action": "removed",
            "resource_id": "ambulance_2",
            "remove_target": 2,
            "removed": 1,
            "capacity": 1,
        },
        {
            "time": 5.0,
            "action": "removed",
            "resource_id": "ambulance_1",
            "remove_target": 2,
            "removed": 2,
            "capacity": 0,
        },
    ]
    assert model.capacity_log == expected_log


# ---------------------------------------------------------------------------
# Deadline test for apply_capacity_update()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n_ambulances", [2], indirect=True)
def test_not_remove_after_deadline(model):
    """If ambulance still busy after deadline, don't remove later."""

    def occupy_ambulance():
        with model.ambulance.request(
            priority=1,
            entity_id=999,
            start_event="ambulance_assigned",
            end_event="ambulance_available",
        ) as req:
            yield req
            yield model.env.timeout(20)

    model.env.process(occupy_ambulance())

    model.env.process(
        model.apply_capacity_update(remove_target=2, deadline=10),
    )

    model.env.run(until=25)

    # Removed resources
    assert len(model.removed_units) == 1
    # Capacity (busy + available ambulances)
    assert model.ambulance.num_resources == 1
    # Available ambulances
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
            "capacity": 2,
        },
        {
            "time": 0.0,
            "action": "removed",
            "resource_id": "ambulance_2",
            "remove_target": 2,
            "removed": 1,
            "capacity": 1,
        },
    ]
    assert model.capacity_log == expected_log


# ---------------------------------------------------------------------------
# Test of update_operational_capacity (which calls apply_capacity_update)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("capacity_interval", [60], indirect=True)
def test_capacity_changes_between_intervals(model):
    """Test capacity changes using interval and update_operational_capacity."""
    # With 1-hour capacity interval, first remove two ambulances, then return
    model.dists = {
        "reduce_daily_hours": SequenceDistribution([2, 0]),
    }
    model.env.process(model.update_operational_capacity())
    model.env.run(until=61)

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
            "time": 60.0,
            "action": "returned",
            "resource_id": "ambulance_2",
            "remove_target": 0,
            "removed": 1,
            "capacity": 2,
        },
        {
            "time": 60.0,
            "action": "returned",
            "resource_id": "ambulance_1",
            "remove_target": 0,
            "removed": 0,
            "capacity": 3,
        },
    ]
    assert model.capacity_log == expected_log
