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
from .dispatcher import Dispatcher
from .patient import Patient


class Model:
    """Discrete-event simulation model for ambulance responses.

    The model generates patient calls, allocates ambulance resources and
    records patients during a single simulation run.
    """

    # ------------------------------------------------------------------------
    # Model set up
    # ------------------------------------------------------------------------

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

        self._setup_environment()
        self._setup_distributions()
        self._setup_patient_tracking()
        self._setup_resources()
        self._setup_dispatcher()
        self._setup_capacity_schedule()

    def _setup_environment(self):
        """Create the SimPy environment and event logger."""
        self.env = simpy.Environment()
        self.logger = EventLogger(env=self.env, run_number=self.run_number)

    def _setup_distributions(self):
        """Initialise distributions with seed based on run number."""
        self.dists = DistributionRegistry.create_batch(
            self.config.dist_config,
            main_seed=self.run_number,
            sort=True,
            preserve_structure=True,
        )

    def _setup_patient_tracking(self):
        """Create attributes to store patient results and create IDs.

        We create a separate `patient_id_counter` instead of relying on the
        length of `patients` to create IDs as this ensures they are
        independent, and so that patients in warm-up and data collection
        period each have unique ID.
        """
        self.patients = []
        self.patient_id_counter = 0

    def _setup_resources(self):
        """Create ambulance and optional restricted send permit pools."""
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

        # Set-up permit pool. No logging as are just a modelling
        # constraint and dont't represent actual ambulance use
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

    def _setup_dispatcher(self):
        """Create the central dispatcher for ambulance allocation."""
        self.dispatcher = Dispatcher(
            env=self.env,
            ambulance=self.ambulance,
            permit=self.permit,
        )

    def _setup_capacity_schedule(self):
        """Create schedules for resources with varying availability."""
        # Manage varying ambulance availability when a schedule is supplied
        if self.config.ambulance_schedule is not None:
            self.ambulance_availability = CapacitySchedule(
                env=self.env,
                resource=self.ambulance,
                schedule=self.config.ambulance_schedule,
                period=self.config.ambulance_schedule_period,
                record_changes=True,
                on_units_returned=self.dispatcher.notify,
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
                on_units_returned=self.dispatcher.notify,
            )
        else:
            self.permit_availability = None

    # ------------------------------------------------------------------------
    # Model logic
    # ------------------------------------------------------------------------

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
        patient.connect_to_queue_time = self.dists["connect_to_queue_time"][
            patient.category
        ].sample()

        yield self.env.timeout(patient.connect_to_queue_time)

        # Log start time of wait for allocation
        self.logger.log_queue(
            entity_id=patient.patient_id, event="ambulance_wait_begins"
        )

        # Join the dispatch queue and wait for all required resources
        allocation = self.dispatcher.request_resources(patient)
        ambulance, permit = yield allocation

        yield from self.use_ambulance(
            patient=patient,
            ambulance=ambulance,
            permit=permit,
        )

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
        patient.mobilisation_time = self.dists["mobilisation_time"][
            patient.category
        ].sample()
        yield self.env.timeout(patient.mobilisation_time)

        # Sample travel to scene
        patient.time_to_scene = self.dists["time_to_scene"][
            patient.category
        ].sample()
        yield self.env.timeout(patient.time_to_scene)

        # Record response time
        patient.response_time = self.env.now - patient.call_timestamp

        # On-scene time
        patient.on_scene_time = self.dists["on_scene_time"][patient.category][
            patient.outcome
        ].sample()
        yield self.env.timeout(patient.on_scene_time)

        if patient.outcome == "see_and_convey":
            # Sample travel to hospital
            patient.time_to_hospital = self.dists["time_to_hospital"][
                patient.category
            ].sample()
            yield self.env.timeout(patient.time_to_hospital)

            # Handover time
            patient.handover_time = self.dists["handover_time"][
                patient.category
            ].sample()
            yield self.env.timeout(patient.handover_time)

        # Wrap up time
        patient.wrap_up_time = self.dists["wrap_up_time"][
            patient.category
        ].sample()
        yield self.env.timeout(patient.wrap_up_time)

        # Return the allocated resources (and trigger another dispatch check)
        self.dispatcher.return_resources(
            ambulance=ambulance, permit=permit, patient_id=patient.patient_id
        )

        self.logger.log_departure(entity_id=patient.patient_id)

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
        self.env.process(self.dispatcher.run())
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
