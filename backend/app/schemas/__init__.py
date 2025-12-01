# Common schemas
from .api_key import ApiKeyCreate, ApiKeyRead, ApiKeyUpdate
from .apple.apple_xml.aws import PresignedURLRequest, PresignedURLResponse
from .apple.auto_export.active_energy import (
    ActiveEnergyCreate as AEActiveEnergyCreate,
)
from .apple.auto_export.active_energy import (
    ActiveEnergyUpdate as AEActiveEnergyUpdate,
)
from .apple.auto_export.heart_rate import (
    HeartRateDataCreate as AEHeartRateDataCreate,
)
from .apple.auto_export.heart_rate import (
    HeartRateDataResponse as AEHeartRateDataResponse,
)
from .apple.auto_export.heart_rate import (
    HeartRateDataUpdate as AEHeartRateDataUpdate,
)
from .apple.auto_export.heart_rate import (
    HeartRateListResponse as AEHeartRateListResponse,
)
from .apple.auto_export.heart_rate import (
    HeartRateMeta as AEMeta,
)
from .apple.auto_export.heart_rate import (
    HeartRateQueryParams as AEHeartRateQueryParams,
)
from .apple.auto_export.heart_rate import (
    HeartRateRecoveryCreate as AEHeartRateRecoveryCreate,
)
from .apple.auto_export.heart_rate import (
    HeartRateRecoveryResponse as AEHeartRateRecoveryResponse,
)
from .apple.auto_export.heart_rate import (
    HeartRateRecoveryUpdate as AEHeartRateRecoveryUpdate,
)
from .apple.auto_export.heart_rate import (
    HeartRateSummary as AESummary,
)
from .apple.auto_export.heart_rate import (
    HeartRateValue as AEHeartRateValue,
)
from .apple.auto_export.import_schemas import (
    ActiveEnergyIn as AEActiveEnergyIn,
)
from .apple.auto_export.import_schemas import (
    HeartRateDataIn as AEHeartRateDataIn,
)
from .apple.auto_export.import_schemas import (
    HeartRateRecoveryIn as AEHeartRateRecoveryIn,
)
from .apple.auto_export.import_schemas import (
    ImportBundle as AEImportBundle,
)
from .apple.auto_export.import_schemas import (
    WorkoutIn as AEWorkoutIn,
)
from .apple.auto_export.json_schemas import (
    ActiveEnergyEntryJSON as AEActiveEnergyEntryJSON,
)
from .apple.auto_export.json_schemas import (
    HeartRateEntryJSON as AEHeartRateEntryJSON,
)
from .apple.auto_export.json_schemas import (
    QuantityJSON as AEQuantityJSON,
)
from .apple.auto_export.json_schemas import (
    RootJSON as AERootJSON,
)
from .apple.auto_export.json_schemas import (
    WorkoutJSON as AEWorkoutJSON,
)
from .apple.auto_export.workout_crud import (
    WorkoutCreate as AEWorkoutCreate,
)
from .apple.auto_export.workout_crud import (
    WorkoutUpdate as AEWorkoutUpdate,
)
from .apple.auto_export.workout_queries import WorkoutQueryParams as AEWorkoutQueryParams
from .apple.auto_export.workout_responses import (
    DateRange as AEDateRange,
)
from .apple.auto_export.workout_responses import (
    WorkoutListResponse as AEWorkoutListResponse,
)
from .apple.auto_export.workout_responses import (
    WorkoutMeta as AEWorkoutMeta,
)
from .apple.auto_export.workout_responses import (
    WorkoutResponse as AEWorkoutResponse,
)
from .apple.auto_export.workout_responses import (
    WorkoutSummary as AEWorkoutSummary,
)
from .apple.auto_export.workout_values import (
    ActiveEnergyValue as AEActiveEnergyValue,
)
from .apple.auto_export.workout_values import (
    DistanceValue as AEDistanceValue,
)
from .apple.auto_export.workout_values import (
    HumidityValue as AEHumidityValue,
)
from .apple.auto_export.workout_values import (
    IntensityValue as AEIntensityValue,
)
from .apple.auto_export.workout_values import (
    TemperatureValue as AETemperatureValue,
)
from .apple.healthkit.record_crud import (
    RecordCreate as HKRecordCreate,
)
from .apple.healthkit.record_crud import (
    RecordUpdate as HKRecordUpdate,
)
from .apple.healthkit.record_import import (
    MetadataEntryIn as HKMetadataEntryIn,
)
from .apple.healthkit.record_import import (
    RecordIn as HKRecordIn,
)
from .apple.healthkit.record_import import (
    RecordJSON as HKRecordJSON,
)
from .apple.healthkit.record_queries import (
    RecordQueryParams as HKRecordQueryParams,
)
from .apple.healthkit.record_responses import (
    MetadataEntryResponse as HKMetadataEntryResponse,
)
from .apple.healthkit.record_responses import (
    RecordListResponse as HKRecordListResponse,
)
from .apple.healthkit.record_responses import (
    RecordMeta as HKRecordMeta,
)
from .apple.healthkit.record_responses import (
    RecordResponse as HKRecordResponse,
)

# HealthKit schemas
from .apple.healthkit.workout_crud import (
    WorkoutCreate as HKWorkoutCreate,
)
from .apple.healthkit.workout_crud import (
    WorkoutUpdate as HKWorkoutUpdate,
)
from .apple.healthkit.workout_import import (
    RootJSON as HKRootJSON,
)
from .apple.healthkit.workout_import import (
    WorkoutIn as HKWorkoutIn,
)
from .apple.healthkit.workout_import import (
    WorkoutJSON as HKWorkoutJSON,
)
from .apple.healthkit.workout_queries import (
    WorkoutQueryParams as HKWorkoutQueryParams,
)
from .apple.healthkit.workout_responses import (
    DateRange as HKDateRange,
)
from .apple.healthkit.workout_responses import (
    WorkoutListResponse as HKWorkoutListResponse,
)
from .apple.healthkit.workout_responses import (
    WorkoutMeta as HKWorkoutMeta,
)
from .apple.healthkit.workout_responses import (
    WorkoutResponse as HKWorkoutResponse,
)
from .apple.healthkit.workout_responses import (
    WorkoutSummary as HKWorkoutSummary,
)
from .apple.workout_statistics import (
    WorkoutStatisticCreate as HKWorkoutStatisticCreate,
)
from .apple.workout_statistics import (
    WorkoutStatisticIn as HKWorkoutStatisticIn,
)
from .apple.workout_statistics import (
    WorkoutStatisticJSON as HKWorkoutStatisticJSON,
)
from .apple.workout_statistics import (
    WorkoutStatisticResponse as HKWorkoutStatisticResponse,
)
from .apple.workout_statistics import (
    WorkoutStatisticUpdate as HKWorkoutStatisticUpdate,
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
from .response import UploadDataResponse
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
    # Auto Export schemas
    "AEWorkoutCreate",
    "AEWorkoutUpdate",
    "AEWorkoutQueryParams",
    "AEWorkoutResponse",
    "AEWorkoutListResponse",
    "AEWorkoutSummary",
    "AEWorkoutMeta",
    "AESummary",
    "AEMeta",
    "AEDistanceValue",
    "AEActiveEnergyValue",
    "AEIntensityValue",
    "AETemperatureValue",
    "AEHumidityValue",
    "AEDateRange",
    "AEHeartRateDataCreate",
    "AEHeartRateDataUpdate",
    "AEHeartRateRecoveryCreate",
    "AEHeartRateRecoveryUpdate",
    "AEHeartRateQueryParams",
    "AEHeartRateDataResponse",
    "AEHeartRateRecoveryResponse",
    "AEHeartRateListResponse",
    "AEHeartRateValue",
    "AEActiveEnergyCreate",
    "AEActiveEnergyUpdate",
    "AEWorkoutIn",
    "AEHeartRateDataIn",
    "AEHeartRateRecoveryIn",
    "AEActiveEnergyIn",
    "AEQuantityJSON",
    "AEHeartRateEntryJSON",
    "AEActiveEnergyEntryJSON",
    "AEWorkoutJSON",
    "AERootJSON",
    "AEImportBundle",
    # HealthKit schemas
    "HKWorkoutCreate",
    "HKWorkoutUpdate",
    "HKWorkoutQueryParams",
    "HKWorkoutResponse",
    "HKWorkoutListResponse",
    "HKWorkoutSummary",
    "HKWorkoutMeta",
    "HKDateRange",
    "HKWorkoutIn",
    "HKRootJSON",
    "HKWorkoutJSON",
    "HKWorkoutStatisticCreate",
    "HKWorkoutStatisticUpdate",
    "HKWorkoutStatisticJSON",
    "HKWorkoutStatisticResponse",
    "HKWorkoutStatisticIn",
    "HKRecordCreate",
    "HKRecordUpdate",
    "HKRecordQueryParams",
    "HKRecordResponse",
    "HKRecordListResponse",
    "HKRecordMeta",
    "HKMetadataEntryResponse",
    "HKRecordIn",
    "HKRecordJSON",
    "HKMetadataEntryIn",
    "PresignedURLRequest",
    "PresignedURLResponse",
]
