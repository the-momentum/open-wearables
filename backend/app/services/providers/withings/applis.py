"""Route Withings notification applis to the fetch domain that handles them.

``appli`` notification categories and ``meastype`` measure codes are distinct
numeric namespaces. The domain names are ours, not Withings' — they select which
ingestion call a notification triggers.
"""

from typing import Literal

from app.schemas.providers.withings import PROFILE_CHANGE_APPLI

Domain = Literal["measures", "sleep", "activity_workouts"]

APPLI_DOMAIN: dict[int, Domain] = {
    1: "measures",  # Body and Weight
    2: "measures",  # Temperature
    4: "measures",  # Blood Pressure and Heart Rate
    16: "activity_workouts",  # Activity and workouts
    44: "sleep",
    58: "measures",  # Glucose
}

# Appli 46 is subscribed too, but handled before domain routing: it carries no data.
SUBSCRIBED_APPLIS: list[int] = sorted({*APPLI_DOMAIN, PROFILE_CHANGE_APPLI})
