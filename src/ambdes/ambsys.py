"""Extract data from AmbSYS."""

from calendar import monthrange

import pandas as pd


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
    count_codes = {
        1: "A8",
        2: "A10",
        3: "A11",
        4: "A12",
    }
    result["mean_iat_min"] = {
        category: min_in_month / int(month_df[code])
        for category, code in count_codes.items()
    }

    # Convert mean response times from seconds to minutes
    response_codes = {
        1: "A25",
        2: "A31",
        3: "A34",
        4: "A37",
    }
    result["mean_response_time_min"] = {
        category: float(month_df[code]) / 60
        for category, code in response_codes.items()
    }

    # Convert mean handover time from seconds to minutes
    result["mean_handover_time_min"] = float(month_df["A142"]) / 60

    return result
