"""Tools to support choosing the appropriate warm-up length."""

import copy

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from joblib import Parallel, cpu_count, delayed
from matplotlib.lines import Line2D

from .model import Model
from .results import UtilisationCalculator


def run_single_audit(config, interval, run_number):
    """Run warm-up audit for a single replication.

    Parameters
    ----------
    config : object
        Configuration object containing model parameters.
    interval : int
        Audit frequency in minutes.
    run_number : int
        Run number.

    Returns
    -------
    pd.DataFrame
        Audit results with one row per time, category and metric.

    """
    model = Model(run_number=run_number, config=config)
    auditor = WarmUpAuditor(model=model, interval=interval)
    auditor.run()
    return auditor.to_df()


def run_warm_up_audit(config, interval, n_reps):
    """Run warm-up audit for one or more replications (can run in parallel).

    Parameters
    ----------
    config : object
        Configuration object containing model parameters.
    interval : int
        Audit frequency in minutes.
    n_reps : int, optional
        Number of replications to run.

    Returns
    -------
    pd.DataFrame
        Audit results with one row per run, time, category and metric.

    """
    # Make a local copy so the caller's config is not modified
    config = copy.deepcopy(config)

    # Enforce warm_up_period == 0
    config.warm_up_period = 0

    if config.cores == 1:
        dfs = [run_single_audit(config, interval, i) for i in range(n_reps)]
    else:
        # Check the requested number of cores is possible on machine
        valid_cores = [-1] + list(range(1, cpu_count()))
        if config.cores not in valid_cores:
            raise ValueError(
                f"Invalid cores: {config.cores}. Must be one of: "
                + f"{valid_cores}."
            )
        # Execute warm-up audit in parallel
        dfs = Parallel(n_jobs=config.cores)(
            delayed(run_single_audit)(config, interval, i)
            for i in range(n_reps)
        )

    return pd.concat(dfs, ignore_index=True)


class WarmUpAuditor:
    """Warm-up auditor - records cumulative mean results at intervals.

    Attributes
    ----------
    model : Model
        A model instance that has not yet been run (model.run()).
    interval : int
        Audit frequency in minutes.
    audit_results : list
        List of dictionaries containing audit snapshots at each interval.
    response_categories : list
        List of response categories.

    """

    def __init__(self, model, interval):
        """Initialise WarmUpAuditor.

        Parameters
        ----------
        model : Model
            A model instance that has not yet been run (model.run()).
        interval : int
            Audit frequency in minutes.

        """
        self.model = model
        self.interval = interval
        self.audit_results = []
        self.response_categories = ["C1", "C2", "C3", "C4"]

        if self.model.config.warm_up_period != 0:
            raise ValueError(
                "WarmUpAuditor requires model.config.warm_up_period == 0."
            )

    def _audit_model(self):
        """Audit the model at specified intervals."""
        while True:
            # Response time (by category)
            response_times = self._get_response_times()
            for category, value in response_times.items():
                self.audit_results.append(
                    {
                        "time": self.model.env.now,
                        "category": category,
                        "metric": "response_time",
                        "value": value,
                    }
                )
            # Mean utilisation (overall - not category-specific)
            self.audit_results.append(
                {
                    "time": self.model.env.now,
                    "category": "all",
                    "metric": "utilisation",
                    "value": self._get_utilisation(),
                }
            )
            yield self.model.env.timeout(self.interval)

    def _get_response_times(self):
        """Compute mean response times for patients seen by current time.

        Returns
        -------
        results : dict
            Dictionary with mean response time by response category.

        """
        categories = ["C1", "C2", "C3", "C4"]
        results = {}

        for category in categories:
            values = [
                p.response_time
                for p in self.model.patients
                if p.category == category and p.response_time is not None
            ]
            results[category] = np.mean(values) if values else np.nan

        return results

    def _get_utilisation(self):
        """Compute cumulative mean utilisation up to current time.

        Returns
        -------
        float
            Mean utilisation.

        """
        return UtilisationCalculator.from_model_at_time(
            self.model, self.model.env.now
        ).mean_utilisation()

    def run(self):
        """Run auditor alongside simulation model."""
        self.model.env.process(self._audit_model())
        self.model.run()

    def to_df(self):
        """Convert audit results to dataframe.

        Returns
        -------
        df : pd.DataFrame
            Audit results with one row per run, time, and category.

        """
        df = pd.DataFrame(self.audit_results)
        df["run"] = self.model.run_number
        return df


def plot_warm_up(audit, metric, category=None):
    """Plot warm-up trajectories for one metric and response category.

    Shows one line per run for the cumulative mean trajectories, and overlays
    the overall cumulative mean across runs.

    Parameters
    ----------
    audit : pd.DataFrame
        Warm-up audit results.
    metric: str
        Name of the performance measure to visualise.
    category : str
        Response category to plot.

    Returns
    -------
    fig : matplotlib.figure.Figure
        A Matplotlib Figure containing cumulative mean trajectories for
        each run and the overall cumulative mean.
    ax : matplotlib.axes.Axes
        The Matplotlib Axes object.

    """
    # Filter to specified response category
    df = audit[audit["metric"] == metric].copy()
    if category is not None:
        df = df[df["category"] == category]

    fig, ax = plt.subplots()

    # Convert time to days
    df["time"] = df["time"] / 1440

    # Plot cumulative mean for each run
    for _, run_df in df.groupby("run"):
        ax.plot(
            run_df["time"],
            run_df["value"],
            color="lightblue",
            alpha=0.8,
        )

    # Compute overall cumulative mean and overlay on plot
    overall = df.groupby("time", as_index=False)["value"].mean()
    overall["overall_cumulative"] = overall["value"].expanding().mean()

    ax.plot(
        overall["time"],
        overall["overall_cumulative"],
        color="C0",
        linewidth=2,
        label="Overall cumulative mean",
    )

    # Axis labels and layout
    ax.set_xlabel("Run time (days)")
    ax.set_ylabel(f"cumulative_mean_{metric}_{category}")
    legend_handles = [
        Line2D(
            [0],
            [0],
            color="lightblue",
            lw=2,
            label="Cumulative mean from individual runs",
        ),
        Line2D([0], [0], color="C0", lw=2, label="Overall cumulative mean"),
    ]
    ax.legend(handles=legend_handles)
    fig.tight_layout()

    return fig, ax
