from fastapi import APIRouter

from .api_keys import router as api_keys_router
from .applications import router as applications_router
from .archival import router as archival_router
from .auth import router as auth_router
from .connections import router as connections_router
from .dashboard import router as dashboard_router
from .data_sources import router as data_sources_router
from .deprecated_webhooks import router as deprecated_webhooks_router
from .developers import router as developers_router
from .events import router as events_router
from .health_scores import router as health_scores_router
from .import_xml import router as import_xml_router
from .invitations import router as invitations_router
from .oauth import router as oauth_router
from .oura_webhooks import router as oura_webhooks_router
from .priorities import router as priorities_router
from .sdk_logs import router as sdk_logs_router
from .sdk_sync import router as sdk_sync_router
from .sdk_token import router as sdk_token_router
from .seed_data import router as seed_data_router
from .strava_webhooks import router as strava_webhooks_router
from .summaries import router as summaries_router
from .suunto_debug import router as suunto_debug_router
from .sync_data import router as sync_data_router
from .timeseries import router as timeseries_router
from .token import router as token_router
from .user_invitation_code import router as user_invitation_code_router
from .users import router as users_router
from .vendor_workouts import router as vendor_workouts_router
from .webhooks import router as providers_webhooks_router

v1_router = APIRouter()

# --- External: 3rd party integration endpoints ---
v1_router.include_router(users_router, tags=["External: Users"])
v1_router.include_router(connections_router, tags=["External: Connections"])
v1_router.include_router(summaries_router, tags=["External: Summaries"])
v1_router.include_router(timeseries_router, tags=["External: Timeseries"])
v1_router.include_router(events_router, tags=["External: Events"])
v1_router.include_router(health_scores_router, tags=["External: Health Scores"])
v1_router.include_router(oauth_router, prefix="/oauth")
v1_router.include_router(sync_data_router, prefix="/providers", tags=["External: Data Sync"])
v1_router.include_router(vendor_workouts_router, prefix="/providers", tags=["External: Workouts"])
v1_router.include_router(import_xml_router, tags=["External: Apple Health Import"])
v1_router.include_router(sdk_logs_router, tags=["External: Mobile SDK"])
v1_router.include_router(sdk_sync_router, tags=["External: Mobile SDK"])
v1_router.include_router(sdk_token_router, tags=["External: Mobile SDK"])
v1_router.include_router(user_invitation_code_router, tags=["External: Mobile SDK"])
v1_router.include_router(token_router, tags=["External: Token"])
v1_router.include_router(data_sources_router, tags=["External: Data Sources"])

# --- Internal: dashboard endpoints ---
v1_router.include_router(auth_router, prefix="/auth", tags=["Internal: Auth"])
v1_router.include_router(developers_router, prefix="/developers", tags=["Internal: Developers"])
v1_router.include_router(invitations_router, prefix="/invitations", tags=["Internal: Invitations"])
v1_router.include_router(api_keys_router, prefix="/developer", tags=["Internal: API Keys"])
v1_router.include_router(applications_router, tags=["Internal: Applications"])
v1_router.include_router(dashboard_router, prefix="/dashboard", tags=["Internal: Dashboard"])
v1_router.include_router(archival_router, tags=["Internal: Data Lifecycle"])
v1_router.include_router(seed_data_router, tags=["Internal: Seed Data"])
v1_router.include_router(priorities_router, tags=["Internal: Priorities"])

# --- System: provider webhooks and debug ---
v1_router.include_router(oura_webhooks_router, prefix="/oura/webhooks", tags=["System: Oura Webhooks"])
v1_router.include_router(strava_webhooks_router, prefix="/strava/webhooks", tags=["System: Strava Webhooks"])
v1_router.include_router(
    providers_webhooks_router, prefix="/providers/{provider}/webhooks", tags=["System: Provider Webhooks"]
)
v1_router.include_router(deprecated_webhooks_router, tags=["System: Provider Webhooks (Deprecated)"], deprecated=True)
v1_router.include_router(suunto_debug_router, prefix="/debug", tags=["System: Debug"])

__all__ = ["v1_router"]
