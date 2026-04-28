"""Extract data from AmbSYS."""

import math
from calendar import monthrange

import pandas as pd
from scipy.stats import norm


def ambsys(csv_path, org_code, month, year):
    """Extract AmbSYS timing metrics for a given organisation, month and year.

    Parameters
    ----------
    csv_path : str
        Path to the AmbSYS CSV file.
    org_code : str
        Organisation code used to filter the dataset.
    month : int | str
        Month of interest (provided as number between 1 and 12).
    year : int | str
        Year of interest (e.g., 2025).

    Returns
    -------
    dict
        Nested dictionary containing mean inter-arrival times for C1-C4 calls,
        mean response times for C1-C4 calls, and mean handover time, all
        expressed in minutes.

    """
    # Convert year and month to int, if not already
    year = int(year)
    month = int(month)

    # Extract series for given organisation, year and month
    df = pd.read_csv(csv_path)
    month_df = df.loc[
        (df["Org Code"] == org_code)
        & (df["Year"] == year)
        & (df["Month"] == month)
    ].squeeze()

    if month_df.empty:
        raise ValueError(
            f"No AmbSYS data found for org_code={org_code}, "
            f"year={year}, month={month}."
        )

    # Find minutes in given month
    _, days_in_month = monthrange(year, month)
    min_in_month = days_in_month * 24 * 60

    result = {}

    # Calulate mean inter-arrival times by dividing minutes in month by
    # incident count
    count_codes = {"C1": "A8", "C2": "A10", "C3": "A11", "C4": "A12"}
    result["mean_iat_min"] = {
        category: min_in_month / int(month_df[code])
        for category, code in count_codes.items()
    }

    # Convert mean response times from seconds to minutes
    response_mean_codes = {"C1": "A25", "C2": "A31", "C3": "A34", "C4": "A37"}
    result["mean_response_time_min"] = {
        category: float(month_df[code]) / 60
        for category, code in response_mean_codes.items()
    }

    # Convert 90th centile response times from seconds to minutes
    response_p90_codes = {"C1": "A26", "C2": "A32", "C3": "A35", "C4": "A38"}
    result["p90_response_time_min"] = {
        category: float(month_df[code]) / 60
        for category, code in response_p90_codes.items()
    }

    # Estimate response time SDs (minutes) assuming lognormal response times
    result["sd_response_time_min"] = {}
    for category in response_mean_codes:
        result["sd_response_time_min"][category] = lognormal_sd_from_mean_p90(
            mean=result["mean_response_time_min"][category],
            p90=result["p90_response_time_min"][category],
        )

    # Convert mean handover time from seconds to minutes
    result["mean_handover_time_min"] = float(month_df["A142"]) / 60

    return result


def lognormal_sd_from_mean_p90(mean: float, p90: float) -> float:
    """Approximate SD on the original scale for a lognormal distribution.

    Given the mean and 90th percentile, estimates a reasonable standard
    deviation of a lognormal variable on the original (un-logged) scale.

    Parameters
    ----------
    mean : float
        Arithmetic mean of the lognormal variable (on original scale).
    p90 : float
        90th percentile (on original scale).

    Returns
    -------
    float
        Standard deviation (on the original scale).

    """
    # Mean and 90th percentile must be positive
    if mean <= 0 or p90 <= 0:
        raise ValueError(
            f"mean and p90 must be positive; got mean={mean}, p90={p90}."
        )
    # For a right-skewed distribution like a lognormal, higher percentiles
    # should be larger than the mean. If p90 <= mean, something is wrong
    # with the inputs (or the data is not lognormal-like).
    if p90 <= mean:
        raise ValueError(
            "For a positively skewed lognormal, p90 should exceed mean; "
            f"got mean={mean}, p90={p90}."
        )

    # If you draw the standard normal distribution (mean 0, SD1), z90 is the
    # value on the x-axis where 90% of the distribution lies below it. This is
    # a fixed constant (about 1.28) which we can get using norm.ppf().
    z90 = norm.ppf(0.9)

    # sigma_log is the standard deviation of our distribution on the log scale.
    # mean on original scale is mean = exp(mu_log + 0.5 * sigma_log**2)
    # 90th centile on original scale is p90 = exp(mu_log + z90 * sigma_log)
    # We take logs, subtract one equation from the other to eliminate mu_log,
    # leaving a quadratic equation which can be solved with the quadratic
    # formula.
    #
    # The expression inside the square root is called the "discriminant".
    # If the discriminant is negative, the square root would be imaginary,
    # which means there is NO real lognormal distribution that has BOTH
    # this mean and this p90 at the same time.
    # In other words: the inputs are mathematically inconsistent with a
    # lognormal model.
    disc = z90**2 - 2 * math.log(mean / p90)
    if disc < 0:
        raise ValueError(
            "Mean and p90 are inconsistent with any lognormal distribution; "
            f"got mean={mean}, p90={p90}."
        )
    sigma_log = z90 - math.sqrt(disc)

    # Calculate mean on the log scale
    mu_log = math.log(mean) - 0.5 * sigma_log**2

    # Find variance (and therefore standard deviation) on the log scale
    variance = (math.exp(sigma_log**2) - 1.0) * math.exp(
        2.0 * mu_log + sigma_log**2
    )
    return math.sqrt(variance)
