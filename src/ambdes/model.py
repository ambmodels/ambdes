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

    The model generates patient calls, allocates ambulance resources and
    records patients during a single simulation run.
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

        # Calculate maximum possible number of ambulances
        if self.config.ambulance_schedule is None:
            self.max_n_ambulances = self.config.n_ambulances
        else:
            self.max_n_ambulances = max(
                self.config.ambulance_schedule.values()
            )

        # Set up ambulance resource
        self.ambulance = VidigiPriorityStore(
            self.env,
            num_resources=self.max_n_ambulances,
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
                "capacity": self.max_n_ambulances,
            }
        ]

        # Set-up the permit pool (indicating vehicles permitted to attend
        # C2-C4 incidents - i.e., excluding those in restricted send) in a
        # similar way to our set-up for ambulance resources, with support
        # for varying the permits over time. However, we deliberately don't
        # log, as permits are just used as a modelling constraints and don't
        # represent actual ambulance use
        if self.config.permit_schedule is not None:
            self.max_n_permits = max(self.config.permit_schedule.values())
            self.permit = VidigiPriorityStore(
                self.env,
                num_resources=self.max_n_permits,
                label="c2_to_c4_permit",
            )
            self.removed_permits = []
        else:
            self.max_n_permits = None
            self.permit = None
            self.removed_permits = None

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
        """Wait for the resources needed to respond to a patient.

        First samples the time from call receipt to joining the dispatch queue.

        Without restricted send, all patients wait only for an ambulance.

        With restricted send:
        - C1 patients wait only for an ambulance.
        - C2-C4 patients wait for a permit and then an ambulance.

        Parameters
        ----------
        patient : Patient
            Patient requiring an ambulance response.

        """
        # Sample time from call connection to decision for call to be
        # added to stack for response (i.e., joining queue for resource)
        connect_to_queue_time = self.dists["connect_to_queue_time"][
            patient.category
        ].sample()

        yield self.env.timeout(connect_to_queue_time)

        # Log start time of wait for allocation
        self.logger.log_queue(
            entity_id=patient.patient_id, event="ambulance_wait_begins"
        )

        # C1 does not require a permit OR not modelling restricted send
        if patient.category == "C1" or self.permit is None:
            yield from self.use_ambulance(patient)
            return

        # C2-C4 require a non-C1 permit and an ambulance
        # Permit remains held while the patient waits for and uses an ambulance
        # When use_ambulance() finishes, the permit context manager returns it
        # automatically
        with self.permit.request(
            priority=patient.priority, auto_log=False
        ) as permit_request:
            yield permit_request
            yield from self.use_ambulance(patient)

    def use_ambulance(self, patient):
        """Request and use an ambulance for a patient.

        Parameters
        ----------
        patient : Patient
            Patient requesting ambulance transport.

        """
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

    def log_capacity_change(
        self,
        resource,
        removed_units,
        capacity_log,
        action,
        unit,
        remove_target,
    ):
        """Record a capacity change.

        Parameters
        ----------
        resource : VidigiPriorityStore
            Resource pool.
        removed_units : list
            List of resources currently removed from the resource pool.
        capacity_log : list[dict]
            List of dictionaries recording each change in capacity.
        action : str
            Description of the capacity change ("removed" or "returned").
        unit : VidigiResource
            The individual ambulance resource object whose availability
            changed.
        remove_target : int
            Target number of units removed from the maximum resource pool.

        """
        if capacity_log is None:
            return

        capacity_log.append(
            {
                "time": self.env.now,
                "action": action,
                "resource_id": unit.unique_id_attribute,
                "remove_target": remove_target,
                "removed": len(removed_units),
                "capacity": resource.num_resources,
            }
        )

    def update_capacity(
        self,
        resource,
        schedule,
        max_capacity,
        removed_units,
        capacity_log=None,
    ):
        """Apply a resource capacity schedule repeatedly.

        Parameters
        ----------
        resource : VidigiPriorityStore
            Resource pool.
        schedule : dict
            Schedule for capacity changes (keys are times, values are capacity
            of resource).
        max_capacity : int
            Maximum size of the resource pool.
        removed_units : list
            List of resources currently removed from the resource pool.
        capacity_log : list[dict]
            List of dictionaries recording each change in capacity.

        """
        schedule = sorted(schedule.items())
        cycle_start = self.env.now

        while True:
            for index, (time, capacity) in enumerate(schedule):
                # Wait until the next schedule entry starts
                start = cycle_start + time

                if self.env.now < start:
                    yield self.env.timeout(start - self.env.now)

                # Get the next time in schedule - or if at end of schedule,
                # use the ambulance_schedule_period
                if index + 1 < len(schedule):
                    next_time = schedule[index + 1][0]
                else:
                    next_time = self.config.ambulance_schedule_period

                deadline = cycle_start + next_time
                remove_target = max_capacity - capacity

                yield from self.apply_capacity_update(
                    resource=resource,
                    max_capacity=max_capacity,
                    removed_units=removed_units,
                    remove_target=remove_target,
                    deadline=deadline,
                    capacity_log=capacity_log,
                )

                # If the target was reached early, wait for the remainder
                # of the interval
                remaining_time = deadline - self.env.now
                if remaining_time > 0:
                    yield self.env.timeout(remaining_time)

            cycle_start += self.config.ambulance_schedule_period

    def apply_capacity_update(
        self,
        resource,
        max_capacity,
        removed_units,
        remove_target,
        deadline,
        capacity_log=None,
    ):
        """Try to reach capacity target until the specified deadline.

        Parameters
        ----------
        resource : VidigiPriorityStore
            Resource pool.
        max_capacity : int
            Maximum size of the resource pool.
        removed_units : list
            List of resources currently removed from the resource pool.
        remove_target : int
            Target total number of resources removed from the maximum
            resource pool.
        deadline : float
            Simulation time (in minutes) at which to stop attempting to reach
            the removal target. If the required resources are busy, the
            method waits for them to become available only until this time.
        capacity_log : list[dict]
            List of dictionaries recording each change in capacity.

        """
        if not 0 <= remove_target <= max_capacity:
            raise ValueError(
                f"remove_target must be between 0 and "
                f"{max_capacity}; received {remove_target}"
            )

        # Return units if the new target is lower than the
        # number currently removed
        while len(removed_units) > remove_target:
            # Remove final unit from list
            unit = removed_units.pop()
            # Increment the expected number of objects in the store
            # We alter _n_pool_units as num_resources is not changeable
            resource._n_pool_units += 1
            # Add the unit to the store
            resource.put(unit, auto_log=False)
            self.log_capacity_change(
                resource=resource,
                removed_units=removed_units,
                capacity_log=capacity_log,
                action="returned",
                unit=unit,
                remove_target=remove_target,
            )

        # Create a deadline event that can be shared by all removal attempts
        # made during this target period
        remaining_time = max(0, deadline - self.env.now)
        deadline_event = self.env.timeout(remaining_time)

        # Attempt to remove additional units
        while len(removed_units) < remove_target:
            # Do not start another request once the deadline has passed
            if self.env.now >= deadline:
                break

            # Wait for either:
            # 1. An ambulance to become available to remove from store, or-
            # 2. The target interval to end.
            get_event = resource.get_direct(auto_log=False)
            result = yield get_event | deadline_event

            if get_event in result:
                unit = result[get_event]
                # Add the object to the list of removed units
                removed_units.append(unit)
                # Reduce the expected number of objects in the store
                # We alter _n_pool_units as num_resources is not changeable
                resource._n_pool_units -= 1
                self.log_capacity_change(
                    resource=resource,
                    removed_units=removed_units,
                    capacity_log=capacity_log,
                    action="removed",
                    unit=unit,
                    remove_target=remove_target,
                )
            else:
                # The deadline occurred first. Cancel the outstanding request
                # so it can't remove an ambulance later
                resource.cancel_get(get_event)
                break

        self.assert_resource_invariants(
            resource=resource,
            max_capacity=max_capacity,
            removed_units=removed_units,
        )

    def assert_resource_invariants(
        self, resource, max_capacity, removed_units
    ):
        """Check that resource counting is consistent.

        Parameters
        ----------
        resource : VidigiPriorityStore
            Resource pool.
        max_capacity : int
            Maximum size of the resource pool.
        removed_units : list
            List of resources currently removed from the resource pool.

        """
        operational = resource.num_resources
        removed = len(removed_units)
        busy = resource.count
        available = len(resource.items)

        assert max_capacity == operational + removed
        assert operational == busy + available
        assert 0 <= busy <= operational
        assert 0 <= available <= operational
        assert 0 <= removed <= max_capacity

    def run(self):
        """Run the simulation model.

        Starts patient generation and resource capacity processes, then runs
        the simulation for the configured duration.

        """
        # Schedule arrival generator and warm-up
        self.env.process(self.generate_patients())
        self.env.process(self.warm_up())

        # Schedule changing capacity if set
        if self.config.ambulance_schedule is not None:
            self.env.process(
                self.update_capacity(
                    resource=self.ambulance,
                    schedule=self.config.ambulance_schedule,
                    max_capacity=self.max_n_ambulances,
                    removed_units=self.removed_units,
                    capacity_log=self.capacity_log,
                )
            )

        # Varying schedule of number of vehicles permitted for C2-C4 (used to
        # model restricted send)
        if self.config.permit_schedule is not None:
            self.env.process(
                self.update_capacity(
                    resource=self.permit,
                    schedule=self.config.permit_schedule,
                    max_capacity=self.max_n_permits,
                    removed_units=self.removed_permits,
                )
            )

        # Run simulation
        self.env.run(
            until=self.config.warm_up_period
            + self.config.data_collection_period
        )
