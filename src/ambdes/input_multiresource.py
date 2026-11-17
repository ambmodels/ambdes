"""Input modelling: multiple resources per incident."""


def mean_job_time(time_data):
    """Find the mean ambulance job time by response category.

    Parameters
    ----------
    time_data : pd.DataFrame
        Time data for the whole trust or filtered to a specific area.

    Returns
    -------
    amb_times : pd.DataFrame
        Dataframe with two columns: response category and mean ambulance time.

    """
    # Columns that represent ambulance resource time on an incident
    amb_time_cols = [
        "C0001_Mobilisation_Duration",
        "C0004_MobilisationToScene_Duration",
        "C0007_OnScene_Duration",
        "C0172_SceneToDestination_Duration",
        "C0012_Handover_Duration",
        "C0171_WrapUp_Duration",
    ]

    # Calculate total ambulance time for each incident
    # min_count=1 prevents completely empty rows from becoming zero
    time_data["amb_time"] = time_data[amb_time_cols].sum(axis=1, min_count=1)

    # Find mean time by response category, converted to minutes
    amb_times = (
        time_data.groupby("category")["amb_time"]
        .mean()
        .reset_index()
        .rename(columns={"amb_time": "mean_amb_time"})
    )
    amb_times["mean_amb_time"] = amb_times["mean_amb_time"] / 60

    return amb_times


def estimate_extra_amb_time(resources, amb_times):
    """Estimate the time spent by extra ambulances on scene.

    Assumes extra ambulances remain occupied for the full job duration too
    (including conveyance) - this is a simplification.

    Parameters
    ----------
    resources : pd.DataFrame
        Resources data, for whole trust or filtered to a particular area.
    amb_times : pd.DataFrame
        Mean job time by response category, as returned by mean_job_time().

    Returns
    -------
    df : pd.DataFrame
        Dataframe with count of ambulances at scene by response category,
        and an estimate of the time spent by any ambulance except the first
        on scene.

    """
    # Count the frequency of requiring X resources for an incident per category
    df = (
        resources.groupby("category")["ResourcesAtScene"]
        .value_counts()
        .reset_index()
    )

    # Add the mean time on a job per response category
    df = df.merge(amb_times, on="category", validate="many_to_one")

    # The model already sends one ambulance per incident, so only count
    # the second, third, fourth, etc. ambulances
    df["extra_amb"] = df["ResourcesAtScene"] - 1

    # From the whole year of data, estimate the time spent by extra ambulances
    # on scene for multi-resource incidents. Assumes additional ambulances
    # remain occupied for the full job duration (inc. conveyance)
    df["extra_amb_time"] = df["extra_amb"] * df["count"] * df["mean_amb_time"]

    return df


def estimate_multiresource_reduction(extra_time, resources_days=365):
    """Estimate the reduction for the model.

    Parameters
    ----------
    extra_time : pd.DataFrame
        Dataframe returned by estimate_extra_amb_time().
    resources_days : int
        Number of days in the dataset.

    Returns
    -------
    float
        Estimated reduction in model resources required.

    """
    # Get total time by response category
    extra_amb_time = extra_time.groupby("category")["extra_amb_time"].sum()

    # Get the extra time per day by dividing by the number
    # of days in the dataset
    extra_amb_time_per_day = extra_amb_time / resources_days

    # Convert additional ambulance-minutes per day into the average
    # number of ambulances concurrently occupied by that workload.
    # One continuously occupied ambulance accounts for 1,440
    # ambulance-minutes per day.
    reduction_by_cat = extra_amb_time_per_day / 1440

    return reduction_by_cat.sum()
