"""Input modelling: patient arrivals."""

import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sim_tools.distributions import DistributionRegistry


def get_mean_arrivals(time_df, hourly=False):
    """Mean counts by weekday, category, outcome, and optionally by hour.

    Parameters
    ----------
    time_df : pd.DataFrame
        Dataframe with one row per patient. May be a subset (e.g., filtered
        to a particular area).
    hourly : bool
        Whether to get mean arrivals by hour of day too, or just day of week.

    Returns
    -------
    pd.DataFrame
        Mean arrivals by weekday, category, outcome, and optionally by hour.

    """
    dates = ["IncidentMonth", "IncidentDay", "weekday"]
    groups = ["category", "outcome"]
    if hourly:
        groups = ["IncidentHour"] + groups

    # Create a dataframe with every possible data x category x outcome
    # combination (x hour too if relevant)
    # Start with one row per observed month/day/weekday
    complete = time_df[dates].drop_duplicates()
    for col in groups:
        # For IncidentHour, do rows for each hour - else, do for each
        # distinct category for that column
        values = range(24) if col == "IncidentHour" else time_df[col].unique()
        complete = complete.merge(pd.DataFrame({col: values}), how="cross")

    # Group by the month and day (to keep each date separate), then also
    # by the other specified groups, and count the number of patients
    counts = time_df.groupby(dates + groups).size().reset_index(name="count")

    # Add counts to the template dataframe, and fill NA with 0
    complete = complete.merge(counts, on=dates + groups, how="left")
    complete["count"] = complete["count"].fillna(0)

    # Average counts across dates by the same weekday/category/outcome/hour
    return complete.groupby(["weekday"] + groups)["count"].mean().reset_index()


def build_arrival_config(arrivals, hourly=False):
    """Determine arrival parameters and create config dict.

    Parameters
    ----------
    arrivals : pd.DataFrame
        Mean count of arrivals by weekday, response category and outcome. Must
        also contain incident hour when hourly=True.
    hourly : bool
        Use weekday-hour intervals instead of just weekday intervals.

    Returns
    -------
    dict
        Configuration dictionary.

    """
    if hourly:
        time_index = arrivals["weekday"] * 24 + arrivals["IncidentHour"]
        n_intervals = 168
        interval_minutes = 60
    else:
        time_index = arrivals["weekday"]
        n_intervals = 7
        interval_minutes = 1440

    # Aggregate to counts by response category only
    # Producing dataframe where weekday is index and columns are category
    arrival_df = (
        pd.crosstab(
            time_index,
            arrivals["category"],
            values=arrivals["count"],
            aggfunc="sum",
        )
        .reindex(range(n_intervals))
        .fillna(0)
    )

    category_counts = arrival_df.sum(axis=0)
    category_proportions = category_counts / category_counts.sum()

    # Get count of total arrivals per interval
    arrivals_per_interval = arrival_df.sum(axis=1)

    # Convert to format required by sim_tools NSPPThinning class
    # It requires "t" (timepoint when arrival rate changes) and "mean_iat"
    # (mean inter-arrival time).
    nspp_df = pd.DataFrame(
        {
            "t": range(0, n_intervals * interval_minutes, interval_minutes),
            "mean_iat": interval_minutes / arrivals_per_interval.values,
        }
    )

    # Overall see & convey v.s., see & treat split, varying by response
    # category but pooled across days of week
    outcome_by_category = (
        arrivals.groupby(["category", "outcome"])["count"]
        .sum()
        .unstack("outcome", fill_value=0)
    )
    outcome_proportions = outcome_by_category.div(
        outcome_by_category.sum(axis=1), axis=0
    )

    # Create dictionary in format suitable for sim-tools distribution registry
    dist_config = {
        "call_arrival": {
            "class_name": "NSPPThinning",
            "params": {
                "t": list(nspp_df["t"]),
                "mean_iat": list(nspp_df["mean_iat"]),
            },
        },
        "call_category": {
            "class_name": "DiscreteEmpirical",
            "params": {
                "values": list(category_proportions.index),
                "freq": list(category_proportions.values),
            },
        },
        "call_outcome": {
            cat: {
                "class_name": "DiscreteEmpirical",
                "params": {
                    "values": list(outcome_proportions.columns),
                    "freq": list(outcome_proportions.loc[cat].values),
                },
            }
            for cat in outcome_proportions.index
        },
    }

    # Return the config dictionary
    return dist_config


def plot_simulated_arrivals(
    arrivals_json, hourly=False, n_reps=50, title=None
):
    """Simulate repeated weeks and plot arrival counts by weekday (+ hour).

    Parameters
    ----------
    arrivals_json : str | Path
        Path to the arrivals configuration JSON.
    hourly : bool
        Whether to plot arrival counts by weekday and hour of day, or just
        weekday.
    n_reps : int
        Number of simulated weeks. Plot the mean and 10th-90th percentiles
        of arrival counts across replications.
    title : str
        Title for the plot.

    """
    # Load arrivals configuration
    with open(arrivals_json, encoding="utf-8") as f:
        config = json.load(f)

    # Convert the NSPP parameter into required format for sim-tools
    config["call_arrival"]["params"] = {
        "data": pd.DataFrame(
            {
                "t": config["call_arrival"]["params"]["t"],
                "mean_iat": config["call_arrival"]["params"]["mean_iat"],
            }
        )
    }

    # Create distribution registry
    registry = DistributionRegistry.create_batch(
        config, main_seed=42, preserve_structure=True
    )

    # Sample replications for a week, repeat that n_reps times
    # Capture results either per day or per hour
    bin_minutes = 60 if hourly else 1440
    n_bins = 168 if hourly else 7
    counts = np.zeros((n_reps, n_bins), dtype=int)
    for rep in range(n_reps):
        time = 0
        while True:
            time += registry["call_arrival"].sample(simulation_time=time)
            if time >= (7 * 1440):
                break
            counts[rep, int(time // bin_minutes)] += 1
    x = np.arange(n_bins)

    fig, ax = plt.subplots(figsize=(14, 5) if hourly else (8, 5))

    ax.plot(x, counts.mean(axis=0), marker="o", label="Sample mean")
    ax.fill_between(
        x,
        np.percentile(counts, 10, axis=0),
        np.percentile(counts, 90, axis=0),
        alpha=0.2,
        label="10th-90th percentiles",
    )

    ax.set_title(title)
    ax.set_ylabel("Arrivals")
    ax.legend()

    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    if hourly:
        ticks = np.arange(0, 168, 6)
        ax.set_xticks(ticks)
        ax.set_xticklabels(
            [f"{days[h // 24]} {h % 24:02d}:00" for h in ticks],
            rotation=90,
        )
        ax.set_xlabel("Weekday and hour")
        ax.set_ylabel("Arrivals per hour")
    else:
        ax.set_xticks(x)
        ax.set_xticklabels(days)
        ax.set_xlabel("Weekday")
        ax.set_ylabel("Arrivals per day")

    sns.despine()
    fig.tight_layout()
    plt.show()
