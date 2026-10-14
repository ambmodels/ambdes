"""Objects for running the model with empirical distributions."""

import numpy as np
from sim_tools.distributions import RawContinuousEmpirical

from .model import Model
from .results import Results
from .runner import Runner


def build_empirical_config(time_data, run_number):
    """Build registry configuration for empirical time distributions.

    Parameters
    ----------
    time_data : pd.DataFrame
        The raw ambulance data containing times per patient.
    run_number : int
        Run number, used to initialise SeedSequence.

    Returns
    -------
    results : dict
        Nested dictionary of distributions.

    """
    # Six single column stages across four categories (24), plus on-scene time
    # across four categories and two outcomes (8) -> 32
    seed_sequence = np.random.SeedSequence([run_number, 1])
    child_seeds = iter(seed_sequence.spawn(32))
    results = {}

    # For columns that just group by response category...
    single_columns = {
        "connect_to_queue_time": "AddedToStack_Duration",
        "mobilisation_time": "C0001_Mobilisation_Duration",
        "time_to_scene": "C0004_MobilisationToScene_Duration",
        "time_to_hospital": "C0172_SceneToDestination_Duration",
        "handover_time": "C0012_Handover_Duration",
        "wrap_up_time": "C0171_WrapUp_Duration",
    }
    for stage, column in single_columns.items():
        results[stage] = {}
        for i in range(1, 5):
            # Get the time data for that metric and category
            mask = time_data["ResponseCategoryGroupLevel2"] == f"Category {i}"
            values = time_data.loc[mask, column].dropna().values
            # Convert to minutes
            values = values / 60
            # Construct distribution and save into results dictionary
            results[stage][f"C{i}"] = RawContinuousEmpirical(
                data=values, random_seed=next(child_seeds)
            )

    # For columns that group by response category and outcome...
    outcomes = {
        "see_and_convey": ["See & Convey ED", "See & Convey non ED"],
        "see_and_treat": ["See & Treat"],
    }
    results["on_scene_time"] = {}
    for i in range(1, 5):
        # Create mask for that response category
        category_mask = (
            time_data["ResponseCategoryGroupLevel2"] == f"Category {i}"
        )
        # Set up new nested dict to store results per outcome
        results["on_scene_time"][f"C{i}"] = {}
        for outcome, outcome_values in outcomes.items():
            # Create mask for that response outcome
            outcome_mask = time_data["C0660_CallOutcomeDetail"].isin(
                outcome_values
            )
            # Filter to data for that metric, category and outcome
            values = (
                time_data.loc[
                    category_mask & outcome_mask, "C0007_OnScene_Duration"
                ]
                .dropna()
                .values
            )
            # Convert to minutes
            values = values / 60
            # Construct distribution and save into results dictionary
            results["on_scene_time"][f"C{i}"][outcome] = (
                RawContinuousEmpirical(
                    data=values, random_seed=next(child_seeds)
                )
            )

    return results


class EmpiricalRunner(Runner):
    """Run replications using empirical process time distributions."""

    def __init__(self, config, time_data):
        """Initialise EmpiricalRunner.

        config : ambdes.SimConfig
            Simulation configuration instance.
        time_data : pd.DataFrame
            Raw time data.
        """
        super().__init__(config)
        self.time_data = time_data

    def run_single(self, run_number):
        """Replace method from Runner, now with set-up for empirical dists.

        Parameters
        ----------
        run_number : int
            Used to set up SeedSequence which is used when initialising the
            empirical distributions.

        Returns
        -------
        dict
            Dictionary with two DataFrames:
            - "patients": per-patient results for the run.
            - "run": summary of results for run by response category.

        """
        model = Model(run_number, config=self.config)
        empirical_dists = build_empirical_config(
            time_data=self.time_data, run_number=run_number
        )
        model.dists.update(empirical_dists)
        model.run()
        results = Results(model=model)
        return {
            "patients": results.patient_df(),
            "run": results.summary_df(),
        }
