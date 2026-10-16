"""Core simulation model.

Defines the Model class with all simulation logic for a single run. Handles
SimPy processes and records Patient instances, but does not format results or
manage replications.
"""

import simpy
from sim_tools.distributions import DistributionRegistry
from vidigi.logging import EventLogger
from vidigi.resources import VidigiPriorityStore

from .capacity import CapacitySchedule
from .patient import Patient


class Model:
    """Discrete-event simulation model for ambulance responses.

    The model generates patient calls, allocates ambulance resources and
    records patients during a single simulation run.
    """

    def __init__(self, run_number, config):
        """Initialise the simulation model.

        Parameters
        ----------
        run_number : int
            Simulation run identifier.
        config : object
            Configuration object containing model parameters.

        """
        self.run_number = run_number
        self.config = config

        # Create SimPy environment
        self.env = simpy.Environment()

        # Set up logger
        self.logger = EventLogger(env=self.env, run_number=self.run_number)

        # Initialise distributions, with random seed based on run number
        self.dists = DistributionRegistry.create_batch(
            self.config.dist_config,
            main_seed=self.run_number,
            sort=True,
            preserve_structure=True,
        )

        # Set up attribute to store results
        # Patient ID counter is independent of self.patients to ensure
        # patients in warm-up and data collection period each have unique ID
        self.patients = []
        self.patient_id_counter = 0

        # Patients waiting for resources
        self.dispatch_queue = []
        self.dispatch_counter = 0

        # Messages telling the dispatcher to check the queue.
        self.dispatch_notifications = simpy.Store(self.env)

        # Calculate maximum possible number of ambulances
        if self.config.ambulance_schedule is None:
            self.max_n_ambulances = self.config.n_ambulances
        else:
            self.max_n_ambulances = max(
                self.config.ambulance_schedule.values()
            )

        # Set up ambulance resource
        self.ambulance = VidigiPriorityStore(
            self.env,
            num_resources=self.max_n_ambulances,
            label="ambulance",
            logger=self.logger,
        )

        # Manage varying ambulance availability when a schedule is supplied
        if self.config.ambulance_schedule is not None:
            self.ambulance_availability = CapacitySchedule(
                env=self.env,
                resource=self.ambulance,
                schedule=self.config.ambulance_schedule,
                period=self.config.ambulance_schedule_period,
                record_changes=True,
                on_units_returned=self.notify_dispatcher,
            )
            self.capacity_log = self.ambulance_availability.capacity_log
        # If no variation in availability, set ambulance_availability to None
        # and create one simple entry for capacity log, used to allow
        # consistent approach in calculations in results code
        else:
            self.ambulance_availability = None
            self.capacity_log = [
                {
                    "time": 0.0,
                    "action": "initial",
                    "resource_id": None,
                    "remove_target": 0,
                    "removed": 0,
                    "capacity": self.max_n_ambulances,
                }
            ]

        # Set-up the permit pool (indicating vehicles permitted to attend
        # C2-C4 incidents - i.e., excluding those in restricted send) in a
        # similar way to our set-up for ambulance resources, with support
        # for varying the permits over time. However, we deliberately don't
        # log, as permits are just used as a modelling constraints and don't
        # represent actual ambulance use
        if self.config.permit_schedule is not None:
            self.max_n_permits = max(self.config.permit_schedule.values())
            self.permit = VidigiPriorityStore(
                self.env,
                num_resources=self.max_n_permits,
                label="c2_to_c4_permit",
            )
        else:
            self.max_n_permits = None
            self.permit = None

        # Manage varying restriction of ambulances to C1 calls only, with a
        # "permit" schedule showing the number of ambulances available for
        # all call types at any given time (and excluding the ambulances
        # who are restricted to C1 only)
        if self.config.permit_schedule is not None:
            self.permit_availability = CapacitySchedule(
                env=self.env,
                resource=self.permit,
                schedule=self.config.permit_schedule,
                period=self.config.ambulance_schedule_period,
                on_units_returned=self.notify_dispatcher,
            )
        else:
            self.permit_availability = None

    def generate_patients(self):
        """Generate patients."""
        while True:
            # Sample and pass time to next call
            iat = self.dists["call_arrival"].sample(
                simulation_time=self.env.now
            )
            yield self.env.timeout(iat)

            # Sample call type
            category = self.dists["call_category"].sample()

            # Sample whether patient is conveyed or not
            outcome = self.dists["call_outcome"][category].sample()

            # Create a new patient
            self.patient_id_counter += 1
            patient = Patient(
                patient_id=self.patient_id_counter,
                category=category,
                outcome=outcome,
                call_timestamp=self.env.now,
            )
            self.patients.append(patient)

            # Log call time
            self.logger.log_arrival(entity_id=patient.patient_id)

            # Start process of requesting an ambulance
            self.env.process(self.request_ambulance(patient))

    def request_ambulance(self, patient):
        """Join the dispatch queue and wait for the required resources.

        First samples the time from call receipt to joining the dispatch queue.

        Without restricted send, all patients wait only for an ambulance.

        With restricted send:
        - C1 patients wait only for an ambulance.
        - C2-C4 patients wait for a permit and then an ambulance.

        Parameters
        ----------
        patient : Patient
            Patient requiring an ambulance response.

        """
        # Sample time from call connection to decision for call to be
        # added to stack for response (i.e., joining queue for resource)
        connect_to_queue_time = self.dists["connect_to_queue_time"][
            patient.category
        ].sample()

        yield self.env.timeout(connect_to_queue_time)

        # Log start time of wait for allocation
        self.logger.log_queue(
            entity_id=patient.patient_id, event="ambulance_wait_begins"
        )

        # Get a queue number for the central dispatch queue
        self.dispatch_counter += 1
        dispatch_request = {
            "patient": patient,
            "order": self.dispatch_counter,
            # The event will occur when the patient has been allocated
            # their resources
            "allocated": self.env.event(),
        }
        self.dispatch_queue.append(dispatch_request)
        self.notify_dispatcher()

        # Wait until all required resources have been allocated
        ambulance, permit = yield dispatch_request["allocated"]

        yield from self.use_ambulance(
            patient=patient,
            ambulance=ambulance,
            permit=permit,
        )

    def dispatch_patients(self):
        """Allocate resources to the highest-priority eligible patient."""
        while True:
            # Wait until the model state changes
            yield self.dispatch_notifications.get()

            # Dispatch as many patients as currently possible.
            while self.dispatch_queue and self.ambulance.items:
                request = self.get_next_dispatchable_request()

                # Patients are waiting, but none can currently be sent
                if request is None:
                    break

                patient = request["patient"]

                needs_permit = (
                    patient.category != "C1" and self.permit is not None
                )

                # Reserve everything before yielding
                ambulance_get = self.ambulance.get_direct(
                    entity_id=patient.patient_id, event="ambulance_assigned"
                )
                permit_get = None
                if needs_permit:
                    permit_get = self.permit.get_direct(auto_log=False)

                self.dispatch_queue.remove(request)

                # Collecte the reserved resources
                ambulance = yield ambulance_get
                permit = None
                if permit_get is not None:
                    permit = yield permit_get

                # Give the resources to the waiting patient process
                request["allocated"].succeed((ambulance, permit))

    def notify_dispatcher(self):
        """Tell the dispatcher that the model state has changed."""
        # None carries no information - it just triggers it to check the
        # dispatch queue again
        self.dispatch_notifications.put(None)

    def get_next_dispatchable_request(self):
        """Return highest-priority patient whose resources are available."""
        # Create a new sorted list of patients waiting in self.dispatch_queue.
        # It gets the priority and arrival order for each patient then sorts.
        waiting_requests = sorted(
            self.dispatch_queue,
            key=lambda request: (
                request["patient"].priority,
                request["order"],
            ),
        )

        # Looks through the sorted requests...
        for request in waiting_requests:
            patient = request["patient"]

            # If the patient is C1 or if restricted send is not enabled, then
            # everyone can be sent as soon as an ambulance is available
            if patient.category == "C1" or self.permit is None:
                return request

            # If at least one permit is free, return this C2-C4 patient to
            # be dispatched
            if self.permit.items:
                return request

        return None

    def use_ambulance(self, patient, ambulance, permit):
        """Simulate an ambulance response for a patient.

        Parameters
        ----------
        patient : Patient
            Patient receiving an ambulance response.
        ambulance : VidigiResource
            Ambulance allocated by the dispatcher.
        permit : VidigiResoure or None
            Permit allocated by the dispatcher for C2-C4 patient under
            restricted send conditions, or None if no permit was required.

        """
        # Record when patient was assigned an ambulance. This is their
        # allocation time - time from call receipt to resource allocation.
        patient.allocation_time = self.env.now - patient.call_timestamp

        # Sample mobilisation time
        mobilisation_time = self.dists["mobilisation_time"][
            patient.category
        ].sample()
        yield self.env.timeout(mobilisation_time)

        # Sample travel to scene
        time_to_scene = self.dists["time_to_scene"][patient.category].sample()
        yield self.env.timeout(time_to_scene)

        # Record response time
        patient.response_time = self.env.now - patient.call_timestamp

        # On-scene time
        on_scene_time = self.dists["on_scene_time"][patient.category][
            patient.outcome
        ].sample()
        yield self.env.timeout(on_scene_time)

        if patient.outcome == "see_and_convey":
            # Sample travel to hospital
            time_to_hospital = self.dists["time_to_hospital"][
                patient.category
            ].sample()
            yield self.env.timeout(time_to_hospital)

            # Handover time
            handover_time = self.dists["handover_time"][
                patient.category
            ].sample()
            yield self.env.timeout(handover_time)

        # Wrap up time
        wrap_up_time = self.dists["wrap_up_time"][patient.category].sample()
        yield self.env.timeout(wrap_up_time)

        # Return the ambulance
        self.ambulance.put(
            ambulance,
            entity_id=patient.patient_id,
            event="ambulance_available",
        )

        # Return the permit, if one was required
        if permit is not None:
            self.permit.put(permit, auto_log=False)

        self.logger.log_departure(entity_id=patient.patient_id)

        # Notify the dispatcher, as returning resources may allow another
        # patient to be sent
        self.notify_dispatcher()

    def warm_up(self):
        """Reset results collection after the warm-up period."""
        if self.config.warm_up_period > 0:
            yield self.env.timeout(self.config.warm_up_period)
            self.patients = []

    def run(self):
        """Run the simulation model.

        Starts patient generation and resource capacity processes, then runs
        the simulation for the configured duration.

        """
        # Schedule arrival generator and warm-up
        self.env.process(self.generate_patients())
        self.env.process(self.dispatch_patients())
        self.env.process(self.warm_up())

        # Schedule changing number of ambulances if set
        if self.ambulance_availability is not None:
            self.env.process(self.ambulance_availability.run())

        # Varying schedule of number of vehicles permitted for C2-C4 (used to
        # model restricted send)
        if self.permit_availability is not None:
            self.env.process(self.permit_availability.run())

        # Run simulation
        self.env.run(
            until=self.config.warm_up_period
            + self.config.data_collection_period
        )
