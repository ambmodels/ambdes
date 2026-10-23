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
    connect_to_queue_time : float
        Time from call to joining the dispatch queue.
    allocation_time : float
        Time from call to ambulance allocation.
    mobilisation_time : float
        Time from ambulance allocation to departure.
    time_to_scene : float
        Travel time to scene.
    response_time : float
        Time from the call to ambulance arrival on scene.
    on_scene_time : float
        TIme spent at the scene.
    time_to_hospital : float
        Travel time from the scene to the destination.
    handover_time : float
        Time spent handing over the patient at the destination.
    wrap_up_time : float
        Time spent preparing the crew and ambulance for the next call.

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
        self.connect_to_queue_time = None
        self.allocation_time = None
        self.mobilisation_time = None
        self.time_to_scene = None
        self.response_time = None
        self.on_scene_time = None
        self.time_to_hospital = None
        self.handover_time = None
        self.wrap_up_time = None

    @property
    def priority(self):
        """Numeric priority for resource requests (lower = more urgent)."""
        return self.PRIORITY_MAP[self.category]
