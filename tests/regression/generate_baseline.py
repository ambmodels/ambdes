"""Generate baseline results for regression testing.

Only run this script when you have intentionally changed model behaviour and
want to update the stored baseline:

    python tests/regression/generate_baseline.py
"""

from pathlib import Path

from ambdes import SimConfig
from ambdes.runner import Runner

AMBSYS_DATA = {
    "mean_iat_min": {"C1": 60.0, "C2": 30.0, "C3": 20.0, "C4": 15.0},
    "mean_handover_time_min": 20.0,
    "p90_handover_time_min": 45.0,
    "sd_handover_time_min": 15.0,
}

RUN_NUMBER = 0
WARM_UP_PERIOD = 0
DATA_COLLECTION_PERIOD = 2_000

PATIENTS_PATH = Path(__file__).parent.joinpath("patients.csv")
RUN_PATH = Path(__file__).parent.joinpath("run.csv")


def main():
    """Generate baseline results and save to CSV."""
    config = SimConfig(
        ambsys_data=AMBSYS_DATA,
        warm_up_period=WARM_UP_PERIOD,
        data_collection_period=DATA_COLLECTION_PERIOD,
    )
    runner = Runner(config=config)

    results = runner.run_single(run_number=RUN_NUMBER)

    results["patients"].to_csv(PATIENTS_PATH, index=False)
    results["run"].to_csv(RUN_PATH, index=False)

    print(f"Saved patients baseline to {PATIENTS_PATH}")
    print(f"Saved run baseline to {RUN_PATH}")


if __name__ == "__main__":
    main()
