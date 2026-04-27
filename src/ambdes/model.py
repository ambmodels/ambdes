from sim_tools.distributions import Exponential
import numpy as np
import simpy
from .patient import Patient
from .logging import Logger


class Model:
    """
    """
    def __init__(self, run_number, config):
        """
        """
        self.run_number = run_number
        self.config = config

        # Create SimPy environment
        self.env = simpy.Environment()

        # Set up logger
        self.logger = Logger(verbose=self.config.verbose)
        self.logger.log(f"Initialising model for run {self.run_number}")

        # Create a random seed sequence based on the run number
        ss = np.random.SeedSequence(self.run_number)
        seeds = ss.spawn(4)

        # Set up attribute to store results
        self.patients = []

        # Initialise call inter-arrival distributions
        self.call_dists = {}
        for i, (category, mean_iat_min) in enumerate(self.config.mean_iat_min.items()):
            self.call_dists[category] = Exponential(
                mean=mean_iat_min,
                random_seed=seeds[i]
            )

    def generate_patients(self, dist, category):
        """
        """
        while True:
            # Sample and pass time to next call
            iat = dist.sample()
            yield self.env.timeout(iat)

            # Create a new patient
            patient = Patient(
                id=len(self.patients)+1,
                category=category,
                call_time=self.env.now
            )
            self.patients.append(patient)

            # Print call time
            self.logger.log(
                msg=f"Patient {patient.id} (C{patient.category}) calls",
                sim_time=self.env.now
            )

    def run(self):
        # Set up processes to generate patients of each category
        for category, dist in self.call_dists.items():
            self.env.process(
                self.generate_patients(
                    dist=dist,
                    category=category
                )
            )
        # Run simulation
        self.env.run(until=self.config.run_length)
