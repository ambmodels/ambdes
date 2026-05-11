"""Run the simulation and combine results.

Executes the Model for one or more runs and uses Results to build and
concatenate per-run DataFrames.
"""

import pandas as pd

from .model import Model
from .results import Results


class Runner:
    """Run the simulation for one or more replications."""

    def __init__(self, config):
        """Create instance of Runner.

        Parameters
        ----------
        config : object
            Configuration object containing model parameters.

        """
        self.config = config

    def run_single(self, run_number):
        """Run a single replication and return results.

        Parameters
        ----------
        run_number : int
            Simulation run identifier.

        Returns
        -------
        dict
            Dictionary with two DataFrames:
            - "patients": per-patient results for the run.
            - "summary": single-row summary for the run.

        """
        model = Model(run_number=run_number, config=self.config)
        model.run()
        results = Results(model.patients, run_number)
        return {
            "patients": results.patient_df(),
            "summary": results.summary_df(),
        }

    def run_reps(self):
        """Run replications, as defined by config.n_reps.

        Returns
        -------
        dict
            Dictionary with two DataFrames:
            - "patients": concatenated per-patient results across runs.
            - "summary": one-row-per-run summary table.

        """
        all_runs = [self.run_single(i) for i in range(self.config.n_reps)]
        return {
            "patients": pd.concat(
                [r["patients"] for r in all_runs], ignore_index=True
            ),
            "summary": pd.concat(
                [r["summary"] for r in all_runs], ignore_index=True
            ),
        }
