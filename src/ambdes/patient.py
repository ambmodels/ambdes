"""Patient."""

from dataclasses import dataclass


@dataclass
class Patient:
    """Represents a patient who has called 999.

    Attributes
    ----------
    id: int
        Unique identifier for the patient.
    category: str
        Ambulance response category ("C1", "C2", "C3" or "C4").
    call_time: float
        Time at which patient called 999.

    """

    id: int
    category: str
    call_time: float
