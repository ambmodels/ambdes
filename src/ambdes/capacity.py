"""Management of resource capacity that varies over time."""


class CapacitySchedule:
    """Apply a repeating availability schedule to one resource pool."""

    def __init__(
        self,
        env,
        resource,
        schedule,
        period,
        record_changes=False,
        on_units_returned=None,
    ):
        """Initialise CapacitySchedule.

        Parameters
        ----------
        env : simpy.Env
            SimPy environment.
        resource : VidigiPriorityStore
            Resource pool whose capacity varies over time.
        schedule : dict[int, int]
            Repeating availability schedule. Keys are times, in minutes from
            start of the cycle, and values are the number of units that should
            be in the pool at that time.
        period : int
            Length of one full schedule cycle, in minutes. After this time,
            the schedule begins from the beginning.
        record_changes : bool
            Whether to record capacity changes in `capacity_log`.
        on_units_returned : callable | None
            Optional callback triggered when units are returned to the
            resource pool. This can be used to notify other parts of the model
            that newly available capacity may allow further progress.

        """
        self.env = env
        self.resource = resource
        self.schedule = sorted(schedule.items())
        self.period = period
        self.on_units_returned = on_units_returned

        self.validate_schedule()

        # Calculate maximum possible number of resources
        self.max_capacity = max(schedule.values())

        # List to store units when removed from the resource pool
        self.removed_units = []

        # Log of all capacity changes
        if record_changes:
            self.capacity_log = [
                {
                    "time": 0.0,
                    "action": "initial",
                    "resource_id": None,
                    "remove_target": 0,
                    "removed": 0,
                    "capacity": self.max_capacity,
                }
            ]
        else:
            self.capacity_log = None

    def validate_schedule(self):
        """Validate the capacity schedule."""
        if not self.schedule:
            raise ValueError("`schedule` must not be empty.")

        if self.schedule[0][0] != 0:
            raise ValueError("`schedule` must contain a value at time 0.")

        if self.period is None:
            raise ValueError("`period` must be provided.")

        if self.period <= self.schedule[-1][0]:
            raise ValueError(
                "`period` must be greater than the last time in `schedule`."
            )

        if any(capacity < 0 for _, capacity in self.schedule):
            raise ValueError("Schedule capacities must not be negative.")

    def run(self):
        """Apply the capacity schedule repeatedly."""
        cycle_start = self.env.now

        while True:
            for index, (time, capacity) in enumerate(self.schedule):
                # Wait until the next schedule entry starts
                start = cycle_start + time

                if self.env.now < start:
                    yield self.env.timeout(start - self.env.now)

                # Get the next time in schedule - or if at end of schedule,
                # use the ambulance_schedule_period
                if index + 1 < len(self.schedule):
                    next_time = self.schedule[index + 1][0]
                else:
                    next_time = self.period

                deadline = cycle_start + next_time
                remove_target = self.max_capacity - capacity

                yield from self.apply_target(
                    remove_target=remove_target,
                    deadline=deadline,
                )

                # If the target was reached early, wait for the remainder
                # of the interval
                remaining_time = deadline - self.env.now
                if remaining_time > 0:
                    yield self.env.timeout(remaining_time)

            cycle_start += self.period

    def apply_target(self, remove_target, deadline):
        """Try to reach capacity target until the specified deadline.

        Parameters
        ----------
        remove_target : int
            Target total number of resources removed from the maximum
            resource pool.
        deadline : int
            Simulation time (in minutes) at which to stop attempting to reach
            the removal target. If the required resources are busy, the
            method waits for them to become available only until this time.

        """
        if not 0 <= remove_target <= self.max_capacity:
            raise ValueError(
                f"remove_target must be between 0 and "
                f"{self.max_capacity}; received {remove_target}"
            )

        # Return units if target is lower than the number currently removed
        units_returned = self.return_units(remove_target)

        # If provided, trigger the callback provided to be run after units
        # are returned, notifying other parts of the model that there is
        # new capacity that can now be allocated
        if units_returned and self.on_units_returned is not None:
            self.on_units_returned()

        # Remove units if target is lower than the number of units in pool.
        # We use yield from as apply_target() has to wait until remove_units()
        # has finished trying to remove units before it runs the subsequent
        # code. remove_units() is a generator function which pauses at SimPy
        # events while it waits for a unit to become available or a deadline
        # to arrive. So the caller needs to use yield from.
        yield from self.remove_units(
            remove_target=remove_target, deadline=deadline
        )

        self.assert_resource_invariants()

    def return_units(self, remove_target):
        """Return units to the resource pool.

        If the new target is lower than the number currently removed, then
        return units to the resource pool from the `removed_units` list.

        Parameters
        ----------
        remove_target : int
            Target total number of resources removed from the maximum
            resource pool.

        Returns
        -------
        units_returned : bool
            True if units were returned to the resource pool. This is needed
            so we know whether to trigger on_units_returned callback.

        """
        units_returned = False

        while len(self.removed_units) > remove_target:
            # Remove final unit from list
            unit = self.removed_units.pop()

            # Increment the expected number of objects in the store
            # We alter _n_pool_units as num_resources is not changeable
            self.resource._n_pool_units += 1

            # Add the unit to the store
            self.resource.put(unit, auto_log=False)

            # Log the change
            self.record_change(
                action="returned",
                unit=unit,
                remove_target=remove_target,
            )

            units_returned = True

        return units_returned

    def remove_units(self, remove_target, deadline):
        """Remove available units until the target or deadline is reached.

        Parameters
        ----------
        remove_target : int
            Target total number of resources removed from the maximum
            resource pool.
        deadline : int
            Simulation time (in minutes) at which to stop attempting to reach
            the removal target. If the required resources are busy, the
            method waits for them to become available only until this time.

        """
        # Create a deadline event that can be shared by all removal attempts
        # made during this target period
        remaining_time = max(0, deadline - self.env.now)
        deadline_event = self.env.timeout(remaining_time)

        # Attempt to remove additional units
        while len(self.removed_units) < remove_target:
            # Do not start another request once the deadline has passed.
            # Removals are only allowed stricly before the deadline
            if self.env.now >= deadline:
                break

            # Ask the store for one unit. This request may be satisfied
            # immediately if an idle unit is available, or it may remain queued
            # while we wait for a busy unit to be returned.
            get_event = self.resource.get_direct(auto_log=False)

            # Wait for either:
            # 1. An ambulance to become available to remove from store, or-
            # 2. The target interval to end.
            result = yield get_event | deadline_event

            # If we resume at or after the deadline, the removal window is
            # over. In SimPy, get_event may already be triggered and the store
            # already handed us the unit - in which case, we put this back
            # explicitly (instead of just cancelling the request, otherwise
            # the unit can disappear from the store)
            if self.env.now >= deadline:
                if get_event.triggered:
                    self.resource.put(get_event.value, auto_log=False)
                else:
                    self.resource.cancel_get(get_event)
                break

            # If we get here, then we are before the deadline, so a triggered
            # even should count as a genuine removal
            if get_event.triggered:
                unit = get_event.value

                # Add the object to the list of removed units
                self.removed_units.append(unit)

                # Reduce the expected number of objects in the store
                # We alter _n_pool_units as num_resources is not changeable
                self.resource._n_pool_units -= 1

                self.record_change(
                    action="removed",
                    unit=unit,
                    remove_target=remove_target,
                )
                if deadline_event in result and self.env.now >= deadline:
                    break

            else:
                # The get did not trigger, so the deadline must have ended
                # this waiting period before any unit became available.
                self.resource.cancel_get(get_event)
                break

    def record_change(self, action, unit, remove_target):
        """Record a single change in capacity.

        Parameters
        ----------
        action : str
            Description of the capacity change ("removed" or "returned").
        unit : VidigiResource
            The individual ambulance resource object whose availability
            changed.
        remove_target : int
            Target number of units removed from the maximum resource pool.

        """
        if self.capacity_log is None:
            return

        self.capacity_log.append(
            {
                "time": self.env.now,
                "action": action,
                "resource_id": unit.unique_id_attribute,
                "remove_target": remove_target,
                "removed": len(self.removed_units),
                "capacity": self.resource.num_resources,
            }
        )

    def assert_resource_invariants(self):
        """Check that resource counting is consistent."""
        operational = self.resource.num_resources
        removed = len(self.removed_units)
        busy = self.resource.count
        available = len(self.resource.items)

        assert self.max_capacity == operational + removed
        assert operational == busy + available
        assert 0 <= busy <= operational
        assert 0 <= available <= operational
        assert 0 <= removed <= self.max_capacity
