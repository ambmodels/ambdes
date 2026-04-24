from sim_tools.distributions import Exponential
import numpy as np
import simpy
from ambdes import Patient


class Model:
    def __init__(self, run_number, config):
        """
        """
        self.run_number = run_number

        # Create SimPy environment
        self.env = simpy.Environment()

        # Create a random seed sequence based on the run number
        ss = np.random.SeedSequence(self.run_number)
        seeds = ss.spawn(4)

        # Set up attribute to store results
        self.patients = []

        # Initialise call inter-arrival distributions
        self.call_dists = {}
        for i, (category, mean_iat_min) in enumerate(config["mean_iat_min"].items()):
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
            print(
                f"C{patient.category} patient {patient.id} calls 999 at: ",
                f"{patient.call_time}"
            )

    def run(self):
        for category, dist in self.call_dists.items():
            self.env.process(self.generate_patients(dist=dist, category=category))
        self.env.run(until=100)
