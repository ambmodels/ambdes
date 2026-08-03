"""Generate regression results.

To run: python tests/regression_results/generate_regression_results.py
"""

from pathlib import Path

from ambdes import (
    Model,
    Results,
    Runner,
    SimConfig,
    run_warm_up_audit,
)

# Paths
INPUT = Path(__file__).parent.parent / "input_data"
OUTPUT = Path(__file__).parent


# Config
def make_config():
    """Make SimConfig."""
    return SimConfig(
        arrivals_json=INPUT / "param_arrivals.json",
        times_json=INPUT / "param_times.json",
        param_csv=INPUT / "param_model.csv",
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
