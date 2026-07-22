"""Run the simulation and combine results.

Executes the Model for one or more runs and uses Results to build and
concatenate per-run DataFrames.
"""

from joblib import Parallel, cpu_count, delayed

from .model import Model
from .results import Results, combine_run_results


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
            - "run": summary of results for run by response category.

        """
        model = Model(run_number=run_number, config=self.config)
        model.run()
        results = Results(model=model)
        return {
            "patients": results.patient_df(),
            "run": results.summary_df(),
        }

    def run_reps(self):
        """Run replications, as defined by config.n_reps.

        Returns
        -------
        dict
            Dictionary with three DataFrames:
            - "patients": concatenated per-patient results across runs.
            - "run": summary of results for each run by response category.
            - "overall": summary of results across runs by response category.

        """
        # Sequential execution
        if self.config.cores == 1:
            all_runs = [self.run_single(i) for i in range(self.config.n_reps)]
        # Parallel execution
        else:
            # Check the requested number of cores is possible on machine
            valid_cores = [-1] + list(range(1, cpu_count()))
            if self.config.cores not in valid_cores:
                raise ValueError(
                    f"Invalid cores: {self.config.cores}. Must be one of: "
                    + f"{valid_cores}."
                )
            # Execute replications in parallel
            all_runs = Parallel(n_jobs=self.config.cores)(
                delayed(self.run_single)(i) for i in range(self.config.n_reps)
            )

        # Create results dataframes
        return combine_run_results(all_runs)
