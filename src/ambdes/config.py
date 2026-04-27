"""Model configuration"""

import time

#@dataclass
#class SimConfig:
#    warm_up_duration: int
#    results_collection_duration: int
#    n_replications: int


#@dataclass(frozen=True, kw_only=True)
#class ModelStructure:
#    geography: Literal["none", "county", "lsoa"]
#    arrivals: Literal["overall", "daily"]


class SimConfig:
    def __init__(
        self,
        ambsys_data,
        run_length=100, 
        log_to_console=False,
        log_to_file=False,
        log_file_path=f"{time.strftime('%Y-%m-%d_%H-%M-%S')}.log"
    ):
        self.mean_iat_min = ambsys_data["mean_iat_min"]
        self.mean_response_time_min = ambsys_data["mean_response_time_min"]
        self.mean_handover_time_min = ambsys_data["mean_handover_time_min"]
        self.run_length = run_length
        self.log_to_console = log_to_console
        self.log_to_file = log_to_file
        self.log_file_path = log_file_path

