"""Test restricted send."""

from types import SimpleNamespace

import pytest

from ambdes import Model, Patient

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


@pytest.fixture
def model(monkeypatch):
    """Model with one ambulance and one C2-C4 permit."""
    # Don't run create_batch - just return dict as is
    monkeypatch.setattr(
        "ambdes.model.DistributionRegistry.create_batch",
        lambda *args, **kwargs: {},
    )
    # Create an object that can replace config in Model, which contains fields
    # that Model accesses during construction and when run.
    config = SimpleNamespace(
        n_ambulances=1,
        ambulance_schedule=None,
        ambulance_schedule_period=100,
        permit_schedule={0: 1},
        warm_up_period=0,
        data_collection_period=100,
        dist_config={},
    )

    model = Model(run_number=0, config=config)

    # Start the central dispatcher
    model.env.process(model.dispatch_patients())

    return model


def add_to_dispatch_queue(model, category, order):
    """Add a patient directly to the dispatch queue.

    This skips the usual steps (patient calls → waits for connect-to-queue
    time → joins dispatch queue) and instead just immediately puts the patient
    in the queue.

    Parameters
    ----------
    model : Model
        Test model.
    category : str
        Patient category ("C1", "C2", "C3" or "C4").
    order : int
        The order this patient joined the dispatch queue.

    """
    # Create a patient
    patient = Patient(
        patient_id=order,
        category=category,
        outcome="see_and_treat",
        call_timestamp=model.env.now,
    )
    # Create the dictionary that the dispatcher expects to find in
    # model.dispatch_queue. It contains all the information the dispatcher
    # needs. The blank SimPy event will be triggered later once allocated all
    # requirements
    dispatch_request = {
        "patient": patient,
        "order": order,
        "allocated": model.env.event(),
    }

    # Add the request to the model's waiting list. This is the same queue that
    # request_ambulance() would normally add patients to
    model.dispatch_queue.append(dispatch_request)

    return dispatch_request


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_c1_does_not_need_permit(model):
    """C1 should receive an ambulance when no permit is available."""
    # Remove the only permit from the available pool
    model.env.run(until=model.permit.get_direct(auto_log=False))

    request = add_to_dispatch_queue(
        model=model,
        category="C1",
        order=1,
    )

    model.notify_dispatcher()
    model.env.run()

    # C1 was allocated an ambulance and not a permit
    assert request["allocated"].triggered
    ambulance, permit = request["allocated"].value
    assert ambulance is not None
    assert permit is None

    # The patient is no longer in the queue
    assert request not in model.dispatch_queue

    # There are no ambulances available
    assert len(model.ambulance.items) == 0


@pytest.mark.parametrize("category", ["C2", "C3", "C4"])
def test_nonc1_waits_without_permit(model, category):
    """C2, C3 or C4 should wait if not permit is available."""
    # Remove the only permit from the available pool
    model.env.run(until=model.permit.get_direct(auto_log=False))

    request = add_to_dispatch_queue(
        model=model,
        category=category,
        order=1,
    )

    model.notify_dispatcher()
    model.env.run()

    # C2 was not allocated an ambulance or permit
    assert not request["allocated"].triggered

    # Patient remains in queue
    assert request in model.dispatch_queue

    # There is still an ambulance available
    assert len(model.ambulance.items) == 1


@pytest.mark.parametrize("category", ["C2", "C3", "C4"])
def test_nonc1_receives_both(model, category):
    """C2, C3 or C4 should receive an ambulance and a permit."""
    request = add_to_dispatch_queue(model=model, category=category, order=1)

    model.notify_dispatcher()
    model.env.run()

    # C2 was allocated an ambulance and permit
    assert request["allocated"].triggered
    ambulance, permit = request["allocated"].value
    assert ambulance is not None
    assert permit is not None

    # Patient is no longer in queue
    assert request not in model.dispatch_queue

    # There are no ambulances or permits available
    assert len(model.ambulance.items) == 0
    assert len(model.permit.items) == 0


def test_higher_priority_goes_first(model):
    """A later C2 should be dispatched before an earlier C4."""
    c4_request = add_to_dispatch_queue(model=model, category="C4", order=1)
    c2_request = add_to_dispatch_queue(model=model, category="C2", order=2)

    model.notify_dispatcher()
    model.env.run()

    # C2 was allocated an ambulance and permit and is no longer in the queue
    assert c2_request["allocated"].triggered
    c2_ambulance, c2_permit = c2_request["allocated"].value
    assert c2_ambulance is not None
    assert c2_permit is not None

    # C4 was not allocated anything and is still in the queue
    assert not c4_request["allocated"].triggered
    assert c4_request in model.dispatch_queue

    # There are no ambulances or permits available
    assert len(model.ambulance.items) == 0
    assert len(model.permit.items) == 0


def test_patient_does_not_hold_permit_while_waiting(model):
    """Patient should not take a permit while no ambulance is available."""
    # Remove the only ambulance
    ambulance = model.env.run(until=model.ambulance.get_direct(auto_log=False))

    c4_request = add_to_dispatch_queue(model=model, category="C4", order=1)

    model.notify_dispatcher()
    model.env.run()

    # C4 cannot be dispatched without an ambulance and has not taken permit
    assert not c4_request["allocated"].triggered
    assert len(model.permit.items) == 1

    c2_request = add_to_dispatch_queue(model=model, category="C2", order=2)

    # Add the ambulance again
    model.ambulance.put(ambulance, auto_log=False)
    model.notify_dispatcher()
    model.env.run()

    # C2 receives the ambulance and permit
    assert c2_request["allocated"].triggered
    c2_ambulance, c2_permit = c2_request["allocated"].value
    assert c2_ambulance is not None
    assert c2_permit is not None

    # C4 was not allocated anything and is still in the queue
    assert not c4_request["allocated"].triggered
    assert c4_request in model.dispatch_queue

    # There are no ambulances or permits available
    assert len(model.ambulance.items) == 0
    assert len(model.permit.items) == 0
