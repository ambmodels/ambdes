"""Calculate simulation results."""

import pandas as pd
import statsmodels.stats.api as sms


class UtilisationCalculator:
    """Compute time-weighted ambulance utilisation from an event log.

    Attributes
    ----------
    log : pd.DataFrame
        Event log from a vidigi EventLogger.
    warm_up_period : float
        Length of the warm-up period - observations before this time are
        excluded.
    data_collection_period : float
        Length of the data collection period.
    run_length : float
        Total run length (including warm-up and data collection period).
    capacity : int
        Total number of ambulances.

    """

    def __init__(self, log, warm_up_period, data_collection_period, capacity):
        """Initialise UtilisationCalculator.

        Parameters
        ----------
        log : pd.DataFrame
            Event log from a vidigi EventLogger.
        warm_up_period : float
            Length of the warm-up period - observations before this time are
            excluded.
        data_collection_period : float
            Length of the data collection period.
        capacity : int
            Total number of ambulances.

        """
        self.log = log
        self.warm_up_period = warm_up_period
        self.data_collection_period = data_collection_period
        self.run_length = warm_up_period + data_collection_period
        self.capacity = capacity

    @classmethod
    def from_model(cls, model):
        """Construct a UtilisationCalculator from a completed Model instance.

        This "classmethod" makes it easier to set up the UtilisationCalculator
        as you can just write UtilisationCalculator.from_model(model) instead
        of manually passing all the arguments.

        Parameters
        ----------
        model : Model
            A model instance that has already been executed (model.run()).

        Returns
        -------
        UtilisationCalculator

        """
        return cls(
            log=model.logger.to_dataframe(),
            warm_up_period=model.config.warm_up_period,
            data_collection_period=model.config.data_collection_period,
            capacity=model.config.n_ambulances,
        )

    @classmethod
    def from_model_at_time(cls, model, current_time):
        """Construct a UtilisationCalculator from a running Model, up to now.

        Intended for use during warm-up audits, where the model has not
        yet finished. warm_up_period is forced to 0 and run_length is set
        to current_time so the full elapsed period is included.

        This "classmethod" makes it easier to set up the UtilisationCalculator
        as you can just write UtilisationCalculator.from_model_at_time(model)
        instead of manually passing all the arguments.

        Parameters
        ----------
        model : Model
            A model instance that has been run up to current_time.
        current_time : float
            The simulation time to treat as the end of the observation
            window.

        Returns
        -------
        UtilisationCalculator

        """
        return cls(
            log=model.logger.to_dataframe(),
            warm_up_period=0,
            data_collection_period=current_time,
            capacity=model.config.n_ambulances,
        )

    def state_changes_df(self):
        """Return the time-weighted ambulance utilisation intervals.

        Returns
        -------
        state_changes : pd.DataFrame
            Columns: time, busy, interval_duration, utilisation. One row per
            state-change interval during the data collection period. `busy`
            is the number of ambulances in use during that interval.

        """
        # Return empty of logger returned an empty DataFrame with no columns
        if self.log.empty:
            return pd.DataFrame(
                columns=["time", "busy", "interval_duration", "utilisation"]
            )

        # Filter to events marking start and end of ambulance resource use
        amb = self.log.loc[
            self.log["event"].isin(
                ["ambulance_assigned", "ambulance_available"]
            ),
            ["entity_id", "event_type", "time"],
        ]

        # Create two dataframes - one with start times and one with end times
        starts = amb.loc[
            amb["event_type"] == "resource_use", ["entity_id", "time"]
        ].rename(columns={"time": "start_time"})
        ends = amb.loc[
            amb["event_type"] == "resource_use_end", ["entity_id", "time"]
        ].rename(columns={"time": "end_time"})

        # Defensive check: each ID should only correspond to one start
        dup_starts = starts.loc[starts["entity_id"].duplicated(), "entity_id"]
        dup_ends = ends.loc[ends["entity_id"].duplicated(), "entity_id"]
        dup_id = set(dup_starts) | set(dup_ends)
        if dup_id:
            raise ValueError(
                "Duplicate entity_id values found in ambulance event log ",
                f"(n={len(dup_id)}). Each entity_id must only appear once ",
                "for one arrival and one departure."
            )

        # Combine these, so each patient has one row with start and end time
        intervals = starts.merge(ends, on="entity_id", how="left")

        # If end_time is NA, use end of observation window as end time
        intervals["end_time"] = intervals["end_time"].fillna(self.run_length)

        # Clip the intervals, so those entirely before warm-up are dropped,
        # and those that span warm-up are trimmed so their start time is the
        # start of the data collection period
        intervals["start_time"] = intervals["start_time"].clip(
            lower=self.warm_up_period
        )
        intervals["end_time"] = intervals["end_time"].clip(
            lower=self.warm_up_period
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
            state_changes["time"].shift(-1).fillna(self.run_length)
            - state_changes["time"]
        )

        # Drop any zero-length states, just to be safe
        state_changes = state_changes.loc[
            state_changes["interval_duration"] > 0
        ]

        # Convert busy ambulances into utilisation.
        # Because capacity is fixed in this model, utilisation is simply
        # busy/capacity.
        state_changes["utilisation"] = state_changes["busy"] / self.capacity

        return state_changes

    def mean_utilisation(self):
        """Return mean time-weighted ambulance utilisation.

        Returns
        -------
        float
            Mean time-weighted ambulance utilisation.

        """
        util_df = self.state_changes_df()

        # If there is no observed utilisation interval, return 0
        if util_df.empty or self.data_collection_period <= 0:
            return 0

        # Time-weighted mean utilisation
        return (util_df["busy"] * util_df["interval_duration"]).sum() / (
            self.capacity * self.data_collection_period
        )


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
                    "outcome": p.outcome,
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
        pd.DataFrame
            Columns: time, busy, interval_duration, utilisation.

        """
        return UtilisationCalculator.from_model(self.model).state_changes_df()

    def utilisation(self):
        """Return mean time-weighted ambulance utilisation.

        Returns
        -------
        float
            Mean time-weighted ambulance utilisation.

        """
        return UtilisationCalculator.from_model(self.model).mean_utilisation()

    def summary_df(self):
        """Return run-level summary in long format.

        Returns
        -------
        pd.DataFrame
            Run-level summary.

        """
        df = self.patient_df()

        # Mean response time by response category
        by_category = (
            df.groupby("category", dropna=False)
            .agg(response_time_mean=("response_time", "mean"))
            .reset_index()
            .assign(outcome="all", run=self.model.run_number)
        )

        # Mean response time by category and outcome
        by_category_outcome = (
            df.groupby(["category", "outcome"], dropna=False)
            .agg(response_time_mean=("response_time", "mean"))
            .reset_index()
            .assign(run=self.model.run_number)
        )

        summary = pd.concat(
            [by_category, by_category_outcome], ignore_index=True
        )

        # Overall utilisation
        utilisation = pd.DataFrame(
            [
                {
                    "run": self.model.run_number,
                    "category": "all",
                    "outcome": "all",
                    "utilisation_mean": self.utilisation(),
                }
            ]
        )

        return pd.concat([summary, utilisation], ignore_index=True)


def combine_run_results(results_list):
    """Combine per-run results into patient, run, and overall DataFrames.

    Parameters
    ----------
    results_list : list of dict
        Each element is the output of Runner.run_single(), with keys
        "patients" and "run".

    Returns
    -------
    dict
        Dictionary with three DataFrames:
        - "patients": concatenated per-patient results across runs.
        - "run": summary of results for each run by category and outcome.
        - "overall": summary of results across runs by category and outcome.

    """
    # Per-patient results across runs
    patients = pd.concat(
        [r["patients"] for r in results_list], ignore_index=True
    )

    # Average results for each run by response category
    run = pd.concat([r["run"] for r in results_list], ignore_index=True)

    # Summary of results across runs by response category
    metrics = [
        c for c in run.columns if c not in ("run", "category", "outcome")
    ]
    records = []
    # Group the results by response category (C1-C4) and outcome
    for (category, outcome), group in run.groupby(
        ["category", "outcome"], dropna=False
    ):
        row = {"category": category, "outcome": outcome}
        # Filter to each metric for that group, ignoring NA
        for col in metrics:
            values = group[col].dropna()
            # If too few runs with results, don't return confidence intervals
            if len(values) < 2:
                mean = values.mean() if len(values) else float("nan")
                lower, upper = float("nan"), float("nan")
            # Otherwise, return mean and confidence intervals
            else:
                mean = values.mean()
                lower, upper = sms.DescrStatsW(values).tconfint_mean(
                    alpha=0.05
                )
            row[f"{col}"] = mean
            row[f"{col}_ci_lower"] = lower
            row[f"{col}_ci_upper"] = upper
        records.append(row)
    overall = pd.DataFrame(records)

    return {
        "patients": patients,
        "run": run,
        "overall": overall,
    }
