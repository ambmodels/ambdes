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
        """Return time-weighted ambulance utilisation intervals.

        Returns
        -------
        state_changes : pd.DataFrame
            Columns: time, busy, interval_duration, utilisation. One row per
            state-change interval during the data collection period. `busy`
            is the number of ambulances in use during that interval.

        """
        log = self.model.logger.to_dataframe()
        warm_up_period = self.model.config.warm_up_period
        run_length = warm_up_period + self.model.config.data_collection_period
        capacity = self.model.config.n_ambulances

        # Return empty of logger returned an empty DataFrame with no columns
        if log.empty:
            return pd.DataFrame(
                columns=["time", "busy", "interval_duration", "utilisation"]
            )

        # Filter to events marking start and end of ambulance resource use
        amb = log.loc[
            log["event"].isin(["ambulance_assigned", "ambulance_available"]),
            ["entity_id", "event_type", "time"],
        ]

        # Create two dataframes - one with start times and one with end times
        starts = amb.loc[
            amb["event_type"] == "resource_use", ["entity_id", "time"]
        ].rename(columns={"time": "start_time"})
        ends = amb.loc[
            amb["event_type"] == "resource_use_end", ["entity_id", "time"]
        ].rename(columns={"time": "end_time"})

        # Combine these, so each patient has one row with start and end time
        intervals = starts.merge(ends, on="entity_id", how="left")

        # If end_time is NA, use end of observation window as end time
        intervals["end_time"] = intervals["end_time"].fillna(run_length)

        # Clip the intervals, so those entirely before warm-up are dropped,
        # and those that span warm-up are trimmed so their start time is the
        # start of the data collection period
        intervals["start_time"] = intervals["start_time"].clip(
            lower=warm_up_period
        )
        intervals["end_time"] = intervals["end_time"].clip(
            lower=warm_up_period
        )
        # Drop those before warm-up (becomes [start, start])
        intervals = intervals.loc[
            intervals["end_time"] > intervals["start_time"]
        ]

        if intervals.empty:
            return pd.DataFrame(
                columns=["time", "busy", "interval_duration", "utilisation"]
            )

        # Convert intervals into event times: +1 when ambulance becomes busy
        # and -1 when ambulance stops being busy
        events = pd.concat(
            [
                intervals[["start_time"]]
                .rename(columns={"start_time": "time"})
                .assign(delta=1),
                intervals[["end_time"]]
                .rename(columns={"end_time": "time"})
                .assign(delta=-1),
            ],
            ignore_index=True,
        ).sort_values("time")

        # Combine all changes that happen at the same simulation time, then
        # take a cumulative sum to get the number of busy ambulances after
        # each event time. Grouping by time is important because multiple
        # ambulances may start/end at exactly the same timestamp.
        state_changes = (
            events.groupby("time", as_index=False)["delta"]
            .sum()
            .assign(busy=lambda df: df["delta"].cumsum())
            .drop(columns="delta")
        )

        # The duration of each state is the gap until the next change in
        # state. The final state runs until the end of the observation window.
        state_changes["interval_duration"] = (
            state_changes["time"].shift(-1).fillna(run_length)
            - state_changes["time"]
        )

        # Drop any zero-length states, just to be safe
        state_changes = state_changes.loc[
            state_changes["interval_duration"] > 0
        ]

        # Convert busy ambulances into utilisation.
        # Because capacity is fixed in this model, utilisation is simply
        # busy/capacity.
        state_changes["utilisation"] = state_changes["busy"] / capacity

        return state_changes

    def utilisation(self):
        """Return mean time-weighted ambulance utilisation.

        Returns
        -------
        float
            Mean time-weighted ambulance utilisation.

        """
        util_df = self.utilisation_df()
        data_collection_period = self.model.config.data_collection_period
        capacity = self.model.config.n_ambulances

        # If there is no observed utilisation interval, return 0
        if util_df.empty:
            return 0

        # Time-weighted mean utilisation
        return (util_df["busy"] * util_df["interval_duration"]).sum() / (
            capacity * data_collection_period
        )

    def summary_df(self):
        """Return run-level summary in long format.

        Returns
        -------
        pd.DataFrame
            Run-level summary.

        """
        df = self.patient_df()

        # Per category summaries for response time
        summary = (
            df.groupby("category", dropna=False)
            .agg(
                n_patients=("patient_id", "count"),
                mean_response_time=("response_time", "mean"),
            )
            .reset_index()
            .assign(run=self.model.run_number)
        )

        # Overall utilisation
        utilisation = pd.DataFrame(
            [
                {
                    "run": self.model.run_number,
                    "category": "all",
                    "mean_utilisation": self.utilisation(),
                }
            ]
        )

        return pd.concat([summary, utilisation], ignore_index=True)