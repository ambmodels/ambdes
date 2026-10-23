"""Test resource variation."""

from types import SimpleNamespace

import pytest

from ambdes import CapacitySchedule, Model


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


# ---------------------------------------------------------------------------
# Fixed capacity model
# ---------------------------------------------------------------------------


def test_fixed_capacity_model_has_dispatcher(model):
    """A fixed-capacity model should still use the dispatcher."""
    assert model.ambulance.num_resources == 3
    assert model.ambulance_availability is None

    assert model.dispatcher.ambulance is model.ambulance
    assert model.dispatcher.permit is None
    assert model.dispatcher.queue == []


# ---------------------------------------------------------------------------
# Invalid and edge case inputs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "schedule, period, error",
    [
        ({}, 10, "must not be empty"),
        ({1: 1}, 10, "value at time 0"),
        ({0: 1}, None, "period.*provided"),
        ({0: 1, 10: 2}, 10, "greater than the last time"),
        ({0: 1, 10: 2}, 9, "greater than the last time"),
        ({0: -1}, 10, "must not be negative"),
    ],
)
def test_invalid_capacity_schedule(model, schedule, period, error):
    """Invalid schedules should be rejected."""
    with pytest.raises(ValueError, match=error):
        CapacitySchedule(
            env=model.env,
            resource=model.ambulance,
            schedule=schedule,
            period=period,
        )


@pytest.mark.parametrize(
    "ambulance_schedule, ambulance_schedule_period",
    [({0: 2}, 1000)],
    indirect=True,
)
@pytest.mark.parametrize("remove_target", [-1, 3])
def test_invalid_remove_target(model, remove_target):
    """Removal targets outside the resource range should be rejected."""
    process = model.env.process(
        model.ambulance_availability.apply_target(
            remove_target=remove_target,
            deadline=10,
        )
    )
    with pytest.raises(ValueError, match="remove_target must be between"):
        model.env.run(until=process)


@pytest.mark.parametrize(
    "ambulance_schedule, ambulance_schedule_period",
    [({60: 2, 0: 1}, 120)],
    indirect=True,
)
def test_unsorted_schedule_is_applied_in_time_order(model):
    """Schedule entries should be sorted before they are applied."""
    model.env.process(model.ambulance_availability.run())
    model.env.run(until=61)

    assert model.ambulance_availability.schedule == [(0, 1), (60, 2)]
    assert model.ambulance.num_resources == 2
    assert len(model.ambulance_availability.removed_units) == 0


# ---------------------------------------------------------------------------
# Other tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ambulance_schedule, ambulance_schedule_period",
    [({0: 3}, 1000)],
    indirect=True,
)
def test_partial_return_calls_callback_once(model):
    """Target update should notify once after all returns are complete."""
    callback_states = []
    availability = model.ambulance_availability

    def callback():
        """Record current state."""
        callback_states.append(
            {
                "removed": len(availability.removed_units),
                "capacity": model.ambulance.num_resources,
                "available": len(model.ambulance.items),
            }
        )

    # In the actual model, on_units_returned() will call
    # model.dispatcher.notify. In this test, we replace that notification with
    # a callback that records the state at the exact moment the callback runs
    availability.on_units_returned = callback

    # We start with 3 ambulances, then set target of 2 at time 0, target of
    # 1 at time 1, and target of 1 again at time 2
    def scenario():
        """Ambulance reduction scenario."""
        yield from availability.apply_target(remove_target=2, deadline=10)
        yield model.env.timeout(1)
        yield from availability.apply_target(remove_target=1, deadline=10)
        yield model.env.timeout(1)
        yield from availability.apply_target(remove_target=1, deadline=10)

    model.env.process(scenario())
    model.env.run()

    # The callback should only be triggered when capacity increases
    # So we check there is a single callback state, and it is when we went
    # from remove_target=2 to remove_target=1 (so from 1 to 2 capacity).
    assert callback_states == [{"removed": 1, "capacity": 2, "available": 2}]
    # There should just be one "returned" entry in the log
    assert [entry["action"] for entry in model.capacity_log].count(
        "returned"
    ) == 1


@pytest.mark.parametrize(
    "ambulance_schedule, ambulance_schedule_period",
    [({0: 2}, 1000)],
    indirect=True,
)
def test_no_callback_when_only_removing_or_target_unchanged(model):
    """Removal and no-op updates should not trigger the return callback."""
    callback_times = []
    availability = model.ambulance_availability

    # This callback records when it was called. It should be called when
    # units become available again
    availability.on_units_returned = lambda: callback_times.append(
        model.env.now
    )

    # The model starts with 2 ambulances. In this scenario, we have target to
    # remove 1, then same target again (i.e., no change)
    def scenario():
        yield from availability.apply_target(remove_target=1, deadline=10)
        yield model.env.timeout(1)
        yield from availability.apply_target(remove_target=1, deadline=10)

    model.env.process(scenario())
    model.env.run()

    # There were no returns to the pool, so there should be no callbacks
    assert callback_times == []


@pytest.mark.parametrize(
    "ambulance_schedule, ambulance_schedule_period",
    [({0: 2}, 1000)],
    indirect=True,
)
def test_changes_work_when_logging_and_callback_are_disabled(model):
    """Capacity changes should not require logging or a callback."""
    # Create a schedule with record_changes=False and on_units_returned=None
    availability = CapacitySchedule(
        env=model.env,
        resource=model.ambulance,
        schedule={0: 2},
        period=1000,
        record_changes=False,
        on_units_returned=None,
    )

    # Remove and then return one unit
    def scenario():
        yield from availability.apply_target(remove_target=1, deadline=10)
        yield from availability.apply_target(remove_target=0, deadline=10)

    model.env.process(scenario())
    model.env.run()

    # Check that there was no logging, but ambulance still returned
    # successfully and internal counts remain consistent
    assert availability.capacity_log is None
    assert availability.removed_units == []
    availability.assert_resource_invariants()


@pytest.mark.parametrize(
    "ambulance_schedule, ambulance_schedule_period",
    [({0: 2, 5: 0, 10: 2}, 20)],
    indirect=True,
)
def test_expired_removal_does_not_consume_later_return(model):
    """A removal request must not survive beyond its schedule interval."""

    # At time 5, the schedule tries to remove both ambulances, but both are
    # deliberately made busy until time 12
    def occupy_all_ambulances():
        requests = [
            model.ambulance.get_direct(auto_log=False) for _ in range(2)
        ]
        ambulances = yield model.env.all_of(requests)
        yield model.env.timeout(12)
        for request in requests:
            model.ambulance.put(ambulances[request], auto_log=False)

    model.env.process(occupy_all_ambulances())
    model.env.process(model.ambulance_availability.run())
    model.env.run(until=13)

    # Confirm that at time 13 both ambulances are in the pool and idle
    assert model.ambulance_availability.removed_units == []
    assert model.ambulance.num_resources == 2
    assert len(model.ambulance.items) == 2
    # Check no ambulance has been lost or double counted
    model.ambulance_availability.assert_resource_invariants()


@pytest.mark.parametrize(
    "ambulance_schedule, ambulance_schedule_period",
    [({0: 1}, 1000)],
    indirect=True,
)
def test_resource_released_at_deadline_stays_operational(model):
    """A release at the deadline must not lose the resource."""
    original_ids = {
        ambulance.unique_id_attribute for ambulance in model.ambulance.items
    }

    # There is one ambulance and we create a patient that occupies it for
    # exactly 10 minutes
    def occupy_ambulance():
        with model.ambulance.request(
            priority=1,
            entity_id=999,
            start_event="ambulance_assigned",
            end_event="ambulance_available",
        ) as request:
            yield request
            yield model.env.timeout(10)

    model.env.process(occupy_ambulance())

    # At the same time, the schedule attempts to remove it by 10
    model.env.process(
        model.ambulance_availability.apply_target(
            remove_target=1,
            deadline=10,
        )
    )
    model.env.run(until=11)

    # Check the IDs to be sure that every original ambulance still exists,
    # no ambulance exists in both places, none disappeared and none were
    # duplicated. At time 10, we expect our ambulance_1 to be in items.
    available_ids = {
        ambulance.unique_id_attribute for ambulance in model.ambulance.items
    }
    removed_ids = {
        ambulance.unique_id_attribute
        for ambulance in model.ambulance_availability.removed_units
    }
    assert available_ids | removed_ids == original_ids
    assert available_ids.isdisjoint(removed_ids)

    # At simulation time 10, two things happen:
    # 1. The patient releases the ambulance back to the store
    # 2. The removal deadline occurs
    # We expect that a unit that becomes available at the deadline should
    # remain operational, because the removal window has ended
    assert model.ambulance_availability.removed_units == []
    assert model.ambulance.num_resources == 1
    assert len(model.ambulance.items) == 1
    model.ambulance_availability.assert_resource_invariants()
