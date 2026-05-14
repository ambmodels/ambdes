"""Create animation."""

from vidigi.animation import animate_activity_log
from vidigi.utils import EventPosition, create_event_position_df


def generate_animation(model):
    """Generate vidigi animation.

    Parameters
    ----------
    model : Model
        A model instance that has already been executed (model.run()) and
        contains a vidigi logger and config.

    Returns
    -------
    fig : plotly.graph_objs._figure.Figure
        An animated Plotly figure object representing the patient flow.

    """
    event_position_df = create_event_position_df(
        [
            EventPosition(event="arrival", x=50, y=450, label="Arrival"),
            EventPosition(
                event="ambulance_wait_begins",
                x=205,
                y=400,
                label="Waiting for ambulance",
            ),
            EventPosition(
                event="ambulance_arrives",
                x=205,
                y=100,
                label="With ambulance crew",
                resource="n_ambulances",
            ),
            EventPosition(event="depart", x=270, y=70, label="Exit"),
        ]
    )
    fig = animate_activity_log(
        event_log=model.logger.to_dataframe(),
        event_position_df=event_position_df,
        scenario=model.config,
        entity_icon_size=16,
        gap_between_entities=5,
        gap_between_queue_rows=20,
        gap_between_resource_rows=20,
        wrap_queues_at=20,
        wrap_resources_at=20,
    )
    return fig
