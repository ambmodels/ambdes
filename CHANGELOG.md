# Changelog

All notable changes to this project are documented.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Dates formatted as YYYY-MM-DD as per [ISO standard](https://www.iso.org/iso-8601-date-and-time-format.html).

## v0.1.0 - 2026-10-09

First release. This contains a working discrete event simulation model of ambulance operations. It includes code for input modelling and choosing model parameters. It is on a Trust-level.

Note: the model results are currently not quite right - C1 and C2 always seen too quick, while C3 and C4 wait far far far too long (or are never seen). Also, the current adjustment for sickness has been identified as the wrong adjustment - should instead be using resource unavailability. This sickness measure is all sickness (e.g., long-term leave that will have planned cover, and on-the-day sickness which might not).

The current simulation model structure is:

![DES model structure in v0.1.0](https://github.com/ambmodels/ambdes/blob/3cb9a0e717d9dd5e852a658bc61e970ace01800f/assets/images/ambdes_aggregate.drawio.png?raw=true)