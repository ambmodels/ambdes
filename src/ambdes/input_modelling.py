"""Input modelling."""

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from scipy.stats import beta, gamma, ks_2samp, weibull_min
from sim_tools.distributions import (
    Beta,
    Erlang,
    Exponential,
    Gamma,
    Lognormal,
    Normal,
    Triangular,
    Uniform,
    Weibull,
)

DISTRIBUTIONS = [
    "beta",
    "erlang",
    "exponential",
    "gamma",
    "lognormal",
    "normal",
    "triangular",
    "uniform",
    "weibull",
]

CONVEY_COL = "C0660_CallOutcomeDetail"
CONVEY_LABELS = {
    "convey": ["See & Convey ED", "See & Convey non ED"],
    "not_convey": ["See & Treat"],
}


class FitDist:
    """Fit distributions using sim-tools and compare samples to real data.

    Attributes
    ----------
    data : pd.Series
        Time data to fit distribution to.
    mean : float
        Mean of `data`.
    stdev : float
        Standard deviation of `data`.
    min : float
        Minimum value of `data`.
    max : float
        Maximum value of `data`.
    mode : float
        Mode of `data`. If there are several modes, it chooses the middle one.

    """

    def __init__(self, metric, df):
        """Create instance of FitDist.

        Parameters
        ----------
        metric : str
            Name of metric.
        df : pd.DataFrame
            Time data.

        """
        self.data = df[metric].dropna()

        self.mean = self.data.mean()
        self.stdev = self.data.std()
        self.min = self.data.min()
        self.max = self.data.max()

        # If multiple modes, choose the middle one
        modes = self.data.mode()
        self.mode = modes.iloc[len(modes) // 2]

    def fit(self, dist, seed):
        """Create a sim-tools distribution instance.

        Parameters
        ----------
        dist : str
            Lower case name of distribution object in sim-tools to create.
        seed : int
            Random seed.

        """
        if dist == "exponential":
            return Exponential(mean=self.mean, random_seed=seed)

        if dist == "lognormal":
            return Lognormal(
                mean=self.mean, stdev=self.stdev, random_seed=seed
            )

        if dist == "normal":
            return Normal(
                mean=self.mean, sigma=self.stdev, minimum=0, random_seed=seed
            )

        if dist == "uniform":
            return Uniform(low=self.min, high=self.max, random_seed=seed)

        if dist == "triangular":
            mode = self.mode
            if mode <= self.min:
                epsilon = 1e-6
                mode = self.min + epsilon
            return Triangular(
                low=self.min, mode=mode, high=self.max, random_seed=seed
            )

        if dist == "erlang":
            return Erlang(mean=self.mean, stdev=self.stdev, random_seed=seed)

        # Gamma and Weibull are stricly positive distributions, so we shift
        # the data a tiny amount to avoid zeroes
        if dist == "weibull" or dist == "gamma":
            fit_data = self.data
            if (fit_data <= 0).any():
                epsilon = 1e-6
                fit_data = fit_data.clip(lower=epsilon)
            if dist == "weibull":
                shape, loc, scale = weibull_min.fit(fit_data, floc=0)
                return Weibull(alpha=shape, beta=scale, random_seed=seed)
            if dist == "gamma":
                shape, loc, scale = gamma.fit(fit_data, floc=0)
                return Gamma(alpha=shape, beta=scale, random_seed=seed)

        if dist == "beta":
            # Normalise data to [0, 1]
            range_ = self.max - self.min
            normalized = (self.data - self.min) / range_
            epsilon = 1e-6
            normalized_adj = normalized.clip(lower=epsilon, upper=1 - epsilon)
            a, b, loc, scale = beta.fit(normalized_adj, floc=0, fscale=1)
            return Beta(
                alpha1=a,
                alpha2=b,
                lower_bound=self.min,
                upper_bound=self.max,
                random_seed=seed,
            )

        raise ValueError(
            f"Unable to fit {dist} - not supported in FitDist code."
        )

    def fit_and_compare(
        self,
        dists=DISTRIBUTIONS,
        xmax=200,
        seed=42,
    ):
        """Fit distributions and compare.

        Parameters
        ----------
        dists : str | list
            Distribution name/s.
        xmax : int
            Max for x axis in plot to help view easier with long tails.
        seed : int
            Random seed.

        """
        if isinstance(dists, str):
            dists = [dists]

        results = {}

        # Fit distribution, take sample, and calculate Kolmogorov-Smirnov
        for dist_name in dists:
            fitted = self.fit(dist_name, seed=seed)
            sample = fitted.sample(size=len(self.data))
            ks_statistic = ks_2samp(self.data, sample).statistic
            results[dist_name] = {
                "fitted": fitted,
                "sample": sample,
                "ks_statistic": ks_statistic,
            }

        # Sort dict items by ks_statistic (ascending: best fit first)
        sorted_results = dict(
            sorted(results.items(), key=lambda item: item[1]["ks_statistic"])
        )

        # Create dataframe with KS statistics
        ks_table = pd.DataFrame(
            {
                "Distribution": list(sorted_results.keys()),
                "ks_statistic": [
                    v["ks_statistic"] for v in sorted_results.values()
                ],
            }
        )
        print(ks_table)

        # Plot in the same sorted order
        for _, v in sorted_results.items():
            plot_observed_fitted(
                data=self.data,
                sample=v["sample"],
                kind="hist",
                xmax=xmax,
                title=v["fitted"],
            )


def plot_observed_fitted(data, sample, kind="hist", xmax=200, title=""):
    """Plot overlaid comparison of observed vs fitted data.

    Parameters
    ----------
    data : array-like
        Observed data values.
    sample : array-like
        Sampled/fitted distribution values.
    kind : str
        Either "kde" (density curve) or "hist" (plain count-based histogram).
    xmax : int or None
        X-axis limit for a second, optional cropped copy of the plot.
    title : str
        Title.

    """
    df_plot = pd.concat(
        [
            pd.DataFrame({"value": data, "source": "Observed"}),
            pd.DataFrame({"value": sample, "source": "Fitted"}),
        ],
        ignore_index=True,
    )

    plot_fn = sns.histplot if kind == "hist" else sns.kdeplot
    plot_kwargs = dict(data=df_plot, x="value", hue="source", fill=True)
    if kind == "kde":
        plot_kwargs["common_norm"] = False
    if kind == "hist":
        plot_kwargs["bins"] = 100

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    plot_fn(**plot_kwargs, ax=axes[0])
    axes[0].set_title("Full range")
    axes[0].set_ylabel("Count" if kind == "hist" else "Density")

    cropped_kwargs = dict(plot_kwargs)
    if kind == "hist":
        cropped_kwargs["bins"] = min(xmax, 100)
        cropped_kwargs["binrange"] = (0, xmax)
    plot_fn(**cropped_kwargs, ax=axes[1])
    axes[1].set_xlim(0, xmax)
    axes[1].relim()
    axes[1].autoscale_view(scalex=False, scaley=True)
    axes[1].set_title(f"Cropped to 0-{xmax}")
    axes[1].set_ylabel("Count" if kind == "hist" else "Density")

    fig.suptitle(title)

    fig.tight_layout()
    plt.show()


def fit_dist(dist, data, time_data_unit):
    """Generate the required parameters for the chosen distribution.

    Parameters
    ----------
    dist : str
        Name of distribution to use, as named in sim-tools.
    data : pd.Series
        Time series data sample to get parameters for.
    time_data_unit : str
        Whether the provided raw data is in seconds ("s") or minutes ("m").

    Returns
    -------
    dict
        Dictionary in format suitable for sim-tools distribution registry.

    """
    # If provided data is in seconds, convert to minutes (as the
    # simulation model time unit is minutes)
    if time_data_unit == "s":
        data = data / 60

    # Shift to avoid zeroes for strictly positive distributions
    if dist in ("Weibull", "Gamma") and (data <= 0).any():
        epsilon = 1e-6
        data = data.clip(lower=epsilon)

    if dist == "Weibull":
        shape, loc, scale = weibull_min.fit(data, floc=0)
        params = {"alpha": shape, "beta": scale}

    elif dist == "Gamma":
        shape, loc, scale = gamma.fit(data, floc=0)
        params = {"alpha": shape, "beta": scale}

    elif dist in ("Erlang", "Lognormal"):
        params = {
            "mean": data.mean(),
            "stdev": data.std(),
        }

    return {"class_name": dist, "params": params}


def fit_config(
    time_data,
    time_data_unit,
    metric_config
):
    """Fit distributions for each metric and category from raw time data.

    If specified in `metric_config`, times may be additional split depending
    on whether patients were conveyed (see & convey) or not (see & treat).

    Parameters
    ----------
    time_data : pd.DataFrame
        Raw time data.
    time_data_unit : str
        Whether the provided raw data is in seconds ("s") or minutes ("m").
    metric_config : dict
        Dictionary where keys are the times, then sub dict, has dist sim-tools
        name and column mapping to column in raw time data for that time.

    Returns
    -------
    config : dict
        Dictionary in format suitable for sim-tools distribution registry
        with generated parameters for dists by category etc.

    """
    if time_data_unit not in ["s", "m"]:
        raise ValueError(
            f"Invalid time data unit: {time_data_unit}. Must be 's' or 'm'."
        )

    config = {}

    # Loop through the config dictionary
    for metric_name, info in metric_config.items():
        config[metric_name] = {}

        # Check if the distribution is split by conveyance status or not
        split = "convey" in info and "not_convey" in info

        for cat_number in [1, 2, 3, 4]:
            cat = f"Category {cat_number}"
            key = f"C{cat_number}"
            cat_mask = time_data["ResponseCategoryGroupLevel2"] == cat

            # Distributions are fit separately by conveyance status
            if split:
                config[metric_name][key] = {}
                for label, sub_info in info.items():
                    # Get the relevant distribution, column and labels
                    dist = sub_info["dist"]
                    column = sub_info["column"]
                    outcomes = CONVEY_LABELS[label]
                    # Filter to that column + that conveyance status
                    sample = time_data.loc[
                        cat_mask & time_data[CONVEY_COL].isin(outcomes),
                        column
                    ].dropna()
                    # Get distribution parameters
                    config[metric_name][key][label] = fit_dist(
                        dist=dist, data=sample, time_data_unit=time_data_unit
                    )
            # For other metrics, just one distribution, regardless of whether
            # patient was conveyed or not
            else:
                dist = info["dist"]
                column = info["column"]
                sample = time_data.loc[cat_mask, column].dropna()
                config[metric_name][key] = fit_dist(
                    dist=dist, data=sample, time_data_unit=time_data_unit
                )

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
        # Filter to the dictionary entry for that metric and category
        cat_entry = registry[metric][cat]

        # Split by sub-category (i.e., convey / not convey)
        if isinstance(cat_entry, dict):
            for label, dist in cat_entry.items():
                samples = dist.sample(size=size)
                sns.kdeplot(samples, lw=2, label=f"{cat} ({label})", ax=ax)
        # If not, just sample directly
        else:
            samples = cat_entry.sample(size=size)
            sns.kdeplot(samples, lw=2, label=cat, ax=ax)

    ax.set_xlabel(f"{metric} (minutes)")
    ax.set_ylabel("Density")
    ax.legend(title="Category")
    ax.grid(alpha=0.3)
    sns.despine()
    fig.tight_layout()
