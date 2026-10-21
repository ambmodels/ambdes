"""Generate regression results.

To run: python tests/regression_results/generate_regression_results.py
"""

import json
from pathlib import Path

import pandas as pd

from ambdes import (
    Model,
    Results,
    Runner,
    SimConfig,
    build_arrival_config,
    run_warm_up_audit,
)

# Paths
INPUT = Path(__file__).parent.parent / "input_data"
OUTPUT = Path(__file__).parent

PATIENT_ARRIVALS = INPUT / "patient_arrivals.csv"
ARRIVALS = INPUT / "param_arrivals.json"
TIMES = INPUT / "param_times.json"

WARM_UP_PERIOD = 10
DATA_COLLECTION_PERIOD = 400
N_REPS = 5
CORES = 1
N_AMBULANCES = 12

# ----------------------------------------------------------------------------
# Arrivals config
# ----------------------------------------------------------------------------

arrivals = pd.read_csv(PATIENT_ARRIVALS)

daily_arrivals = build_arrival_config(arrivals=arrivals, hourly=False)
with open(OUTPUT / "daily_arrivals_config.json", "w") as fp:
    json.dump(daily_arrivals, fp, indent=4)

hourly_arrivals = build_arrival_config(arrivals=arrivals, hourly=True)
with open(OUTPUT / "hourly_arrivals_config.json", "w") as fp:
    json.dump(hourly_arrivals, fp, indent=4)

# ----------------------------------------------------------------------------
# Simulation run
# ----------------------------------------------------------------------------


# Config
def make_config():
    """Create a standard simulation config for regression tests."""
    return SimConfig(
        arrivals_config=ARRIVALS,
        times_config=TIMES,
        warm_up_period=WARM_UP_PERIOD,
        data_collection_period=DATA_COLLECTION_PERIOD,
        n_reps=N_REPS,
        cores=CORES,
        n_ambulances=N_AMBULANCES,
    )


# Single run using Model and Results
model = Model(run_number=0, config=make_config())
model.run()
Results(model).utilisation_df().to_csv(
    OUTPUT / "model_utilisation_df.csv", index=False
)
Results(model).summary_df().to_csv(
    OUTPUT / "model_summary_df.csv", index=False
)

# Multiple replications using Runner
runner = Runner(make_config())
results = runner.run_reps()
results["run"].to_csv(OUTPUT / "runner_run.csv", index=False)
results["overall"].to_csv(OUTPUT / "runner_overall.csv", index=False)

# Warm-up audit
audit = run_warm_up_audit(config=make_config(), interval=30, n_reps=2)
audit.to_csv(OUTPUT / "audit.csv", index=False)
