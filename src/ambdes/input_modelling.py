import matplotlib.pyplot as plt
from scipy.stats import gamma, weibull_min
import seaborn as sns


def fit_config(time_data, metric_config):
    """Fit distributions for each metric and category from raw time data.

    Parameters
    ----------
    time_data : pd.DataFrame
        Raw time data.
    metric_config : dict
        Dictionary where keys are the times, then sub dict, has dist sim-tools
        name and column mapping to column in raw time data for that time.

    Returns
    -------
    config : dict
        Dictionary in format suitable for sim-tools distribution registry
        with generated parameters for dists by category etc.

    """
    config = {}

    for metric_name, info in metric_config.items():
        dist = info["dist"]
        column = info["column"]
        config[metric_name] = {}

        for cat_number in [1, 2, 3, 4]:
            cat = f"Category {cat_number}"
            cat_sample = time_data.loc[
                time_data["ResponseCategoryGroupLevel2"] == cat, column
            ].dropna()

            # Shift to avoid zeroes for strictly positive distributions
            if dist in ("Weibull", "Gamma") and (cat_sample <= 0).any():
                epsilon = 1e-6
                cat_sample = cat_sample.clip(lower=epsilon)

            if dist == "Weibull":
                shape, loc, scale = weibull_min.fit(cat_sample, floc=0)
                params = {"alpha": shape, "beta": scale}

            elif dist == "Gamma":
                shape, loc, scale = gamma.fit(cat_sample, floc=0)
                params = {"alpha": shape, "beta": scale}

            elif dist in ("Erlang", "Lognormal"):
                params = {
                    "mean": cat_sample.mean(),
                    "stdev": cat_sample.std(),
                }

            config[metric_name][f"C{cat_number}"] = {
                "class_name": dist,
                "params": params,
            }

    return config


def plot_metric_kde(metric, registry, size=10_000):
    """Plot KDE curve by category (C1-C4).

    Sample from the fitted distribution stored in the registry for the given
    metric.

    Parameters
    ----------
    metric : str
        Name of metric to plot.
    registry : simtools.distributions.DistributionRegistry
        Registry instance set-up using the distribution config.
    size : int
        Number of samples to draw from each category's distribution.

    """
    fig, ax = plt.subplots(figsize=(8, 5))

    for cat in ["C1", "C2", "C3", "C4"]:
        samples = registry[metric][cat].sample(size=size)
        sns.kdeplot(samples, lw=2, label=cat, ax=ax)

    ax.set_xlabel(metric)
    ax.set_ylabel("Density")
    ax.legend(title="Category")
    ax.grid(alpha=0.3)
    sns.despine()
    fig.tight_layout()
