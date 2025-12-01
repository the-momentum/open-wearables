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
    DeveloperUpdate,
    DeveloperUpdateInternal,
    DeveloperRead,
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
from .user import (
    UserCreate,
    UserCreateInternal,
    UserUpdate,
    UserUpdateInternal,
    UserRead,
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
    "ProviderName",
    "OAuthState",
    "OAuthTokenResponse",
    "ProviderEndpoints",
    "ProviderCredentials",
    "UserConnectionCreate",
    "UserConnectionRead",
    "UserConnectionUpdate",
    "AuthorizationURLResponse",
    "RootJSON",
    "WorkoutCreate",
    "WorkoutUpdate",
    "WorkoutResponse",
    "WorkoutQueryParams",
    "WorkoutStatisticCreate",
    "WorkoutStatisticUpdate",
    "WorkoutStatisticResponse",
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
]
