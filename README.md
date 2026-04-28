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
quarto preview docs
```

To run linter and code formatter:

```
ruff check src tests
ruff check --fix src tests
ruff format src tests
```

This work is part of the [STARS project](https://pythonhealthdatascience.github.io/stars/), supported by the Medical Research Council [grant number MR/Z503915/1] 
