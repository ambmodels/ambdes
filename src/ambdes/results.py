"""Convert model output into results tables.

Takes patient list from one Model run and returns tidy pandas DataFrames
(per-patient and run-level summaries).
"""

import pandas as pd


class Results:
    """Simulation output for a single model run."""

    def __init__(self, patients, run_number):
        """Create instance of Results.

        Parameters
        ----------
        patients : list of Patient
            Patient instances recorded during the run.
        run_number : int
            Simulation run identifier.

        """
        self.patients = patients
        self.run_number = run_number

    def patient_df(self):
        """Return per-patient results as a DataFrame.

        Each row represents one patient. Patients who had not completed
        their full pathway by the end of the run will have NaN for unset
        time attributes.

        Returns
        -------
        pd.DataFrame
            Columns: run, patient_id, category, call_timestamp,
            response_time, travel_time_to_hospital, handover_time.

        """
        return pd.DataFrame(
            [
                {
                    "run": self.run_number,
                    "patient_id": p.patient_id,
                    "category": p.category,
                    "call_timestamp": p.call_timestamp,
                    "response_time": p.response_time,
                    "travel_time_to_hospital": p.travel_time_to_hospital,
                    "handover_time": p.handover_time,
                }
                for p in self.patients
            ]
        )

    def summary_df(self):
        """Return a single-row summary DataFrame.

        Returns
        -------
        pd.DataFrame
            Columns: run, n_patients.

        """
        return pd.DataFrame(
            [
                {
                    "run": self.run_number,
                    "n_patients": len(self.patients),
                }
            ]
        )
