"""Input modelling: patient arrivals."""

import pandas as pd


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
        .unstack("outcome")
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
