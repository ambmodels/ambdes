# Data dictionary

The model uses three CSV files:

- `param_arrivals.csv`
- `param_times.csv`
- `param_model.csv`

## `param_arrivals.csv`

Purpose: number of arrivals by day of week and response category.

### Structure

- First column: day of week
- Other columns: response categories (`C1`, `C2`, `C3`, `C4`)
- One row per day

### Columns

- `day`: day of week, e.g. `monday`
- `C1`: number of C1 arrivals on that day
- `C2`: number of C2 arrivals on that day
- `C3`: number of C3 arrivals on that day
- `C4`: number of C4 arrivals on that day

### Example

```csv
,C1,C2,C3,C4
monday,25,310,180,40
tuesday,24,295,170,38
wednesday,24,295,170,38
thursday,24,295,170,38
friday,25,305,178,40
saturday,28,340,200,45
sunday,27,330,195,43
```

## `param_times.csv`

Purpose: mean and standard deviation for each time type and response category.

### Structure

- One row per time type and summary type
- `type` is either `mean` or `sd`
- Categories are stored in columns `C1` to `C4`

### Columns

- `time`: time type
- `type`: summary value, either `mean` or `sd`
- `C1`: value for category C1
- `C2`: value for category C2
- `C3`: value for category C3
- `C4`: value for category C4

### Allowed `time` values

- `travel_to_scene`
- `on_scene`
- `travel_to_hospital`
- `handover`
- `wrap_up`

### Example

```csv
time,type,C1,C2,C3,C4
travel_to_scene,mean,8,10,12,12
travel_to_scene,sd,5,5,5,5
on_scene,mean,44,46,48,50
on_scene,sd,5,5,5,5
travel_to_hospital,mean,8,10,12,12
travel_to_hospital,sd,5,5,5,5
handover,mean,15,22,40,45
handover,sd,5,5,5,5
wrap_up,mean,5,5,5,5
wrap_up,sd,2,2,2,2
```

## `param_model.csv`

Purpose: other model input values used by the simulation.

### Structure

- One row per parameter
- Two columns: parameter name and value

### Columns

- `parameter`: parameter name
- `value`: parameter value

### Parameters

- `resource_hours_per_week`: total ambulance resource hours available per week
- `warm_up_period`: warm-up period
- `data_collection_period`: data collection period
- `n_reps`: number of replications

### Example

```csv
parameter,value
resource_hours_per_week,52000
warm_up_period,100
data_collection_period,500
n_reps,5
```