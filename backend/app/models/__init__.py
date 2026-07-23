from .api_key import ApiKey
from .application import Application
from .archival_setting import ArchivalSetting
from .data_point_series import DataPointSeries
from .data_point_series_archive import DataPointSeriesArchive
from .data_source import DataSource
from .developer import Developer
from .device_type_priority import DeviceTypePriority
from .event_record import EventRecord
from .event_record_detail import DetailType, EventRecordDetail
from .health_score import HealthScore
from .invitation import Invitation
from .menstrual_cycle_details import MenstrualCycleDetails
from .personal_record import PersonalRecord
from .provider_priority import ProviderPriority
from .provider_setting import ProviderSetting
from .refresh_token import RefreshToken
from .series_type_definition import SeriesTypeDefinition
from .sleep_details import SleepDetails
from .user import User
from .user_connection import UserConnection
from .user_invitation_code import UserInvitationCode
from .workout_details import WorkoutDetails

# Single source of truth mapping detail_type -> concrete model, derived from the
# EventRecordDetail subclasses defined above. Adding a new detail model (and
# importing it here, as every model must be for the ORM) registers it automatically.
DETAIL_MODELS: dict[DetailType, type[EventRecordDetail]] = {
    model.detail_type: model for model in EventRecordDetail.__subclasses__()
}

__all__ = [
    "ApiKey",
    "Application",
    "ArchivalSetting",
    "Developer",
    "DataSource",
    "DataPointSeriesArchive",
    "DeviceTypePriority",
    "Invitation",
    "ProviderPriority",
    "ProviderSetting",
    "RefreshToken",
    "User",
    "UserConnection",
    "UserInvitationCode",
    "EventRecord",
    "EventRecordDetail",
    "MenstrualCycleDetails",
    "SleepDetails",
    "WorkoutDetails",
    "PersonalRecord",
    "DataPointSeries",
    "SeriesTypeDefinition",
    "HealthScore",
    "DetailType",
    "DETAIL_MODELS",
]
