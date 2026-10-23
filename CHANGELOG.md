# Changelog

All notable changes to this project are documented.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Dates formatted as YYYY-MM-DD as per [ISO standard](https://www.iso.org/iso-8601-date-and-time-format.html).

## v0.2.0 - 2026-10-23

Model now has arrivals varying by hour of day, resources varying according to shift patterns, which are adjusted for unavailability, meal break and restricted send per hour.

The results have improved - C1 and C2 times a bit higher, but still too quick.

### Added

* **Empirical:** Add `build_empirical_config` and `EmpiricalRunner` (moved from `ambdes-private`).
* **Restricted send:**
    * Add new attribute `restricted_send_schedule` to `SimConfig`, and a new method `create_permit_schedule()` which will create a schedule based on ambulance schedule v.s., restricted send schedule.
    * In `Model`, add permit schedule and initialise permit store. When request an ambulance, if using restricted send, the C2-C4 patients also have to request a permit first. The various capacity change methods have been amended so they can be used both for varying the ambulance pool and the permit pool.
    * Add new class `Dispatcher` which ensures that patients have to get an ambulance and permit at the same time - else you have an issue where e.g., C4 gets a permit but waiting for an ambulance when C2 comes in. It should be synchronous.
* **Tests:** Add more tests for:
    * Restricted send dispatch logic.
    * `SimConfig` permit schedule.
    * Checking `patients` timings match the vidigi log.
    * Varying capacity with `CapacitySchedule`.
    * Regression tests for `build_arrival_config`.
* **Resource reduction:** Add `reduce_ambulances` which can applied to fixed number of ambulances or ambulance schedule schedule.
* **Outputs:** Add all the times to `Patient`, allowing greater exploration when looking at model results.

### Changed

* **Configuration**:
    * Just directly supply the number of ambulances, rather than expecting `SimConfig` to calculate it from the resource hours.
    * Amend `build_arrival_config` so can build by hour-weekday or just weekday.
    * Allow arrives and times to be a dict or path to JSON.
* **Varying capacity:**
    * Switch from sampling capacity reduction at intervals to instead providing a schedule of resource levels.
    * Moved varying capacity logic out of the model and into a new class `CapacitySchedule`.
* **Tests:** Amend tests following refactoring changes.
* **Model:** Separate `Model.__init__()` into several separate methods to make it easier to read and disentangle what is happening.
* **Documentation:** Update following recent changes.

### Fixed

* Upgrade pandas to resolve future warning.
* Fix for bug identified by `test_resource_released_at_deadline_stays_operational`. When release and deadline coincide, we expect the unit to become available at the deadline and remain operational, but this was not happening, at that timepoint it would look like it disappeared.
* Fixed bug in creation of `arrival_config`. Previous approach summed by day then did mean. But this has changed to just a sum overall. As the current approach would not account for different arrival numbers per day.

### Current model structure

![DES model structure in v0.2.0](https://github.com/ambmodels/ambdes/blob/79554b4242c3cdac5ad585e624f57a77ca6b2455/assets/images/ambdes_aggregate.drawio.png?raw=true)

## v0.1.0 - 2026-10-09

First release. This contains a working discrete event simulation model of ambulance operations. It includes code for input modelling and choosing model parameters. It is on a Trust-level.

Note: the model results are currently not quite right - C1 and C2 always seen too quick, while C3 and C4 wait far far far too long (or are never seen). Also, the current adjustment for sickness has been identified as the wrong adjustment - should instead be using resource unavailability. This sickness measure is all sickness (e.g., long-term leave that will have planned cover, and on-the-day sickness which might not).

### Current model structure

![DES model structure in v0.1.0](https://github.com/ambmodels/ambdes/blob/3cb9a0e717d9dd5e852a658bc61e970ace01800f/assets/images/ambdes_aggregate.drawio.png?raw=true)