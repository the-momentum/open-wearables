from logging import Logger, getLogger
from uuid import UUID
import httpx

from app.config import settings
from app.database import DbSession
from app.services.base_workout_service import BaseWorkoutService


class PolarService(BaseWorkoutService):
    """Service for interacting with Polar AccessLink API."""

    def __init__(self, log: Logger):
        super().__init__(
            log,
            provider="polar",
            api_base_url=settings.polar_api_base_url,
        )

    def register_user(self, access_token: str, member_id: str) -> dict:
        """Register user with Polar API.

        This is REQUIRED before accessing any user data.
        From Polar API docs: "Once partner has been authorized by user,
        partner must register the user before being able to access its data."

        Args:
            access_token: User's access token
            member_id: Partner's custom identifier for user

        Returns:
            dict: User registration response with polar-user-id

        Raises:
            httpx.HTTPStatusError: If registration fails (except 409 Conflict)
        """
        url = f"{self.api_base_url}/v3/users"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        payload = {"member-id": member_id}

        self.logger.info(f"Registering user with member-id: {member_id}")

        response = httpx.post(url, json=payload, headers=headers, timeout=30.0)

        if response.status_code == 409:
            self.logger.debug(f"User {member_id} already registered with Polar API")
            return {"already_registered": True}

        # Raise for other errors
        response.raise_for_status()

        data = response.json()
        self.logger.debug(f"Successfully registered user {member_id} with Polar API")
        return data

    def get_exercises(
        self,
        db: DbSession,
        user_id: UUID,
        samples: bool = False,
        zones: bool = False,
        route: bool = False,
    ) -> list[dict]:
        """Get exercises from Polar API.

        Args:
            db: Database session
            user_id: User ID
            samples: Return all sample data for exercises
            zones: Return all zones data for exercises
            route: Return all route data for exercises

        Returns:
            list[dict]: List of exercises from Polar API
        """
        params = {
            "samples": str(samples).lower(),
            "zones": str(zones).lower(),
            "route": str(route).lower(),
        }

        self.logger.info(f"Fetching exercises for user {user_id} from Polar API")
        return self._make_api_request(db, user_id, "/v3/exercises", params=params)

    def get_exercise_detail(
        self,
        db: DbSession,
        user_id: UUID,
        exercise_id: str,
        samples: bool = False,
        zones: bool = False,
        route: bool = False,
    ) -> dict:
        """Get detailed exercise data from Polar API.

        Args:
            db: Database session
            user_id: User ID
            exercise_id: Polar exercise ID (hashed)
            samples: Return all sample data for this exercise
            zones: Return all zones data for this exercise
            route: Return all route data for this exercise

        Returns:
            dict: Detailed exercise data
        """
        params = {
            "samples": str(samples).lower(),
            "zones": str(zones).lower(),
            "route": str(route).lower(),
        }

        self.logger.info(f"Fetching exercise {exercise_id} for user {user_id} from Polar API")
        return self._make_api_request(db, user_id, f"/v3/exercises/{exercise_id}", params=params)


polar_service = PolarService(log=getLogger(__name__))
