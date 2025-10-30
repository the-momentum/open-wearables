from app.database import DbSession
from app.models import HeartRateData
from app.repositories.repositories import CrudRepository
from app.repositories.apple.auto_export.base_heart_rate_repository import BaseHeartRateRepository
from app.schemas import AEHeartRateQueryParams
from app.schemas import (
    AEHeartRateDataCreate, 
    AEHeartRateDataUpdate
)


class HeartRateDataRepository(CrudRepository[HeartRateData, AEHeartRateDataCreate, AEHeartRateDataUpdate], BaseHeartRateRepository[HeartRateData]):
    def __init__(self, model: type[HeartRateData]):
        CrudRepository.__init__(self, model)
        BaseHeartRateRepository.__init__(self, model)

    def get_heart_rate_data_with_filters(
        self, 
        db_session: DbSession, 
        query_params: AEHeartRateQueryParams,
        user_id: str
    ) -> tuple[list[HeartRateData], int]:
        return self.get_heart_rate_with_filters(db_session, query_params, user_id)
