"""Patient."""


class Patient:
    """Represents a patient who has called 999.

    Attributes
    ----------
    patient_id : int
        Unique identifier for the patient.
    category : str
        Ambulance response category ("C1", "C2", "C3" or "C4").
    outcome : str
        Call outcome ("see_and_convey" or "see_and_treat").
    call_timestamp : float
        Time at which patient called 999.
    response_time : float
        Time between the call and ambulance arrival on scene.

    """

    PRIORITY_MAP = {"C1": 1, "C2": 2, "C3": 3, "C4": 4}

    def __init__(self, patient_id, category, outcome, call_timestamp):
        """Create instance of Patient.

        Parameters
        ----------
        patient_id : int
            Unique identifier for the patient.
        category : str
            Ambulance response category ("C1", "C2", "C3" or "C4").
        outcome : str
            Call outcome ("see_and_convey" or "see_and_treat").
        call_timestamp : float
            Time at which patient called 999.

        """
        self.patient_id = patient_id
        self.category = category
        self.outcome = outcome
        self.call_timestamp = call_timestamp
        self.response_time = None

    @property
    def priority(self):
        """Numeric priority for resource requests (lower = more urgent)."""
        return self.PRIORITY_MAP[self.category]
