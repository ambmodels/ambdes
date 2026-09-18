from itertools import cycle
import simpy
from vidigi.resources import VidigiStore
import pandas as pd


class Model:
    def __init__(self):
        """Initialise Model."""
        self.env = simpy.Environment()
        self.n_ambulances = 20
        self.ambulance = VidigiStore(
            env=self.env,
            num_resources=self.n_ambulances,
            label="ambulance",
        )
        self.patient_count = 0
        self.abstracted_units = []
        self.capacity_log = [
            {
                # "run": self.run_number,
                "time": 0.0,
                "action": "initial",
                "resource_id": None,
                "target_removed": 0,
                "abstracted": 0,
                "capacity": self.n_ambulances,
            }
        ]

    def log_capacity_change(self, action, unit, target_removed):
        """Record a change in operational ambulance capacity."""
        self.capacity_log.append(
            {
                # "run": self.run_number,
                "time": self.env.now,
                "action": action,
                "resource_id": unit.unique_id_attribute,
                "target_removed": target_removed,
                "abstracted": len(self.abstracted_units),
                "capacity": self.ambulance.num_resources,
            }
        )

    def generate_patients(self):
        """Generate patients."""
        while True:
            # Pass time between arrivals
            yield self.env.timeout(1.11111)

            # Print time and ID of new arrival
            self.patient_count += 1
            print(f"{self.env.now}: Patient {self.patient_count} arrived")

            # Request an ambulance
            self.env.process(self.request_ambulance(self.patient_count))

    def request_ambulance(self, patient_id):
        """Request ambulance."""
        with self.ambulance.request() as req:
            # Once an ambulance is available, assign to the patient
            yield req
            print(
                f"{self.env.now}: Patient {patient_id} allocated ambulance." +
                f" Now there are {len(self.ambulance.items)} available " +
                "ambulances"
            )

            # Patient spends 15 minutes with ambulance then it is released
            yield self.env.timeout(15)
            print(f"{self.env.now}: Patient {patient_id} finished")

    def abstraction(self):
        """Set a new abstraction target every 10 minutes."""
        # Targets (amounts to remove from maximum overall capacity)
        targets = cycle([18, 0, 10, 5])
        # How often to change targets
        interval = 10

        while True:
            # Get target
            target_removed = next(targets)
            interval_start = self.env.now
            deadline = interval_start + interval

            print(
                f"\n{self.env.now:.2f}: "
                f"New abstraction target={target_removed}; "
                f"currently abstracted={len(self.abstracted_units)}; "
                f"current capacity={self.ambulance.capacity}; "
                f"new target capacity={self.n_ambulances - target_removed}"
            )

            yield from self.apply_abstraction(
                target_removed=target_removed,
                deadline=deadline
            )

            achieved = len(self.abstracted_units)
            shortfall = max(0, target_removed - achieved)

            print(
                f"{self.env.now:.2f}: "
                f"Finished abstraction; "
                f"target={target_removed}, "
                f"achieved={achieved}, "
                f"shortfall={shortfall}, "
                f"capacity={self.ambulance.capacity}, "
                f"busy={self.ambulance.count}, "
                f"available={len(self.ambulance.items)}"
            )

            # If the target was reached early, wait for the remainder
            # of the interval
            remaining_time = deadline - self.env.now

            if remaining_time > 0:
                yield self.env.timeout(remaining_time)

    def apply_abstraction(self, target_removed, deadline):
        """Try to reach the target until the specified deadline."""
        if not 0 <= target_removed <= self.n_ambulances:
            raise ValueError(
                f"target_removed must be between 0 and "
                f"{self.n_ambulances}; received {target_removed}"
            )

        # Return ambulances if the new target is lower than the
        # number currently abstracted.
        while len(self.abstracted_units) > target_removed:
            # Remove final unit from list
            unit = self.abstracted_units.pop()
            # Increment the expected number of objects in the store
            # We alter _n_pool_units as num_resources is not changeable
            self.ambulance._n_pool_units += 1
            # Add the unit to the store
            self.ambulance.put(unit)
            self.log_capacity_change(
                action="returned",
                unit=unit,
                target_removed=target_removed
            )
            print(
                f"{self.env.now:.2f}: "
                f"Returned {unit.unique_id_attribute}; "
                f"abstracted={len(self.abstracted_units)}, "
                f"capacity={self.ambulance.capacity}, "
                f"available={len(self.ambulance.items)}"
            )

        # Create a deadline event that can be shared by all removal attempts
        # made during this target period
        remaining_time = max(0, deadline - self.env.now)
        deadline_event = self.env.timeout(remaining_time)

        # Attempt to remove additional units
        while len(self.abstracted_units) < target_removed:

            # Do not start another request once the deadline has passed
            if self.env.now >= deadline:
                break

            # Wait for either:
            # 1. An ambulance to become available to remove from store, or-
            # 2. The target interval to end.
            get_event = self.ambulance.get_direct()
            result = yield get_event | deadline_event

            if get_event in result:
                unit = result[get_event]
                # Add the object to the list of abstracted units
                self.abstracted_units.append(unit)
                # Reduce the expected number of objects in the store
                # We alter _n_pool_units as num_resources is not changeable
                self.ambulance._n_pool_units -= 1
                self.log_capacity_change(
                    action="removed",
                    unit=unit,
                    target_removed=target_removed,
                )
                print(
                    f"{self.env.now}: Ambulance capacity is now " +
                    f"{self.ambulance.capacity}. There are " +
                    f"{len(self.ambulance.items)} available. num_resources is " +
                    f"{self.ambulance.num_resources}"
                )
            else:
                # The deadline occurred first. Cancel the outstanding request
                # so it can't remove an ambulance later
                self.ambulance.cancel_get(get_event)
                print(
                    f"{self.env.now:.2f}: "
                    f"Stopped trying to reach target "
                    f"{target_removed}; "
                    f"actually abstracted="
                    f"{len(self.abstracted_units)}"
                )
                break
        
        self.assert_resource_invariants()

    def assert_resource_invariants(self):
        """Check that ambulance resource accounting is consistent."""
        original = self.n_ambulances
        operational = self.ambulance.num_resources
        abstracted = len(self.abstracted_units)
        busy = self.ambulance.count
        available = len(self.ambulance.items)

        assert original == operational + abstracted, {
            "original": original,
            "operational": operational,
            "abstracted": abstracted,
        }

        assert operational == busy + available, {
            "operational": operational,
            "busy": busy,
            "available": available,
        }

        assert 0 <= busy <= operational
        assert 0 <= available <= operational
        assert 0 <= abstracted <= original

    def run(self):
        self.env.process(self.generate_patients())
        self.env.process(self.abstraction())
        self.env.run(50)


model = Model()
model.run()
pd.DataFrame(model.capacity_log)