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
    capacity_log : pd.DataFrame
        Record of ambulance capacity over time.

    """

    def __init__(
        self,
        log,
        warm_up_period,
        data_collection_period,
        capacity=None,
        capacity_log=None,
    ):
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
            Fixed number of ambulances available throughout the simulation.
            Provide this argument when capacity does not change over time.
            Exactly one of `capacity` or `capacity_log` must be provided.
        capacity_log : list[dict]
            Record of changes in ambulance capacity over time. Provide this
            argument when capacity varies during the simulation. Exactly one
            of `capacity` or `capacity_log` must be provided.

        """
        self.log = log
        self.warm_up_period = warm_up_period
        self.data_collection_period = data_collection_period
        self.run_length = warm_up_period + data_collection_period

        if (capacity is None) == (capacity_log is None):
            raise ValueError(
                "Provide exactly one of 'capacity' or 'capacity_log', not "
                "both or neither."
            )

        # Create capacity log if not otherwise provided, then convert into a
        # dataframe. This allows consistent methods below regardless of
        # whether the model had variable capacity or fixed capacity.
        if capacity_log is None:
            capacity_log = [{"time": 0.0, "capacity": capacity}]
        self.capacity_log = pd.DataFrame(capacity_log)

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
        kwargs = dict(
            log=model.logger.to_dataframe(),
            warm_up_period=model.config.warm_up_period,
            data_collection_period=model.config.data_collection_period
        )
        if hasattr(model, "capacity_log"):
            kwargs["capacity_log"] = model.capacity_log
        else:
            kwargs["capacity"] = model.config.n_ambulances
        return cls(**kwargs)

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
        kwargs = dict(
            log=model.logger.to_dataframe(),
            warm_up_period=0,
            data_collection_period=current_time,
        )
        if hasattr(model, "capacity_log"):
            kwargs["capacity_log"] = model.capacity_log
        else:
            kwargs["capacity"] = model.config.n_ambulances
        return cls(**kwargs)

    def create_util_df(self):
        """Return the time-weighted ambulance utilisation intervals.

        Returns
        -------
        util_df : pd.DataFrame
            Columns: time, busy, capacity, interval_duration, and utilisation.
            One row per state-change interval during the data collection
            period. `busy` is the number of ambulances in use during that
            interval.

        """
        # Return empty of logger returned an empty DataFrame with no columns
        if self.log.empty:
            return pd.DataFrame(
                columns=[
                    "time",
                    "busy",
                    "capacity",
                    "interval_duration",
                    "utilisation",
                ]
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
                "for one arrival and one departure.",
            )

        # Combine these, so each patient has one row with start and end time
        intervals = starts.merge(ends, on="entity_id", how="left")

        # If end_time is NA, use end of observation window as end time
        intervals["end_time"] = intervals["end_time"].fillna(self.run_length)

        # Clip the intervals, so those entirely before warm-up are dropped,
        # and those that span warm-up are trimmed so their start time is the
        # start of the data collection period
        intervals["start_time"] = intervals["start_time"].clip(
            lower=self.warm_up_period, upper=self.run_length
        )
        intervals["end_time"] = intervals["end_time"].clip(
            lower=self.warm_up_period, upper=self.run_length
        )
        # Drop those before warm-up (becomes [start, start])
        intervals = intervals.loc[
            intervals["end_time"] > intervals["start_time"]
        ]

        if intervals.empty:
            return pd.DataFrame(
                columns=[
                    "time",
                    "busy",
                    "capacity",
                    "interval_duration",
                    "utilisation",
                ]
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
        # Combine simultaneous changes so it becomes +-0/1/2/3/4/5... with
        # just one row per timepoint
        events = events.groupby("time", as_index=False)["delta"].sum()

        # Keep the last achieved capacity at each timestamp (there can be
        # several individual ambulance changes at same time as add or remove
        # each one - just need a summary of what capacity became at that
        # timepoint)
        capacity_changes = (
            self.capacity_log[["time", "capacity"]]
            .sort_values("time")
            .drop_duplicates(subset="time", keep="last")
        )

        # Create a timeline of every point when:
        # - The number of busy ambulances changes
        # - The operational capacity changes
        # - The observation window starts and ends
        # Only include times that occurred during the observation window
        # (i.e., after warm-up ended)
        capacity_times = capacity_changes.loc[
            capacity_changes["time"].between(
                self.warm_up_period,
                self.run_length,
            ),
            "time",
        ]
        times = sorted(
            {
                self.warm_up_period,
                self.run_length,
                *events["time"].tolist(),
                *capacity_times.tolist(),
            }
        )
        util_df = pd.DataFrame({"time": times})

        # merge_asof requires identical key dtypes, so force time to float
        util_df["time"] = util_df["time"].astype(float)
        capacity_changes["time"] = capacity_changes["time"].astype(float)

        # Add the record of when ambulances were busy/releated by patients
        util_df = util_df.merge(
            events,
            on="time",
            how="left",
        )

        # For any timepoints with no change in ambulance use, set to 0
        util_df["delta"] = util_df["delta"].fillna(0).astype(int)

        # Calculate the total number of ambulances busy at each timepoint
        util_df["busy"] = util_df["delta"].cumsum()
        util_df = util_df.drop(columns="delta")

        # Add the capacity at each timepoint
        util_df = pd.merge_asof(
            util_df.sort_values("time"),
            capacity_changes.sort_values("time"),
            on="time",
            direction="backward",
        )

        # Find the time between each row, dropping any with a time of 0.
        # The final state runs until the end of the observation window.
        util_df["interval_duration"] = (
            util_df["time"].shift(-1).fillna(self.run_length) - util_df["time"]
        )
        util_df = util_df.loc[util_df["interval_duration"] > 0].copy()

        # Check that the state is valid
        invalid = util_df.loc[util_df["busy"] > util_df["capacity"]]
        if not invalid.empty:
            raise ValueError(
                "Reconstructed busy ambulances exceed operational capacity:\n"
                f"{invalid}"
            )

        # Filter to where there is non-zero capacity (as only relevant to
        # include utilisation if there is any vehicles that can possibly be
        # utilised)
        util_df = util_df.loc[util_df["capacity"] > 0].copy()

        # Calculate utilisation at that timepoint (number of busy units over
        # the total capacity at that timepoint)
        util_df["utilisation"] = util_df["busy"] / util_df["capacity"]

        return util_df

    def mean_utilisation(self):
        """Return mean time-weighted ambulance utilisation.

        Calculated as total busy ambulance-minutes divided by total available
        ambulance-minutes. Accounts for interval duration and changes in
        available capacity.

        Returns
        -------
        float
            Mean time-weighted ambulance utilisation.

        """
        util_df = self.create_util_df()

        # If there is no observed utilisation interval, return 0
        if util_df.empty or self.data_collection_period <= 0:
            return 0

        # Time-weighted mean utilisation
        busy_minutes = (util_df["busy"] * util_df["interval_duration"]).sum()
        operational_minutes = (
            util_df["capacity"] * util_df["interval_duration"]
        ).sum()
        return busy_minutes / operational_minutes


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
            Dataframe with patient-level results.

        """
        df = pd.DataFrame([vars(p) for p in self.model.patients])
        df.insert(0, "run", self.model.run_number)
        return df

    def utilisation_df(self):
        """Return time-weighted ambulance utilisation intervals.

        Returns
        -------
        pd.DataFrame
            Columns: time, busy, interval_duration, utilisation.

        """
        return UtilisationCalculator.from_model(self.model).create_util_df()

    def utilisation(self):
        """Return mean time-weighted ambulance utilisation.

        Returns
        -------
        float
            Mean time-weighted ambulance utilisation.

        """
        return UtilisationCalculator.from_model(self.model).mean_utilisation()

    def mean_by_category(self, df, col, name):
        """Find mean of metric by response category, and then also by outcome.

        Parameters
        ----------
        df : pd.DataFrame
            Patient-level dataframe.
        col : str
            Column to aggregate.
        name : str
            Name to assign in the metric column.

        Returns
        -------
        pd.DataFrame
            Long-format dataframe with aggregated results.

        """
        # Aggregate by response category
        by_category = (
            df.groupby("category", dropna=False)[col]
            .mean()
            .reset_index(name="value")
            .assign(outcome="all", run=self.model.run_number, metric=name)
        )
        # Aggregate by response category and response outcome
        by_category_outcome = (
            df.groupby(["category", "outcome"], dropna=False)[col]
            .mean()
            .reset_index(name="value")
            .assign(run=self.model.run_number, metric=name)
        )
        # Return a single dataframe
        return pd.concat([by_category, by_category_outcome], ignore_index=True)

    def summary_df(self):
        """Return run-level summary in long format.

        Returns
        -------
        pd.DataFrame
            Run-level summary.

        """
        df = self.patient_df()

        # Minutes 0-1439 -> day 1, 1440-2879 -> day 2, etc.
        df["day"] = (df["call_timestamp"] // 1440).astype(int) + 1

        # Mean response time and mean wait time for ambulance assignment by
        # response category, and by response category and outcome
        response_time = self.mean_by_category(
            df=df,
            col="response_time",
            name="response_time_mean",
        )
        allocation_time = self.mean_by_category(
            df=df,
            col="allocation_time",
            name="allocation_time_mean",
        )

        # Mean arrivals per day by response category
        arrivals_by_category = (
            df.groupby(["category", "day"], dropna=False)
            .size()
            .reset_index(name="n_arrivals")
            .groupby("category")["n_arrivals"]
            .mean()
            .reset_index(name="value")
            .assign(
                outcome="all",
                run=self.model.run_number,
                metric="arrivals_per_day_mean",
            )
        )

        # Mean arrivals per day by response category and outcome
        arrivals_by_category_outcome = (
            df.groupby(["category", "outcome", "day"], dropna=False)
            .size()
            .reset_index(name="n_arrivals")
            .groupby(["category", "outcome"])["n_arrivals"]
            .mean()
            .reset_index(name="value")
            .assign(run=self.model.run_number, metric="arrivals_per_day_mean")
        )

        # Overall utilisation
        utilisation = pd.DataFrame(
            [
                {
                    "run": self.model.run_number,
                    "category": "all",
                    "outcome": "all",
                    "metric": "utilisation_mean",
                    "value": self.utilisation(),
                }
            ]
        )

        return pd.concat(
            [
                response_time,
                allocation_time,
                arrivals_by_category,
                arrivals_by_category_outcome,
                utilisation,
            ],
            ignore_index=True,
        )[["run", "category", "outcome", "metric", "value"]]


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

    # Summary of results across runs by metric, category, outcome
    records = []
    for (metric, category, outcome), group in run.groupby(
        ["metric", "category", "outcome"], dropna=False
    ):
        values = group["value"].dropna()
        # If too few runs with results, don't return confidence intervals
        if len(values) < 2:
            mean = values.mean() if len(values) else float("nan")
            lower, upper = float("nan"), float("nan")
        # Otherwise, return mean and confidence intervals
        else:
            mean = values.mean()
            lower, upper = sms.DescrStatsW(values).tconfint_mean(alpha=0.05)
        records.append(
            {
                "category": category,
                "outcome": outcome,
                "metric": metric,
                "mean": mean,
                "ci_lower": lower,
                "ci_upper": upper,
            }
        )
    overall = pd.DataFrame(records)

    return {
        "patients": patients,
        "run": run,
        "overall": overall,
    }
