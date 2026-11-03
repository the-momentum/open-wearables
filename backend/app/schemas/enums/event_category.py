from enum import StrEnum


class EventCategory(StrEnum):
    """
    Categories of event records (sessions with a start and an end),
    stored in ``event_record.category``.
    """

    WORKOUT = "workout"
    SLEEP = "sleep"
    MEAL = "meal"
    MENSTRUAL_CYCLE = "menstrual_cycle"
    ACTIVITY = "activity"
