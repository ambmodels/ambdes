"""Patient."""

from dataclasses import dataclass


@dataclass
class Patient:
    """Represents a patient who has called 999.

    Attributes
    ----------
    id: int
        Unique identifier for the patient.
    category: int
        Ambulance response category (C1 to C4).
    call_time: float
        Time at which patient called 999.

    """

    id: int
    category: int
    call_time: float
