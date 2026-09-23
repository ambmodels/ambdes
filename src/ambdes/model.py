"""Core simulation model.

Defines the Model class with all simulation logic for a single run. Handles
SimPy processes and records Patient instances, but does not format results or
manage replications.
"""

import simpy
from sim_tools.distributions import DistributionRegistry
from vidigi.logging import EventLogger
from vidigi.resources import VidigiPriorityStore

from .patient import Patient


class Model:
    """Discrete-event simulation model for generating patient calls.

    The model creates one call-generation process per patient category and
    records generated patients during a single simulation run.
    """

    def __init__(self, run_number, config):
        """Initialise the simulation model.

        Parameters
        ----------
        run_number : int
            Simulation run identifier.
        config : object
            Configuration object containing model parameters.

        """
        self.run_number = run_number
        self.config = config

        # Create SimPy environment
        self.env = simpy.Environment()

        # Set up logger
        self.logger = EventLogger(env=self.env, run_number=self.run_number)

        # Set up ambulance resource
        self.ambulance = VidigiPriorityStore(
            self.env,
            num_resources=self.config.n_ambulances,
            label="ambulance",
            logger=self.logger,
        )

        # These will support varying resource capacity
        self.removed_units = []
        self.capacity_log = [
            {
                "time": 0.0,
                "action": "initial",
                "resource_id": None,
                "remove_target": 0,
                "removed": 0,
                "capacity": self.config.n_ambulances,
            }
        ]

        # Set up attribute to store results
        # Patient ID counter is independent of self.patients to ensure
        # patients in warm-up and data collection period each have unique ID
        self.patients = []
        self.patient_id_counter = 0

        # Initialise distributions, with random seed based on run number
        self.dists = DistributionRegistry.create_batch(
            self.config.dist_config,
            main_seed=self.run_number,
            sort=True,
            preserve_structure=True,
        )

    def generate_patients(self):
        """Generate patients."""
        while True:
            # Sample and pass time to next call
            iat = self.dists["call_arrival"].sample(
                simulation_time=self.env.now
            )
            yield self.env.timeout(iat)

            # Sample call type
            category = self.dists["call_category"].sample()

            # Sample whether patient is conveyed or not
            outcome = self.dists["call_outcome"][category].sample()

            # Create a new patient
            self.patient_id_counter += 1
            patient = Patient(
                patient_id=self.patient_id_counter,
                category=category,
                outcome=outcome,
                call_timestamp=self.env.now,
            )
            self.patients.append(patient)

            # Log call time
            self.logger.log_arrival(entity_id=patient.patient_id)

            # Start process of requesting an ambulance
            self.env.process(self.request_ambulance(patient))

    def request_ambulance(self, patient):
        """Simulate ambulance response.

        Parameters
        ----------
        patient : Patient
            Patient requesting ambulance transport.

        """
        # Sample time from call connection to decision for call to be
        # added to stack for response (i.e., joining queue for resource)
        connect_to_queue_time = self.dists["connect_to_queue_time"][
            patient.category
        ].sample()
        yield self.env.timeout(connect_to_queue_time)

        # Request an ambulance (will queue if none available)
        self.logger.log_queue(
            entity_id=patient.patient_id, event="ambulance_wait_begins"
        )
        with self.ambulance.request(
            priority=patient.priority,
            entity_id=patient.patient_id,
            start_event="ambulance_assigned",
            end_event="ambulance_available",
        ) as req:
            yield req

            # Record when patient was assigned an ambulance. This is their
            # allocation time - time from call receipt to resource allocation.
            patient.allocation_time = self.env.now - patient.call_timestamp

            # Sample mobilisation time
            mobilisation_time = self.dists["mobilisation_time"][
                patient.category
            ].sample()
            yield self.env.timeout(mobilisation_time)

            # Sample travel to scene
            time_to_scene = self.dists["time_to_scene"][
                patient.category
            ].sample()
            yield self.env.timeout(time_to_scene)

            # Record response time
            patient.response_time = self.env.now - patient.call_timestamp

            # On-scene time
            on_scene_time = self.dists["on_scene_time"][patient.category][
                patient.outcome
            ].sample()
            yield self.env.timeout(on_scene_time)

            if patient.outcome == "see_and_convey":
                # Sample travel to hospital
                time_to_hospital = self.dists["time_to_hospital"][
                    patient.category
                ].sample()
                yield self.env.timeout(time_to_hospital)

                # Handover time
                handover_time = self.dists["handover_time"][
                    patient.category
                ].sample()
                yield self.env.timeout(handover_time)

            # Wrap up time
            wrap_up_time = self.dists["wrap_up_time"][
                patient.category
            ].sample()
            yield self.env.timeout(wrap_up_time)

        self.logger.log_departure(entity_id=patient.patient_id)

    def warm_up(self):
        """Reset results collection after the warm-up period."""
        if self.config.warm_up_period > 0:
            yield self.env.timeout(self.config.warm_up_period)
            self.patients = []

    def log_capacity_change(self, action, unit, remove_target):
        """Record a change in operational ambulance capacity.

        Parameters
        ----------
        action : str
            Description of the capacity change ("removed" or "returned").
        unit : VidigiResource
            The individual ambulance resource object whose availability
            changed.
        remove_target : int
            Target total number of ambulances removed from the maximum
            resource pool, rather than the number of additional ambulances to
            remove. The target operational capacity is
            `maximum_capacity - remove_target`. For example, with a maximum
            capacity of 20 and `remove_target=5`, the target operational
            capacity is 15. Current capacity of 10 results in five ambulances
            being returned; current capacity of 18 results in three ambulances
            being removed.

        """
        self.capacity_log.append(
            {
                "time": self.env.now,
                "action": action,
                "resource_id": unit.unique_id_attribute,
                "remove_target": remove_target,
                "removed": len(self.removed_units),
                "capacity": self.ambulance.num_resources,
            }
        )

    def update_operational_capacity(self):
        """Set a new operational capacity target."""
        while True:
            # Sample the number of working hours that capacity should be
            # reduced by, relative to the maximum system capacity. Convert
            # this from hours to minutes to a number of resources
            remove_mins = self.dists["reduce_daily_hours"].sample() * 60
            remove_target = round(remove_mins / self.config.capacity_interval)

            # Deadline is time at start of interval + interval length
            deadline = self.env.now + self.config.capacity_interval
            yield from self.apply_capacity_update(
                remove_target=remove_target, deadline=deadline
            )

            # If the target was reached early, wait for the remainder
            # of the interval
            remaining_time = deadline - self.env.now
            if remaining_time > 0:
                yield self.env.timeout(remaining_time)

    def apply_capacity_update(self, remove_target, deadline):
        """Try to reach capacity target until the specified deadline.

        Parameters
        ----------
        remove_target : int
            Target total number of ambulances removed from the maximum
            resource pool.
        deadline : float
            Simulation time (in minutes) at which to stop attempting to reach
            the removal target. If the required ambulances are busy, the
            method waits for them to become available only until this time.

        """
        if not 0 <= remove_target <= self.config.n_ambulances:
            raise ValueError(
                f"remove_target must be between 0 and "
                f"{self.config.n_ambulances}; received {remove_target}"
            )

        # Return ambulances if the new target is lower than the
        # number currently remove.
        while len(self.removed_units) > remove_target:
            # Remove final unit from list
            unit = self.removed_units.pop()
            # Increment the expected number of objects in the store
            # We alter _n_pool_units as num_resources is not changeable
            self.ambulance._n_pool_units += 1
            # Add the unit to the store
            self.ambulance.put(unit, auto_log=False)
            self.log_capacity_change(
                action="returned", unit=unit, remove_target=remove_target
            )

        # Create a deadline event that can be shared by all removal attempts
        # made during this target period
        remaining_time = max(0, deadline - self.env.now)
        deadline_event = self.env.timeout(remaining_time)

        # Attempt to remove additional units
        while len(self.removed_units) < remove_target:
            # Do not start another request once the deadline has passed
            if self.env.now >= deadline:
                break

            # Wait for either:
            # 1. An ambulance to become available to remove from store, or-
            # 2. The target interval to end.
            get_event = self.ambulance.get_direct(auto_log=False)
            result = yield get_event | deadline_event

            if get_event in result:
                unit = result[get_event]
                # Add the object to the list of removed units
                self.removed_units.append(unit)
                # Reduce the expected number of objects in the store
                # We alter _n_pool_units as num_resources is not changeable
                self.ambulance._n_pool_units -= 1
                self.log_capacity_change(
                    action="removed",
                    unit=unit,
                    remove_target=remove_target,
                )
            else:
                # The deadline occurred first. Cancel the outstanding request
                # so it can't remove an ambulance later
                self.ambulance.cancel_get(get_event)
                break

        self.assert_resource_invariants()

    def assert_resource_invariants(self):
        """Check that ambulance resource counting is consistent."""
        original = self.config.n_ambulances
        operational = self.ambulance.num_resources
        removed = len(self.removed_units)
        busy = self.ambulance.count
        available = len(self.ambulance.items)
        assert original == operational + removed
        assert operational == busy + available
        assert 0 <= busy <= operational
        assert 0 <= available <= operational
        assert 0 <= removed <= original

    def run(self):
        """Run the simulation model.

        Starts one patient-generation process for each category and runs the
        simulation until the configured run length.

        """
        # Schedule arrival generator and warm-up
        self.env.process(self.generate_patients())
        self.env.process(self.warm_up())

        # Schedule changing capacity if set
        if self.config.capacity_interval is not None:
            self.env.process(self.update_operational_capacity())

        # Run simulation
        self.env.run(
            until=self.config.warm_up_period
            + self.config.data_collection_period
        )
