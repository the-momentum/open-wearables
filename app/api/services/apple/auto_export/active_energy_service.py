from logging import Logger, getLogger
from uuid import UUID

from app.database import DbSession
from app.models import ActiveEnergy
from app.repositories import ActiveEnergyRepository
from app.schemas import AEActiveEnergyCreate, AEActiveEnergyUpdate
from app.services.services import AppService
from app.utils.exceptions import handle_exceptions


class ActiveEnergyService(AppService[ActiveEnergyRepository, ActiveEnergy, AEActiveEnergyCreate, AEActiveEnergyUpdate]):
    """Service for active energy-related business logic."""

    def __init__(self, log: Logger, **kwargs):
        super().__init__(
            crud_model=ActiveEnergyRepository,
            model=ActiveEnergy,
            log=log,
            **kwargs
        )

    @handle_exceptions
    def get_active_energy_by_workout_id(self, db_session: DbSession, workout_id: UUID) -> list[ActiveEnergy]:
        self.logger.debug(f"Fetching active energy for workout {workout_id}")
        
        active_energy = self.crud.get_active_energy_by_workout_id(db_session, workout_id)
        
        self.logger.debug(f"Retrieved {len(active_energy)} active energy records for workout {workout_id}")
        
        return active_energy

    @handle_exceptions
    def get_active_energy_by_user_id(self, db_session: DbSession, user_id: str) -> list[ActiveEnergy]:
        self.logger.debug(f"Fetching active energy for user {user_id}")
        
        active_energy = self.crud.get_active_energy_by_user_id(db_session, user_id)
        
        self.logger.debug(f"Retrieved {len(active_energy)} active energy records for user {user_id}")
        
        return active_energy

    @handle_exceptions
    def create_active_energy_batch(
        self, 
        db_session: DbSession, 
        active_energy_data: list[AEActiveEnergyCreate]
    ) -> list[ActiveEnergy]:
        self.logger.debug(f"Creating batch of {len(active_energy_data)} active energy records")
        
        created_records = []
        for data in active_energy_data:
            record = self.create(db_session, data)
            created_records.append(record)
        
        self.logger.debug(f"Successfully created {len(created_records)} active energy records")
        
        return created_records


active_energy_service = ActiveEnergyService(log=getLogger(__name__))
