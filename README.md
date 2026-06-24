# ambdes: open reproducible discrete-event simulation of ambulance operations

This repository contains a discrete-event simulation (DES) model of ambulance operations, with supporting notebooks and documentation.

Documentation: <https://ambmodels.github.io/ambdes/>

## Setup

An environment file is created, which can be used to set-up an environment with `conda` or `mamba`.

```
mamba env create --file environment.yaml
mamba activate ambdes
```

## Repository structure

* `src/` - core simulation code.
* `notebooks/` - example workflows and experiments.
* `data/` - input data used by the notebooks.
* `tests/` - test suite.
* `docs/` - source for the Quarto documentation site <https://ambmodels.github.io/ambdes/>.

## Running the notebooks

After setting up the environment, open and run the notebooks in `notebooks/`.

## Documentation (local build)

```
make -C docs render
make -C docs preview
```

## Linting and formatting

```
ruff format src tests
ruff check --fix src tests
```

## Tests

There is presently just a simple smoke test, which performs a very short model run to see if it can run without error and at least one patient arrives.

More tests will be added as part of verification of the model code.

```
pytest
```

## Citation

See `CITATION.cff`.

## Acknowledgements

This work is part of the [STARS project](https://pythonhealthdatascience.github.io/stars/), supported by the Medical Research Council [grant number MR/Z503915/1] 

`WarmUpAuditor` based on [Length of warm-up](https://pythonhealthdatascience.github.io/des_rap_book/pages/guide/output_analysis/length_warmup.html) chapter from DES RAP Book, which itself adapts the auditor-based strategy from Tom Monks (2024) Lab 6 Output Analysis in [HPDM097 - Making a difference with health data](https://github.com/health-data-science-OR/stochastic_systems) (MIT Licence).