"""Input modelling: functions for importing and processing raw data."""

import numpy as np
import pandas as pd

from ambdes.constants import AREA_NAME_MAP

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------

YEAR = 2025

# "IFT Level 3" and "Other" are marked as C3 as, when we do that, it matches
# up with the original count of Category 3 patients we used to have, when a
# different column with just four groups was provided
CATEGORIES = {
    "Category 1": "C1",
    "Category 2": "C2",
    "Category 3": "C3",
    "IFT Level 3": "C3",
    "Other": "C3",
    "Category 4": "C4",
    "Category 4 999": "C4",
}


# ----------------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------------

def map_icb(source_icb):
    """Map ICB names to simple standardised version.

    Includes defensive programming to check the ICB mapping. Missing values
    and "Unknown ICB" in the raw data are permitted and reported. Unrecognised
    values in the raw data raise an error.

    Parameters
    ----------
    source_icb : pd.Series
        Raw column of ICB names

    Returns
    -------
    mapped_icb : pd.Series
        Standardised simplified column of icb names.

    """
    mapped_icb = source_icb.map(AREA_NAME_MAP)

    # Count how many were missing or unknown in original data, or unmapped
    unknown = source_icb.isna() | source_icb.eq("Unknown ICB")
    unmapped = mapped_icb.isna() & ~unknown

    # Raise an error if any ICB labels were otherwise not mapped
    if unmapped.any():
        raise ValueError(
            f"Unexpected ICB labels:\n{source_icb[unmapped].value_counts()}"
        )

    # Print a success message
    print(f"ICB mapped successfully: {mapped_icb.notna().sum()} rows")

    # Print a record of the number of records with unknown ICB in original data
    if unknown.any():
        print(
            f"Warning: {unknown.sum()} rows have an unknown or missing "
            + "ICB in the provided raw data."
        )

    return mapped_icb


def map_category(source_cat):
    """Map category names to simple standardised version.

    Parameters
    ----------
    source_cat : pd.Series
        Raw column of category names.

    Returns
    -------
    mapped_cat : pd.Series
        Standardised simplified column of categories.

    """
    mapped_cat = source_cat.map(CATEGORIES)

    # Reject any missing or unmapped categories.
    invalid = mapped_cat.isna()

    if invalid.any():
        raise ValueError(
            "Missing or unexpected category labels:\n"
            f"{source_cat[invalid].value_counts(dropna=False)}"
        )

    print(f"Categories mapped successfully: {mapped_cat.notna().sum()} rows")

    return mapped_cat


# ----------------------------------------------------------------------------
# Functions for importing and cleaning data
# ----------------------------------------------------------------------------

def prepare_time_data(path, year=YEAR):
    """Import and clean time data.

    Parameters
    ----------
    path : str | Path
        Path to time data CSV file.
    year : int
        Year the provided data is from.

    Returns
    -------
    time_data : pd.DataFrame
        Processed time data.

    """
    # Import raw time data
    time_data = pd.read_csv(path)

    # Group "See & Convey non ED" and "See & Convey ED" into a single column
    time_data["outcome"] = np.where(
        time_data["C0660_CallOutcomeDetail"] == "See & Treat",
        "see_and_treat",
        np.where(
            time_data["C0660_CallOutcomeDetail"].isin(
                ["See & Convey ED", "See & Convey non ED"]
            ),
            "see_and_convey",
            time_data["C0660_CallOutcomeDetail"],
        ),
    )

    # Add weekday column (0=Monday, 6=Sunday)
    time_data["weekday"] = pd.to_datetime(
        dict(
            year=year,
            month=time_data["IncidentMonth"],
            day=time_data["IncidentDay"],
        )
    ).dt.weekday

    # Add simplified ICB names
    time_data["icb"] = map_icb(time_data["C0722_ICBforCommisisonersReports"])

    # Add simplified category names
    time_data["category"] = map_category(time_data["ResponseCategoryGroupLevel2"])

    return time_data


def prepare_resources_per_incident(path):
    """Import and clean data on resources per incident.

    Parameters
    ----------
    path : str | Path
        Path to the CSV file containing counts of resources per incident.

    Returns
    -------
    pd.DataFrame
        Processed resources data.

    """
    # Import raw data on resources per incident
    resources = pd.read_csv(path)

    # Add simplified ICB names
    resources["icb"] = map_icb(resources["C0722_ICBforCommisisonersReports"])

    # Add simplified category names
    resources["category"] = map_category(resources["ResponseCategoryGroupLevel2"])

    # Exact number of days represented by RESOURCES
    # (This assumes a single year of data)
    days = len(resources[["IncidentMonth", "IncidentDay"]].drop_duplicates())
    if days != 365:
        raise ValueError(
            f"Expected 365 distinct incident dates in resources data, "
            f"but found {days}."
        )

    return resources
