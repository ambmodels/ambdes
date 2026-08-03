"""Core simulation model.

Defines the Model class with all simulation logic for a single run. Handles
SimPy processes and records Patient instances, but does not format results or
manage replications.
"""

import simpy
from sim_tools.distributions import DistributionRegistry
from vidigi.logging import EventLogger
from vidigi.resources import VidigiPriorityStore

from .patient import Patient


class Model:
    """Discrete-event simulation model for generating patient calls.

    The model creates one call-generation process per patient category and
    records generated patients during a single simulation run.
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

        # Set up ambulance resource
        self.ambulance = VidigiPriorityStore(
            self.env, num_resources=self.config.n_ambulances
        )

        # Set up logger
        self.logger = EventLogger(env=self.env, run_number=self.run_number)

        # Set up attribute to store results
        # Patient ID counter is independent of self.patients to ensure
        # patients in warm-up and data collection period each have unique ID
        self.patients = []
        self.patient_id_counter = 0

        # Initialise distributions, with random seed based on run number
        self.dists = DistributionRegistry.create_batch(
            self.config.dist_config,
            main_seed=self.run_number,
            sort=True,
            preserve_structure=True,
        )

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
        """Simulate ambulance response.

        Parameters
        ----------
        patient : Patient
            Patient requesting ambulance transport.

        """
        # Request an ambulance (will queue if none available)
        self.logger.log_queue(
            entity_id=patient.patient_id, event="ambulance_wait_begins"
        )
        with self.ambulance.request(priority=patient.priority) as req:
            vehicle = yield req

            # Record when patient was assigned an ambulance
            patient.wait_for_assignment = self.env.now - patient.call_timestamp
            self.logger.log_resource_use_start(
                entity_id=patient.patient_id,
                event="ambulance_assigned",
                resource_id=vehicle.id_attribute,
            )

            # Sample mobilisation time
            mobilisation_time = self.dists["mobilisation_time"][
                patient.category
            ].sample()
            yield self.env.timeout(mobilisation_time)

            # Sample travel to scene
            time_to_scene = self.dists["time_to_scene"][
                patient.category
            ].sample()
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
            wrap_up_time = self.dists["wrap_up_time"][
                patient.category
            ].sample()
            yield self.env.timeout(wrap_up_time)

            self.logger.log_resource_use_end(
                entity_id=patient.patient_id,
                event="ambulance_available",
                resource_id=vehicle.id_attribute,
            )
            self.logger.log_departure(
                entity_id=patient.patient_id,
            )

    def warm_up(self):
        """Reset results collection after the warm-up period."""
        if self.config.warm_up_period > 0:
            yield self.env.timeout(self.config.warm_up_period)
            self.patients = []

    def run(self):
        """Run the simulation model.

        Starts one patient-generation process for each category and runs the
        simulation until the configured run length.

        """
        # Schedule arrival generator and warm-up
        self.env.process(self.generate_patients())
        self.env.process(self.warm_up())

        # Run simulation
        self.env.run(
            until=self.config.warm_up_period
            + self.config.data_collection_period
        )
