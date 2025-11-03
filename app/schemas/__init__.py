# Auto Export schemas

from .apple.auto_export.workout_queries import WorkoutQueryParams as AEWorkoutQueryParams
from .apple.auto_export.workout_values import (
    DistanceValue as AEDistanceValue,
    ActiveEnergyValue as AEActiveEnergyValue,
    IntensityValue as AEIntensityValue,
    TemperatureValue as AETemperatureValue,
    HumidityValue as AEHumidityValue,
)
from .apple.auto_export.workout_responses import (
    WorkoutResponse as AEWorkoutResponse,
    WorkoutListResponse as AEWorkoutListResponse,
    WorkoutSummary as AEWorkoutSummary,
    WorkoutMeta as AEWorkoutMeta,
    DateRange as AEDateRange,
)
from .apple.auto_export.workout_crud import (
    WorkoutCreate as AEWorkoutCreate,
    WorkoutUpdate as AEWorkoutUpdate,
)
from .apple.auto_export.heart_rate import (
    HeartRateDataCreate as AEHeartRateDataCreate,
    HeartRateDataUpdate as AEHeartRateDataUpdate,
    HeartRateRecoveryCreate as AEHeartRateRecoveryCreate,
    HeartRateRecoveryUpdate as AEHeartRateRecoveryUpdate,
    HeartRateQueryParams as AEHeartRateQueryParams,
    HeartRateDataResponse as AEHeartRateDataResponse,
    HeartRateRecoveryResponse as AEHeartRateRecoveryResponse,
    HeartRateListResponse as AEHeartRateListResponse,
    HeartRateSummary as AESummary,
    HeartRateMeta as AEMeta,
    HeartRateValue as AEHeartRateValue,
)
from .apple.auto_export.active_energy import ActiveEnergyCreate as AEActiveEnergyCreate, ActiveEnergyUpdate as AEActiveEnergyUpdate
from .apple.auto_export.import_schemas import (
    WorkoutIn as AEWorkoutIn,
    HeartRateDataIn as AEHeartRateDataIn,
    HeartRateRecoveryIn as AEHeartRateRecoveryIn,
    ActiveEnergyIn as AEActiveEnergyIn,
    ImportBundle as AEImportBundle,
)
from .apple.auto_export.json_schemas import (
    QuantityJSON as AEQuantityJSON,
    HeartRateEntryJSON as AEHeartRateEntryJSON,
    ActiveEnergyEntryJSON as AEActiveEnergyEntryJSON,
    WorkoutJSON as AEWorkoutJSON,
    RootJSON as AERootJSON,
)

# HealthKit schemas

from .apple.healthkit.workout_crud import (
    WorkoutCreate as HKWorkoutCreate,
    WorkoutUpdate as HKWorkoutUpdate,
)
from .apple.healthkit.workout_queries import (
    WorkoutQueryParams as HKWorkoutQueryParams,
)
from .apple.healthkit.workout_responses import (
    WorkoutResponse as HKWorkoutResponse,
    WorkoutListResponse as HKWorkoutListResponse,
    WorkoutSummary as HKWorkoutSummary,
    WorkoutMeta as HKWorkoutMeta,
    DateRange as HKDateRange,
)
from .apple.healthkit.workout_import import (
    WorkoutIn as HKWorkoutIn,
    WorkoutJSON as HKWorkoutJSON,
    RootJSON as HKRootJSON,
)
from .apple.healthkit.record_crud import (
    RecordCreate as HKRecordCreate,
    RecordUpdate as HKRecordUpdate,
)
from .apple.healthkit.record_queries import (
    RecordQueryParams as HKRecordQueryParams,
)
from .apple.healthkit.record_responses import (
    RecordResponse as HKRecordResponse,
    RecordListResponse as HKRecordListResponse,
    RecordMeta as HKRecordMeta,
    MetadataEntryResponse as HKMetadataEntryResponse,
)
from .apple.healthkit.record_import import (
    RecordIn as HKRecordIn,
    RecordJSON as HKRecordJSON,
    MetadataEntryIn as HKMetadataEntryIn,
)
from .apple.workout_statistics import (
    WorkoutStatisticCreate as HKWorkoutStatisticCreate,
    WorkoutStatisticUpdate as HKWorkoutStatisticUpdate,
    WorkoutStatisticJSON as HKWorkoutStatisticJSON,
    WorkoutStatisticResponse as HKWorkoutStatisticResponse,
    WorkoutStatisticIn as HKWorkoutStatisticIn,
)

# Common schemas

from .filter_params import FilterParams
from .user import UserInfo, UserResponse, UserCreate, UserUpdate
from .error_codes import ErrorCode
from .response import UploadDataResponse

__all__ = [
    # Common schemas
    "FilterParams",
    "UserInfo",
    "UserResponse",
    "UserCreate",
    "UserUpdate",
    "ErrorCode",
    "UploadDataResponse",
    
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
]
