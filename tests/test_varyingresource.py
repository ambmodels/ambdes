"""Test resource variation."""

from types import SimpleNamespace

import pytest

from ambdes import Model


@pytest.fixture
def n_ambulances(request):
    """Ambulances for the test model."""
    return getattr(request, "param", 3)


@pytest.fixture
def ambulance_schedule(request):
    """Ambulance schedule for a varying-capacity test model."""
    return getattr(request, "param", None)


@pytest.fixture
def ambulance_schedule_period(request):
    """Period over which the ambulance schedule repeats."""
    return getattr(request, "param", None)


@pytest.fixture
def model(
    n_ambulances, ambulance_schedule, ambulance_schedule_period, monkeypatch
):
    """Simplified Model."""
    # Don't run create_batch - just return dict as is
    monkeypatch.setattr(
        "ambdes.model.DistributionRegistry.create_batch",
        lambda *args, **kwargs: {},
    )
    # Create an object that can replace config in Model, which contains fields
    # that Model accesses during construction and when run.
    config = SimpleNamespace(
        n_ambulances=(n_ambulances if ambulance_schedule is None else None),
        ambulance_schedule=ambulance_schedule,
        ambulance_schedule_period=ambulance_schedule_period,
        warm_up_period=0,
        data_collection_period=100,
        dist_config={},
        permit_schedule=None,
    )
    # Return initialised model
    return Model(run_number=0, config=config)


# ---------------------------------------------------------------------------
# Simple resource addition / removal tests for apply_target()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ambulance_schedule, ambulance_schedule_period",
    [({0: 3}, 1000)],
    indirect=True,
)
def test_remove_idle_ambulances(model):
    """Check idle ambulances are removed immediately."""
    # Run apply_target
    model.env.process(
        model.ambulance_availability.apply_target(
            remove_target=2,
            deadline=10,
        )
    )
    model.env.run()

    # Removed resources
    assert len(model.ambulance_availability.removed_units) == 2
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


@pytest.mark.parametrize(
    "ambulance_schedule, ambulance_schedule_period",
    [({0: 3}, 1000)],
    indirect=True,
)
def test_remove_and_return_idle_ambulances(model):
    """Check idle ambulances are removed and returned as expected."""

    def scenario():
        yield from model.ambulance_availability.apply_target(
            remove_target=2,
            deadline=10,
        )

        yield model.env.timeout(5)

        yield from model.ambulance_availability.apply_target(
            remove_target=0,
            deadline=15,
        )

        yield model.env.timeout(20)

    model.env.process(scenario())
    model.env.run()

    assert model.env.now == 25
    # Removed resources
    assert len(model.ambulance_availability.removed_units) == 0
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
# Busy resource removal test for apply_target()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ambulance_schedule, ambulance_schedule_period",
    [({0: 2}, 1000)],
    indirect=True,
)
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
        model.ambulance_availability.apply_target(
            remove_target=2,
            deadline=10,
        ),
    )

    model.env.run()

    # Removed resources
    assert len(model.ambulance_availability.removed_units) == 2
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
# Deadline test for apply_target()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ambulance_schedule, ambulance_schedule_period",
    [({0: 2}, 1000)],
    indirect=True,
)
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
        model.ambulance_availability.apply_target(
            remove_target=2,
            deadline=10,
        ),
    )

    model.env.run(until=25)

    # Removed resources
    assert len(model.ambulance_availability.removed_units) == 1
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
# Test of CapacitySchedule.run() (which calls apply_target)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ambulance_schedule, ambulance_schedule_period",
    [
        ({0: 1, 60: 3}, 120),
    ],
    indirect=True,
)
def test_capacity_changes_between_intervals(model):
    """Test capacity changes using interval and run."""
    # With 1-hour capacity interval, first remove two ambulances, then return
    model.env.process(model.ambulance_availability.run())
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


@pytest.mark.parametrize(
    "ambulance_schedule, ambulance_schedule_period",
    [
        ({0: 1, 60: 3}, 120),
    ],
    indirect=True,
)
def test_capacity_schedule_repeats(model):
    """Check the ambulance schedule repeats after its period."""
    model.env.process(model.ambulance_availability.run())
    model.env.run(until=121)

    changes_at_120 = [
        entry for entry in model.capacity_log if entry["time"] == 120.0
    ]

    assert len(changes_at_120) == 2
    assert changes_at_120[-1]["remove_target"] == 2
    assert changes_at_120[-1]["removed"] == 2
    assert changes_at_120[-1]["capacity"] == 1
