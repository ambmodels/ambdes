"""Generate regression results.

To run: python tests/regression_results/generate_regression_results.py
"""

from pathlib import Path

from ambdes import (
    ArrivalConfig,
    Model,
    ModelConfig,
    Results,
    Runner,
    SimConfig,
    TimesConfig,
    run_warm_up_audit,
)

# Paths
INPUT = Path(__file__).parent.parent / "input_data"
OUTPUT = Path(__file__).parent

# Config
arrival_config = ArrivalConfig(arrival_csv=INPUT / "param_arrivals.csv")
times_config = TimesConfig(times_csv=INPUT / "param_times.csv")
model_config = ModelConfig(param_csv=INPUT / "param_model.csv")
config = SimConfig(
    arrival_config=arrival_config,
    times_config=times_config,
    model_config=model_config,
)

# Single run using Model and Results
model = Model(run_number=0, config=config)
model.run()
Results(model).patient_df().to_csv(OUTPUT / "model_patient_df.csv")
Results(model).utilisation_df().to_csv(OUTPUT / "model_utilisation_df.csv")
Results(model).summary_df().to_csv(OUTPUT / "model_summary_df.csv")

# Multiple replications using Runner
runner = Runner(config)
results = runner.run_reps()
results["patients"].to_csv(OUTPUT / "runner_patients.csv")
results["run"].to_csv(OUTPUT / "runner_run.csv")
results["overall"].to_csv(OUTPUT / "runner_overall.csv")

# Warm-up audit
audit = run_warm_up_audit(config=config, interval=30, n_reps=2)
audit.to_csv(OUTPUT / "audit.csv")
