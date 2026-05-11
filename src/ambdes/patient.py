"""Patient."""


class Patient:
    """Represents a patient who has called 999.

    Attributes
    ----------
    patient_id : int
        Unique identifier for the patient.
    category : str
        Ambulance response category ("C1", "C2", "C3" or "C4").
    call_timestamp : float
        Time at which patient called 999.
    response_time : float
        Time between the call and ambulance arrival on scene.
    travel_time_to_hospital : float
        Time taken to transport the patient from the scene to hospital.
    handover_time : float
        Time spent handing over the patient to hospital staff (including any
        handover delays from queueing at hospital).

    """

    def __init__(self, patient_id, category, call_timestamp):
        """Create instance of Patient.

        Parameters
        ----------
        patient_id : int
            Unique identifier for the patient.
        category : str
            Ambulance response category ("C1", "C2", "C3" or "C4").
        call_timestamp : float
            Time at which patient called 999.

        """
        self.patient_id = patient_id
        self.category = category
        self.call_timestamp = call_timestamp

        self.response_time = None
        self.travel_time_to_hospital = None
        self.handover_time = None
