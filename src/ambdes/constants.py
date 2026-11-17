"""Shared constants (used in 2+ modules)."""

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
