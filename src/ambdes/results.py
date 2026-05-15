"""Convert model output into results tables.

Takes patient list from one Model run and returns tidy pandas DataFrames
(per-patient and run-level summaries).
"""

import pandas as pd


class Results:
    """Simulation output for a single model run."""

    def __init__(self, model):
        """Create instance of Results.

        Parameters
        ----------
        model : Model
        A model instance that has already been executed (model.run())

        """
        self.model = model

    def patient_df(self):
        """Return per-patient results as a DataFrame.

        Each row represents one patient. Patients who had not completed
        their full pathway by the end of the run will have NaN for unset
        time attributes.

        Returns
        -------
        pd.DataFrame
            Columns: run, patient_id, category, call_timestamp, response_time.

        """
        return pd.DataFrame(
            [
                {
                    "run": self.model.run_number,
                    "patient_id": p.patient_id,
                    "category": p.category,
                    "call_timestamp": p.call_timestamp,
                    "response_time": p.response_time,
                }
                for p in self.model.patients
            ]
        )

    def utilisation_df(self):
        """Return mean utilisation of ambulances.

        Returns
        -------
        pd.DataFrame
            Columns: run, mean_utilisation.
        """
        log = self.model.logger.to_dataframe()
        warm_up_period = self.model.config.warm_up_period
        run_length = warm_up_period + self.model.config.data_collection_period

        amb = log[
            log["event"].isin(["ambulance_assigned", "ambulance_available"])
        ][["entity_id", "event_type", "time"]]

        # Create dataframe with one row per ID and columns with start and end time of resource use
        starts = amb[amb["event_type"] == "resource_use"].rename(
            columns={"time": "start_time"}
        )[["entity_id", "start_time"]]
        ends = amb[amb["event_type"] == "resource_use_end"].rename(
            columns={"time": "end_time"}
        )[["entity_id", "end_time"]]
        intervals = starts.merge(ends, on="entity_id", how="left")

        # Drop events that completed before data collection period started
        intervals = intervals[~(intervals["end_time"] < warm_up_period)]

        # Events not complete by simulation end, replace NA with simulation end time
        intervals["end_time"] = intervals["end_time"].fillna(run_length)

        # Split by arrival time
        arrive_before = intervals[
            intervals["start_time"] < warm_up_period
        ].copy()
        arrive_after = intervals[intervals["start_time"] >= warm_up_period]

        # For resource_use events before warmup with end events after warmup, replace
        # time with the start of the warm-up period
        arrive_before["start_time"] = warm_up_period

        # Combine and sort
        result = pd.concat(
            [arrive_before, arrive_after], ignore_index=True
        ).sort_values(["start_time"])

        # Convert to state changes
        rows = []
        for _, row in result.iterrows():
            rows.append({"time": row["start_time"], "event": "start"})
            rows.append({"time": row["end_time"], "event": "end"})

        events_df = (
            pd.DataFrame(rows).sort_values("time").reset_index(drop=True)
        )
        events_df["server"] = (
            events_df["event"]
            .apply(lambda x: 1 if x == "start" else -1)
            .cumsum()
        )
        state_changes = (
            events_df[["time", "server"]]
            .drop_duplicates(subset="time", keep="last")
            .copy()
        )

        # Calculate interval metrics
        state_changes["interval_duration"] = (
            state_changes["time"].shift(-1).fillna(run_length)
            - state_changes["time"]
        )
        capacity = self.model.config.n_ambulances
        state_changes["utilisation"] = (
            state_changes["server"] / capacity if capacity > 0 else np.nan
        )

    def utilisation(self):
        """TODO"""
        util_df = self.utilisation_df()
        return (
            util_df["utilisation"] * util_df["interval_duration"]
        ).sum() / util_df["interval_duration"].sum()

    def summary_df(self):
        """Return summary DataFrame with four rows: one per response category.

        Returns
        -------
        pd.DataFrame
            Columns: run, n_patients.

        """
        df = self.patient_df()

        return (
            df.groupby("category", dropna=False)
            .agg(
                n_patients=("patient_id", "count"),
                mean_response_time=("response_time", "mean"),
            )
            .reset_index()
            .assign(run=self.model.run_number)
        )
