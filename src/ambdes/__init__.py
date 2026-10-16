"""ambdes."""

__version__ = "0.1.0"

# This section allows us to import using e.g. `from ambdes import Model`,
# rather than `from ambdes.model import Model`.

from .capacity import CapacitySchedule
from .choose_warm_up import WarmUpAuditor, plot_warm_up, run_warm_up_audit
from .config import (
    SimConfig,
    convert_keys_to_int,
    convert_resource_hours_to_ambulances,
    resolve_dict,
)
from .dispatcher import Dispatcher, DispatchRequest
from .empirical import EmpiricalRunner, build_empirical_config
from .input_modelling import (
    DISTRIBUTIONS,
    FitDist,
    build_arrival_config,
    fit_config,
    get_dist_params,
    plot_metric_kde,
    plot_observed_fitted,
)
from .model import Model
from .patient import Patient
from .results import Results, UtilisationCalculator, plot_capacity_vs_util
from .runner import Runner

__all__ = [
    "build_arrival_config",
    "build_empirical_config",
    "CapacitySchedule",
    "convert_keys_to_int",
    "convert_resource_hours_to_ambulances",
    "Dispatcher",
    "DispatchRequest",
    "DISTRIBUTIONS",
    "EmpiricalRunner",
    "fit_config",
    "FitDist",
    "get_dist_params",
    "Model",
    "Patient",
    "plot_capacity_vs_util",
    "plot_metric_kde",
    "plot_observed_fitted",
    "plot_warm_up",
    "resolve_dict",
    "Results",
    "run_warm_up_audit",
    "Runner",
    "SimConfig",
    "WarmUpAuditor",
    "UtilisationCalculator",
]
