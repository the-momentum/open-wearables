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
from .developer import (
    DeveloperCreate,
    DeveloperCreateInternal,
    DeveloperRead,
    DeveloperUpdate,
    DeveloperUpdateInternal,
)
from .error_codes import ErrorCode
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
from .polar.exercise_import import (
    ExerciseJSON as PolarExerciseJSON,
)
from .provider_setting import (
    BulkProviderSettingsUpdate,
    ProviderSettingRead,
    ProviderSettingUpdate,
)
from .response import UploadDataResponse
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
from .user import (
    UserCreate,
    UserCreateInternal,
    UserRead,
    UserUpdate,
    UserUpdateInternal,
)
from .workout import (
    WorkoutCreate,
    WorkoutQueryParams,
    WorkoutResponse,
    WorkoutUpdate,
)
from .workout_statistics import (
    WorkoutStatisticCreate,
    WorkoutStatisticResponse,
    WorkoutStatisticUpdate,
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
    "WorkoutCreate",
    "WorkoutUpdate",
    "WorkoutResponse",
    "WorkoutQueryParams",
    "WorkoutStatisticCreate",
    "WorkoutStatisticUpdate",
    "WorkoutStatisticResponse",
    "SystemInfoResponse",
    "CountWithGrowth",
    "DataPointsInfo",
    "HKWorkoutJSON",
    "HKRecordJSON",
    "AEWorkoutJSON",
    "AEHeartRateEntryJSON",
    "AEActiveEnergyEntryJSON",
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
]
