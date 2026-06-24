"""Tools to support choosing the appropriate warm-up length."""

import copy

import numpy as np
import pandas as pd
import plotly.express as px

from .model import Model
from .results import UtilisationCalculator


def run_warm_up_audit(config, interval, n_reps):
    """Run warm-up audit for one or more replications.

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
    dfs = []

    # Make a local copy so the caller's config is not modified
    config = copy.deepcopy(config)

    # Enforce warm_up_period == 0
    config.warm_up_period = 0

    for run_number in range(n_reps):
        model = Model(run_number=run_number, config=config)
        auditor = WarmUpAuditor(model=model, interval=interval)
        auditor.run()
        dfs.append(auditor.to_df())

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
    fig : plotly.graph_objects.Figure
        A Plotly Figure object containing cumulative mean trajectories for
        each run and the overall cumulative mean.

    """
    # Filter to specified response category
    df = audit[audit["metric"] == metric].copy()
    if category is not None:
        df = df[df["category"] == category]

    # Plot cumulative mean for each run
    fig = px.line(data_frame=df, x="time", y="value", line_group="run")
    fig.update_traces(line_color="lightblue")

    # Compute overall cumulative mean and overlay on plot
    overall = df.groupby("time", as_index=False)["value"].mean()
    overall["overall_cumulative"] = overall["value"].expanding().mean()
    overall_fig = px.line(overall, x="time", y="overall_cumulative")
    fig.add_traces(list(overall_fig.select_traces()))

    # Axis labels and layout
    fig.update_layout(
        xaxis_title="Run time (minutes)",
        yaxis_title=f"cumulative_mean_{metric}",
        template="plotly_white",
    )
    return fig
