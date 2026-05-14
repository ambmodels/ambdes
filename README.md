# ambdes: open reproducible discrete-event simulation of ambulance operations

Discrete-event simulation of the ambulance system

View documentation: <https://ambmodels.github.io/ambdes/>

Environment:

```
conda env create --file environment.yaml
conda activate ambdes
```

To render documentation locally:

```
make -C docs render
make -C docs execute
make -C docs preview
```

To run linter and code formatter:

```
ruff check src tests
ruff check --fix src tests
ruff format src tests
```

To run tests:

```
pytest
pytest tests/test_smoke.py && pytest --ignore=tests/test_smoke.py
```

This work is part of the [STARS project](https://pythonhealthdatascience.github.io/stars/), supported by the Medical Research Council [grant number MR/Z503915/1] 

## Citation

To cite this repository, please refer to `CITATION.cff`.

## Acknowledgements

`WarmUpAuditor` based on [Length of warm-up](https://pythonhealthdatascience.github.io/des_rap_book/pages/guide/output_analysis/length_warmup.html) chapter from DES RAP Book, which itself adapts the auditor-based strategy from Tom Monks (2024) Lab 6 Output Analysis in [HPDM097 - Making a difference with health data](https://github.com/health-data-science-OR/stochastic_systems) (MIT Licence).