from .api_key import ApiKeyCreate, ApiKeyRead, ApiKeyUpdate
from .apple.apple_xml.aws import PresignedURLRequest, PresignedURLResponse
from .apple.auto_export.json_schemas import (
    ActiveEnergyEntryJSON as AEActiveEnergyEntryJSON,
)
from .apple.auto_export.json_schemas import (
    HeartRateEntryJSON as AEHeartRateEntryJSON,
)
from .apple.auto_export.json_schemas import (
    WorkoutJSON as AEWorkoutJSON,
)
from .apple.healthkit.record_import import (
    RecordJSON as HKRecordJSON,
)
from .apple.healthkit.workout_import import (
    WorkoutJSON as HKWorkoutJSON,
)
from .common import (
    RootJSON,
)
from .common_types import (
    DataSource,
    ErrorDetails,
    PaginatedResponse,
    Pagination,
    TimeseriesMetadata,
)
from .developer import (
    DeveloperCreate,
    DeveloperCreateInternal,
    DeveloperRead,
    DeveloperUpdate,
    DeveloperUpdateInternal,
)
from .error_codes import ErrorCode
from .event_record import (
    EventRecordCreate,
    EventRecordMetrics,
    EventRecordQueryParams,
    EventRecordResponse,
    EventRecordUpdate,
)
from .event_record_detail import (
    EventRecordDetailCreate,
    EventRecordDetailResponse,
    EventRecordDetailUpdate,
)
from .events import (
    Macros,
    Meal,
    Measurement,
    SleepSession,
    Workout,
    WorkoutDetailed,
    WorkoutType,
)
from .external_mapping import (
    ExternalMappingCreate,
    ExternalMappingResponse,
    ExternalMappingUpdate,
)
from .filter_params import FilterParams
from .garmin.activity_import import (
    ActivityJSON as GarminActivityJSON,
)
from .garmin.activity_import import (
    RootJSON as GarminRootJSON,
)
from .oauth import (
    AuthenticationMethod,
    AuthorizationURLResponse,
    ConnectionStatus,
    OAuthState,
    OAuthTokenResponse,
    ProviderCredentials,
    ProviderEndpoints,
    ProviderName,
    UserConnectionCreate,
    UserConnectionRead,
    UserConnectionUpdate,
)
from .personal_record import (
    PersonalRecordCreate,
    PersonalRecordResponse,
    PersonalRecordUpdate,
)
from .polar.exercise_import import (
    ExerciseJSON as PolarExerciseJSON,
)
from .provider_setting import (
    BulkProviderSettingsUpdate,
    ProviderSettingRead,
    ProviderSettingUpdate,
)
from .response import UploadDataResponse
from .summaries import (
    ActivitySummary,
    BodySummary,
    IntensityMinutes,
    RecoverySummary,
    SleepStagesSummary,
    SleepSummary,
)
from .suunto.workout_import import (
    HeartRateJSON as SuuntoHeartRateJSON,
)
from .suunto.workout_import import (
    RootJSON as SuuntoRootJSON,
)
from .suunto.workout_import import (
    WorkoutJSON as SuuntoWorkoutJSON,
)
from .sync import (
    ProviderSyncResult,
    SyncAllUsersResult,
    SyncVendorDataResult,
)
from .system_info import (
    CountWithGrowth,
    DataPointsInfo,
    SystemInfoResponse,
)
from .time_series import (
    HeartRateSampleCreate,
    HeartRateSampleResponse,
    SeriesType,
    StepSampleCreate,
    StepSampleResponse,
    TimeSeriesQueryParams,
    TimeSeriesSampleCreate,
    TimeSeriesSampleResponse,
    TimeSeriesSampleUpdate,
)
from .timeseries import (
    BiometricType,
    BloodGlucoseSample,
    HeartRateSample,
    HrvSample,
    SleepStageSample,
    Spo2Sample,
    StepsSample,
)
from .user import (
    UserCreate,
    UserCreateInternal,
    UserRead,
    UserUpdate,
    UserUpdateInternal,
)

__all__ = [
    # Common schemas
    "FilterParams",
    "UserRead",
    "UserCreate",
    "UserCreateInternal",
    "UserUpdate",
    "UserUpdateInternal",
    "DeveloperRead",
    "DeveloperCreate",
    "DeveloperCreateInternal",
    "DeveloperUpdateInternal",
    "DeveloperUpdate",
    "ApiKeyCreate",
    "ApiKeyRead",
    "ApiKeyUpdate",
    "ErrorCode",
    "UploadDataResponse",
    # OAuth schemas
    "AuthenticationMethod",
    "ConnectionStatus",
    "ProviderName",
    "OAuthState",
    "OAuthTokenResponse",
    "ProviderEndpoints",
    "ProviderCredentials",
    "UserConnectionCreate",
    "UserConnectionRead",
    "UserConnectionUpdate",
    "AuthorizationURLResponse",
    "ProviderSettingRead",
    "ProviderSettingUpdate",
    "BulkProviderSettingsUpdate",
    "RootJSON",
    "EventRecordCreate",
    "EventRecordUpdate",
    "EventRecordResponse",
    "EventRecordQueryParams",
    "EventRecordMetrics",
    "EventRecordDetailCreate",
    "EventRecordDetailResponse",
    "EventRecordDetailUpdate",
    "WorkoutType",
    "ExternalMappingCreate",
    "ExternalMappingUpdate",
    "ExternalMappingResponse",
    "HeartRateSampleCreate",
    "HeartRateSampleResponse",
    "TimeSeriesSampleCreate",
    "TimeSeriesSampleResponse",
    "TimeSeriesSampleUpdate",
    "SeriesType",
    "StepSampleCreate",
    "StepSampleResponse",
    "TimeSeriesQueryParams",
    "SystemInfoResponse",
    "CountWithGrowth",
    "DataPointsInfo",
    "HKWorkoutJSON",
    "HKRecordJSON",
    "AEWorkoutJSON",
    "AEHeartRateEntryJSON",
    "AEActiveEnergyEntryJSON",
    "PersonalRecordCreate",
    "PersonalRecordUpdate",
    "PersonalRecordResponse",
    # Suunto schemas
    "SuuntoRootJSON",
    "SuuntoWorkoutJSON",
    "SuuntoHeartRateJSON",
    # Garmin schemas
    "GarminRootJSON",
    "GarminActivityJSON",
    # Polar schemas
    "PolarExerciseJSON",
    # AWS schemas
    "PresignedURLRequest",
    "PresignedURLResponse",
    # Sync schemas
    "ProviderSyncResult",
    "SyncAllUsersResult",
    "SyncVendorDataResult",
    # Common Types
    "DataSource",
    "ErrorDetails",
    "PaginatedResponse",
    "Pagination",
    "TimeseriesMetadata",
    # Events
    "Macros",
    "Meal",
    "Measurement",
    "SleepSession",
    "Workout",
    "WorkoutDetailed",
    # Summaries
    "ActivitySummary",
    "BodySummary",
    "IntensityMinutes",
    "RecoverySummary",
    "SleepStagesSummary",
    "SleepSummary",
    # Timeseries
    "BiometricType",
    "BloodGlucoseSample",
    "HeartRateSample",
    "HrvSample",
    "SleepStageSample",
    "Spo2Sample",
    "StepsSample",
]
