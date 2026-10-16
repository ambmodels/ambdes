"""Dispatch patients to available ambulance resources."""

from dataclasses import dataclass

import simpy

from .patient import Patient


@dataclass
class DispatchRequest:
    """A patient waiting for ambulance resources.

    Attributes
    ----------
    patient : Patient
        Patient waiting for resources.
    order : int
        Order in which the patient joined the dispatch queue.
    allocated : simpy.events.Event
        Event triggered when the required resources have been allocated.

    """

    patient: Patient
    order: int
    allocated: simpy.events.Event


class Dispatcher:
    """Allocate ambulances and permits to waiting patients.

    Patients are ordered first by clinical priority and then by the order
    in which they joined the dispatch queue. When restricted send is active,
    C2-C4 patients require both an ambulance and a permit. C1 patients require
    only an ambulance.

    We have created this dispatcher class to enable us to only allocate if
    both an ambulance AND a permit are available at the same time, instead of
    assigning one and then the other.
    """

    def __init__(self, env, ambulance, permit=None):
        """Initialise the dispatcher.

        Parameters
        ----------
        env : simpy.Environment
            SimPy environment.
        ambulance : VidigiPriorityStore
            Pool of available ambulance resources.
        permit : VidigiPriorityStore | None
            Pool of permits allowing ambulances to attend C2-C4 incidents. If
            None, restricted send is not active.

        """
        self.env = env
        self.ambulance = ambulance
        self.permit = permit

        # Patients waiting for resources
        self.queue = []
        self.request_counter = 0

        # Messages telling the dispatcher to check the queue
        self.notifications = simpy.Store(self.env)

    def notify(self):
        """Notify the dispatcher that the model state has changed."""
        # The value carries no information. It simply tells run() to check the
        # queue and currently available resources again
        self.notifications.put(None)

    def run(self):
        """Allocate resources to the highest-priority eligible patient."""
        while True:
            # Wait until the model state changes (a patient joins the queue
            # or resources are returned)
            yield self.notifications.get()

            # Dispatch as many patients are the current resources allow
            while self.queue and self.ambulance.items:
                request = self.get_next_dispatchable_request()

                # If patients are waiting, but none are currently eligible
                if request is None:
                    break

                # Check if the patient needed a permit
                needs_permit = (
                    request.patient.category != "C1"
                    and self.permit is not None
                )

                # Reserve all required resources before yielding. This stops
                # another dispatch iteration from allocating the same resource
                ambulance_get = self.ambulance.get_direct(
                    entity_id=request.patient.patient_id,
                    event="ambulance_assigned",
                )
                if needs_permit:
                    permit_get = self.permit.get_direct(auto_log=False)
                else:
                    permit_get = None

                # Remove that patient from the dispatch queue
                self.queue.remove(request)

                # Collect the reserved resources
                ambulance = yield ambulance_get
                if needs_permit:
                    permit = yield permit_get
                else:
                    permit = None

                # Give the resources to the waiting patient process
                request.allocated.succeed((ambulance, permit))

    def get_next_dispatchable_request(self):
        """Return highest-priority patient whose resources are available.

        Returns
        -------
        DispatchRequest | None
            Highest-priority request for which all required resources are
            available, or None if no waiting patient can currently be sent.

        """
        # Create a new sorted list of patients waiting in self.dispatch_queue.
        # It gets the priority and arrival order for each patient then sorts.
        waiting_requests = sorted(
            self.queue,
            key=lambda request: (
                request.patient.priority,
                request.order,
            ),
        )

        # Looks through the sorted requests...
        for request in waiting_requests:
            patient = request.patient

            # If the patient is C1 or if restricted send is not enabled, then
            # everyone can be sent as soon as an ambulance is available
            if patient.category == "C1" or self.permit is None:
                return request

            # If at least one permit is free, return this C2-C4 patient to
            # be dispatched
            if self.permit.items:
                return request

        return None

    def request_resources(self, patient):
        """Add a patient to the dispatch queue.

        Parameters
        ----------
        patient : Patient
            Patient requiring an ambulance response.

        Returns
        -------
        simpy.events.Event
            Event that succeeds with an `(ambulance, permit)` tuple once the
            required resources have been allocated. The permit is None when
            no permit is required.

        """
        # Get a queue number for the central dispatch queue
        self.request_counter += 1

        request = DispatchRequest(
            patient=patient,
            order=self.request_counter,
            # The event will occur when the patient has been allocated
            # their resources
            allocated=self.env.event(),
        )

        self.queue.append(request)
        self.notify()

        return request.allocated

    def return_resources(self, ambulance, permit, patient_id):
        """Return resources after an ambulance response.

        Parameters
        ----------
        ambulance : VidigiResource
            Ambulance to return to the resource pool.
        permit : VidigiResource | None
            Restricted send permit to return, or None if no permit was used.
        patient_id : id
            Identified of the patient whose response has finished.

        """
        # Return the ambulance
        self.ambulance.put(
            ambulance,
            entity_id=patient_id,
            event="ambulance_available",
        )

        # Return the permit, if one was required
        if permit is not None:
            self.permit.put(permit, auto_log=False)

        # Notify the dispatcher, as returning resources may allow another
        # patient to be sent
        self.notify()
