"""Simulation model."""

import simpy
from sim_tools.distributions import DistributionRegistry

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
            Simulation run identifier used to initialise random seeds.
        config : object
            Configuration object containing model parameters, including
            `mean_iat_min` and `run_length`.

        """
        self.run_number = run_number
        self.config = config

        # Create SimPy environment
        self.env = simpy.Environment()

        # Set up ambulance resource
        self.ambulance = simpy.Resource(
            self.env, capacity=self.config.n_ambulances
        )

        # Set up logger
        self.logger = Logger(config=self.config)
        self.logger.log(f"Initialising model for run {self.run_number}")

        # Set up attribute to store results
        self.patients = []

        # Initialise distributions, with random seed based on run number
        flat_dists = DistributionRegistry.create_batch(
            self.config.dist_config,
            main_seed=self.run_number,
            sort=True,
        )

        # Restructure so can call e.g., self.dists["call"]["C1"]
        self.dists = {
            "call": {},
            "response_time": {},
        }
        for name, dist in flat_dists.items():
            group, category = name.rsplit("_", 1)
            self.dists[group][category] = dist

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
                id=len(self.patients) + 1,
                category=category,
                call_time=self.env.now,
            )
            self.patients.append(patient)

            # Log call time
            self.logger.log(
                msg="calls",
                patient=patient,
                sim_time=self.env.now,
            )

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
        with self.ambulance.request() as req:
            yield req

            # Record when patient was assigned as ambulance
            self.logger.log(
                msg="assigned an ambulance",
                patient=patient,
                sim_time=self.env.now,
            )

            # Response time
            response_time = self.dists["response_time"][
                patient.category
            ].sample()
            yield self.env.timeout(response_time)
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
            yield self.env.timeout(self.config.travel_time_to_hospital)
            self.logger.log(
                msg="arrived at hospital",
                patient=patient,
                sim_time=self.env.now,
            )

            # Handover time
            yield self.env.timeout(self.config.mean_handover_time_min)
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
