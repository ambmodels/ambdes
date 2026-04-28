"""Simulation model."""

import numpy as np
import simpy
from sim_tools.distributions import Exponential

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

        # Create a random seed sequence based on the run number
        ss = np.random.SeedSequence(self.run_number)
        seeds = ss.spawn(4)

        # Set up attribute to store results
        self.patients = []

        # Initialise call inter-arrival distributions
        self.call_dists = {}
        for i, (category, mean_iat_min) in enumerate(
            self.config.mean_iat_min.items()
        ):
            self.call_dists[category] = Exponential(
                mean=mean_iat_min, random_seed=seeds[i]
            )

    def generate_patients(self, dist, category):
        """Generate patients for a given category indefinitely.

        Parameters
        ----------
        dist : Exponential
            Inter-arrival time distribution for the patient category.
        category : int
            Response category number.

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

            yield self.env.timeout(10)

            # Log when ambulance is released
            self.logger.log(
                msg="ambulance now free",
                patient=patient,
                sim_time=self.env.now,
            )

    def run(self):
        """Run the simulation model.

        Starts one patient-generation process for each category and runs the
        simulation until the configured run length.

        """
        # Set up processes to generate patients of each category
        for category, dist in self.call_dists.items():
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
