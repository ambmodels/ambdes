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
            Dictionary with model instance and two DataFrames:
            - "model": model instance (useful for development/debugging).
            - "patients": per-patient results for the run.
            - "run": summary of results for run by response category.

        """
        model = Model(run_number=run_number, config=self.config)
        model.run()
        results = Results(model=model)
        return {
            "model": model,
            "patients": results.patient_df(),
            "run": results.summary_df(),
        }

    def run_reps(self):
        """Run replications, as defined by config.n_reps.

        Returns
        -------
        dict
            Dictionary with two DataFrames:
            - "patients": concatenated per-patient results across runs.
            - "run": summary of results for each run by response category.
            - "overall": summary of results across runs by response category.

        """
        all_runs = [self.run_single(i) for i in range(self.config.n_reps)]
        patients = pd.concat(
            [r["patients"] for r in all_runs], ignore_index=True
        )
        run = pd.concat([r["run"] for r in all_runs], ignore_index=True)
        overall = (
            run.drop(columns=["run"], errors="ignore")
            .groupby("category", dropna=False)
            .mean()
            .rename(
                columns=lambda c: c if c.startswith("mean_") else f"mean_{c}"
            )
            .reset_index()
        )
        return {
            "patients": patients,
            "run": run,
            "overall": overall,
        }
