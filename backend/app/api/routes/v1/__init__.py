from fastapi import APIRouter

from .api_keys import router as api_keys_router
from .applications import router as applications_router
from .auth import router as auth_router
from .connections import router as connections_router
from .dashboard import router as dashboard_router
from .developers import router as developers_router
from .events import router as events_router
from .external_connectors import router as external_connectors_router
from .garmin_webhooks import router as garmin_webhooks_router
from .import_xml import router as import_xml_router
from .invitations import router as invitations_router
from .oauth import router as oauth_router
from .priorities import router as priorities_router
from .sdk_sync import router as sdk_sync_router
from .sdk_token import router as sdk_token_router
from .summaries import router as summaries_router
from .suunto_debug import router as suunto_debug_router
from .sync_data import router as sync_data_router
from .timeseries import router as timeseries_router
from .token import router as token_router
from .user_invitation_code import router as user_invitation_code_router
from .users import router as users_router
from .vendor_workouts import router as vendor_workouts_router

v1_router = APIRouter()

v1_router.include_router(auth_router, prefix="/auth", tags=["auth"])
v1_router.include_router(developers_router, prefix="/developers", tags=["developers"])
v1_router.include_router(invitations_router, prefix="/invitations", tags=["invitations"])
v1_router.include_router(api_keys_router, prefix="/developer", tags=["api-keys"])
v1_router.include_router(oauth_router, prefix="/oauth", tags=["providers oauth"])
# Garmin webhooks for push/ping notifications
v1_router.include_router(garmin_webhooks_router, prefix="/garmin/webhooks", tags=["garmin webhooks"])
# New unified vendor workouts endpoint
v1_router.include_router(vendor_workouts_router, prefix="/providers", tags=["providers workouts"])
v1_router.include_router(sync_data_router, prefix="/providers", tags=["sync data"])
# Suunto debug endpoints for raw API access
v1_router.include_router(suunto_debug_router, prefix="/debug", tags=["debug"])
v1_router.include_router(users_router, tags=["users"])
v1_router.include_router(connections_router, tags=["data"])
v1_router.include_router(import_xml_router, tags=["Apple Health XML import"])
v1_router.include_router(external_connectors_router, tags=["External connectors"])
v1_router.include_router(sdk_sync_router, tags=["Mobile SDK"])
v1_router.include_router(sdk_token_router, tags=["Mobile SDK"])
v1_router.include_router(user_invitation_code_router, tags=["Mobile SDK"])
v1_router.include_router(applications_router, tags=["applications"])
v1_router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
v1_router.include_router(priorities_router, tags=["priorities"])

# RFC Taxonomy Routes
v1_router.include_router(summaries_router, tags=["Summaries"])
v1_router.include_router(timeseries_router, tags=["Timeseries"])
v1_router.include_router(events_router, tags=["Events"])

# Token refresh endpoint
v1_router.include_router(token_router, tags=["token"])

__all__ = ["v1_router"]
