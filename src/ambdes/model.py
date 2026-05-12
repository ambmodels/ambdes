"""Core simulation model.

Defines the Model class with all simulation logic for a single run. Handles
SimPy processes and records Patient instances, but does not format results or
manage replications.
"""

import simpy
from sim_tools.distributions import DistributionRegistry
from vidigi.logging import EventLogger
from vidigi.resources import VidigiStore

from .logging import Logger
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
        self.ambulance = VidigiStore(
            self.env, num_resources=self.config.n_ambulances
        )

        # Set up logger with our custom log messages
        self.logger = Logger(config=self.config)
        self.logger.log(f"Initialising model for run {self.run_number}")

        # Set up Vidigi logger
        self.vidigi_logger = EventLogger(
            env=self.env, run_number=self.run_number
        )

        # Set up attribute to store results
        self.patients = []

        # Initialise distributions, with random seed based on run number
        self.dists = DistributionRegistry.create_batch(
            self.config.dist_config,
            main_seed=self.run_number,
            sort=True,
            preserve_structure=True,
        )

    def generate_patients(self, dist, category):
        """Generate patients for a given category indefinitely.

        Parameters
        ----------
        dist : Distribution
            Inter-arrival time distribution for the patient category.
        category : str
            Response category label, e.g., "C1".

        Yields
        ------
        simpy.events.Timeout
            Timeout event until the next patient arrival.

        """
        while True:
            # Sample and pass time to next call
            iat = dist.sample()
            yield self.env.timeout(iat)

            # Create a new patient
            patient = Patient(
                patient_id=len(self.patients) + 1,
                category=category,
                call_timestamp=self.env.now,
            )
            self.patients.append(patient)

            # Log call time
            self.logger.log(
                msg="calls",
                patient=patient,
                sim_time=self.env.now,
            )
            self.vidigi_logger.log_arrival(entity_id=patient.patient_id)

            # Start process of requesting an ambulance
            self.env.process(self.request_ambulance(patient))

    def request_ambulance(self, patient):
        """Simulate ambulance response.

        Parameters
        ----------
        patient : Patient
            Patient requesting ambulance transport.

        """
        # Request an ambulance (and queue if none available)
        self.vidigi_logger.log_queue(
            entity_id=patient.patient_id, event="ambulance_wait_begins"
        )
        with self.ambulance.request() as req:
            vehicle = yield req

            # Record when patient was assigned as ambulance
            self.logger.log(
                msg="assigned an ambulance",
                patient=patient,
                sim_time=self.env.now,
            )
            self.vidigi_logger.log_resource_use_start(
                entity_id=patient.patient_id,
                event="ambulance_arrives",
                resource_id=vehicle.id_attribute,
            )

            # Response time
            patient.response_time = self.dists["response_time"][
                patient.category
            ].sample()
            yield self.env.timeout(patient.response_time)
            self.logger.log(
                msg="ambulance arrives",
                patient=patient,
                sim_time=self.env.now,
            )

            # On-scene time
            yield self.env.timeout(self.config.on_scene_time)
            self.logger.log(
                msg="completed on-scene care; departing for hospital",
                patient=patient,
                sim_time=self.env.now,
            )

            # Travel time to hospital
            patient.travel_time_to_hospital = self.dists[
                "travel_time_to_hospital"
            ].sample()
            yield self.env.timeout(patient.travel_time_to_hospital)
            self.logger.log(
                msg="arrived at hospital",
                patient=patient,
                sim_time=self.env.now,
            )

            # Handover time
            patient.handover_time = self.dists["handover_time"].sample()
            yield self.env.timeout(patient.handover_time)
            self.logger.log(
                msg="handover completed",
                patient=patient,
                sim_time=self.env.now,
            )

            # Wrap up time
            yield self.env.timeout(self.config.wrap_up_time)
            self.logger.log(
                msg="wrap-up completed; ambulance available",
                patient=patient,
                sim_time=self.env.now,
            )
            self.vidigi_logger.log_resource_use_end(
                entity_id=patient.patient_id,
                event="ambulance_available",
                resource_id=vehicle.id_attribute,
            )
            self.vidigi_logger.log_departure(
                entity_id=patient.patient_id,
            )

    def run(self):
        """Run the simulation model.

        Starts one patient-generation process for each category and runs the
        simulation until the configured run length.

        """
        # Set up processes to generate patients of each category
        for category, dist in self.dists["call"].items():
            self.env.process(
                self.generate_patients(dist=dist, category=category)
            )
        # Run simulation
        self.env.run(until=self.config.run_length)

        # Log end of simulation
        self.logger.log(
            msg=f"Simulation run {self.run_number} ends",
            sim_time=self.env.now,
        )
