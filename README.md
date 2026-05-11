# ambdes

Discrete-event simulation of the ambulance system

View documentation: <https://ambmodels.github.io/ambdes/>

Environment:

```
conda env create --file environment.yaml
conda activate ambdes
```

To render documentation locally:

```
quarto render docs
quarto render docs --execute
quarto preview docs
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
