"""Shared constants (used in two or more modules and/or multiple notebooks)."""

DAY_MINUTES = 24 * 60

WEEK_MINUTES = 7 * DAY_MINUTES

# Map from labels used in original data to standard simple area identifiers
AREA_NAME_MAP = {
    "BNSSG": "bnssg",
    "BSW": "bsw",
    "Cornwall": "cornwall",
    "Cornwall/IOS": "cornwall",
    "Devon": "devon",
    "Dorset": "dorset",
    "Gloucestershire": "gloucestershire",
    "Somerset": "somerset",
}

# Unique area identifiers
AREAS = tuple(AREA_NAME_MAP.values())

AREAS_WITH_TRUST = ("trust",) + AREAS
