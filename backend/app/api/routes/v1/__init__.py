from fastapi import APIRouter

from .api_keys import router as api_keys_router
from .auth import router as auth_router
from .heart_rate import router as heart_rate_router
from .import_data import router as import_data_router
from .oauth import router as oauth_router
from .records import router as records_router
from .suunto import router as suunto_router
from .users import router as users_router
from .vendor_workouts import router as vendor_workouts_router
from .workouts import router as workouts_router

v1_router = APIRouter()

v1_router.include_router(auth_router, prefix="/auth", tags=["developer"])
v1_router.include_router(api_keys_router, prefix="/developer", tags=["api-keys"])
v1_router.include_router(oauth_router, prefix="/oauth", tags=["vendors oauth"])
# Legacy route for backwards compatibility
v1_router.include_router(suunto_router, prefix="/suunto", tags=["suunto (deprecated)"])
# New unified vendor workouts endpoint
v1_router.include_router(vendor_workouts_router, prefix="/vendors", tags=["vendor workouts"])
v1_router.include_router(users_router, tags=["users"])
v1_router.include_router(heart_rate_router, tags=["data"])
v1_router.include_router(workouts_router, tags=["data"])
v1_router.include_router(records_router, tags=["data"])
v1_router.include_router(import_data_router, tags=["import-data"])

__all__ = ["v1_router"]
