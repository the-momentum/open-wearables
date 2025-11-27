from .api_key import ApiKeyCreate, ApiKeyRead, ApiKeyUpdate
from .developer import DeveloperCreate, DeveloperRead, DeveloperUpdate
from .error_codes import ErrorCode
from .filter_params import FilterParams
from .oauth import (
    AuthorizationURLResponse,
    OAuthState,
    OAuthTokenResponse,
    ProviderConfig,
    UserConnectionCreate,
    UserConnectionRead,
    UserConnectionUpdate,
)
from .response import UploadDataResponse
from .user import UserCreate, UserCreateInternal, UserRead, UserUpdate

from .apple.apple_xml.aws import PresignedURLRequest, PresignedURLResponse
from .workout import (
    WorkoutCreate,
    WorkoutUpdate,
    WorkoutResponse,
    WorkoutQueryParams,
)
from .workout_statistics import (
    WorkoutStatisticCreate,
    WorkoutStatisticUpdate,
    WorkoutStatisticResponse,
)
from .common import (
    RootJSON,
)

from .apple.healthkit.workout_import import (
    WorkoutJSON as HKWorkoutJSON,
)
from .apple.healthkit.record_import import (
    RecordJSON as HKRecordJSON,
)

from .apple.auto_export.json_schemas import (
    WorkoutJSON as AEWorkoutJSON,
    HeartRateEntryJSON as AEHeartRateEntryJSON,
    ActiveEnergyEntryJSON as AEActiveEnergyEntryJSON,
)
from .suunto.workout_import import (
    RootJSON as SuuntoRootJSON,
    WorkoutJSON as SuuntoWorkoutJSON,
    HeartRateJSON as SuuntoHeartRateJSON,
)
from .garmin.activity_import import (
    RootJSON as GarminRootJSON,
    ActivityJSON as GarminActivityJSON,
)
from .polar.exercise_import import (
    ExerciseJSON as PolarExerciseJSON,
)

__all__ = [
    # Common schemas
    "FilterParams",
    "UserRead",
    "UserCreate",
    "UserCreateInternal",
    "UserUpdate",
    "DeveloperRead",
    "DeveloperCreate",
    "DeveloperUpdate",
    "ApiKeyCreate",
    "ApiKeyRead",
    "ApiKeyUpdate",
    "ErrorCode",
    "UploadDataResponse",
    # OAuth schemas
    "OAuthState",
    "OAuthTokenResponse",
    "ProviderConfig",
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
