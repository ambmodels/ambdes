"""ambdes."""

__version__ = "0.2.0"

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
from .inputs_shifts import(
    AREAS,
    create_availability_schedule,
    create_schedules,
    create_weekly_schedule,
    load_resources,
    load_shifts,
    plot_schedule,
    plot_and_save_schedules,
    save_schedule,
    subtract_unavailability,
)
from .model import Model
from .patient import Patient
from .results import Results, UtilisationCalculator, plot_capacity_vs_util
from .runner import Runner

__all__ = [
    "AREAS",
    "build_arrival_config",
    "build_empirical_config",
    "CapacitySchedule",
    "convert_keys_to_int",
    "convert_resource_hours_to_ambulances",
    "create_weekly_schedule",
    "create_availability_schedule",
    "create_schedules",
    "Dispatcher",
    "DispatchRequest",
    "DISTRIBUTIONS",
    "EmpiricalRunner",
    "fit_config",
    "FitDist",
    "get_dist_params",
    "load_resources",
    "load_shifts",
    "Model",
    "Patient",
    "plot_capacity_vs_util",
    "plot_metric_kde",
    "plot_observed_fitted",
    "plot_and_save_schedules",
    "plot_schedule",
    "plot_warm_up",
    "resolve_dict",
    "Results",
    "run_warm_up_audit",
    "Runner",
    "save_schedule",
    "subtract_unavailability",
    "SimConfig",
    "WarmUpAuditor",
    "UtilisationCalculator",
]
