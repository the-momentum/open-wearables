"""Resource classes for the Open Wearables API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

from open_wearables.models import (
    Connection,
    User,
    UserCreate,
    UserUpdate,
    Workout,
    WorkoutStatistic,
)

if TYPE_CHECKING:
    from open_wearables.http import HttpClient


class UsersResource:
    """Resource for managing users."""

    API_VERSION = "/api/v1"

    def __init__(self, http: HttpClient):
        self._http = http

    def list(self) -> list[User]:
        """List all users.
        
        Returns:
            List of User objects.
        """
        data = self._http.request("GET", f"{self.API_VERSION}/users")
        return [User.model_validate(u) for u in data]

    async def alist(self) -> list[User]:
        """List all users (async).
        
        Returns:
            List of User objects.
        """
        data = await self._http.arequest("GET", f"{self.API_VERSION}/users")
        return [User.model_validate(u) for u in data]

    def get(self, user_id: str | UUID) -> User:
        """Get a user by ID.
        
        Args:
            user_id: The user's UUID.
            
        Returns:
            User object.
        """
        data = self._http.request("GET", f"{self.API_VERSION}/users/{user_id}")
        return User.model_validate(data)

    async def aget(self, user_id: str | UUID) -> User:
        """Get a user by ID (async).
        
        Args:
            user_id: The user's UUID.
            
        Returns:
            User object.
        """
        data = await self._http.arequest("GET", f"{self.API_VERSION}/users/{user_id}")
        return User.model_validate(data)

    def create(
        self,
        *,
        external_user_id: str | None = None,
        email: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> User:
        """Create a new user.
        
        Args:
            external_user_id: Your application's user ID.
            email: User's email address.
            first_name: User's first name.
            last_name: User's last name.
            
        Returns:
            Created User object.
        """
        payload = UserCreate(
            external_user_id=external_user_id,
            email=email,
            first_name=first_name,
            last_name=last_name,
        )
        data = self._http.request(
            "POST",
            f"{self.API_VERSION}/users",
            json=payload.model_dump(exclude_none=True),
        )
        return User.model_validate(data)

    async def acreate(
        self,
        *,
        external_user_id: str | None = None,
        email: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> User:
        """Create a new user (async).
        
        Args:
            external_user_id: Your application's user ID.
            email: User's email address.
            first_name: User's first name.
            last_name: User's last name.
            
        Returns:
            Created User object.
        """
        payload = UserCreate(
            external_user_id=external_user_id,
            email=email,
            first_name=first_name,
            last_name=last_name,
        )
        data = await self._http.arequest(
            "POST",
            f"{self.API_VERSION}/users",
            json=payload.model_dump(exclude_none=True),
        )
        return User.model_validate(data)

    def update(
        self,
        user_id: str | UUID,
        *,
        external_user_id: str | None = None,
        email: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> User:
        """Update a user.
        
        Args:
            user_id: The user's UUID.
            external_user_id: Your application's user ID.
            email: User's email address.
            first_name: User's first name.
            last_name: User's last name.
            
        Returns:
            Updated User object.
        """
        payload = UserUpdate(
            external_user_id=external_user_id,
            email=email,
            first_name=first_name,
            last_name=last_name,
        )
        data = self._http.request(
            "PATCH",
            f"{self.API_VERSION}/users/{user_id}",
            json=payload.model_dump(exclude_none=True),
        )
        return User.model_validate(data)

    async def aupdate(
        self,
        user_id: str | UUID,
        *,
        external_user_id: str | None = None,
        email: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> User:
        """Update a user (async).
        
        Args:
            user_id: The user's UUID.
            external_user_id: Your application's user ID.
            email: User's email address.
            first_name: User's first name.
            last_name: User's last name.
            
        Returns:
            Updated User object.
        """
        payload = UserUpdate(
            external_user_id=external_user_id,
            email=email,
            first_name=first_name,
            last_name=last_name,
        )
        data = await self._http.arequest(
            "PATCH",
            f"{self.API_VERSION}/users/{user_id}",
            json=payload.model_dump(exclude_none=True),
        )
        return User.model_validate(data)

    def delete(self, user_id: str | UUID) -> User:
        """Delete a user.
        
        Args:
            user_id: The user's UUID.
            
        Returns:
            Deleted User object.
        """
        data = self._http.request("DELETE", f"{self.API_VERSION}/users/{user_id}")
        return User.model_validate(data)

    async def adelete(self, user_id: str | UUID) -> User:
        """Delete a user (async).
        
        Args:
            user_id: The user's UUID.
            
        Returns:
            Deleted User object.
        """
        data = await self._http.arequest("DELETE", f"{self.API_VERSION}/users/{user_id}")
        return User.model_validate(data)

    def get_workouts(
        self,
        user_id: str | UUID,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        workout_type: str | None = None,
        source_name: str | None = None,
        min_duration: int | None = None,
        max_duration: int | None = None,
        limit: int | None = 20,
        offset: int | None = 0,
        sort_by: Literal["start_datetime", "end_datetime", "duration_seconds", "type", "source_name"] | None = None,
        sort_order: Literal["asc", "desc"] | None = None,
    ) -> list[Workout]:
        """Get workouts for a user.
        
        Args:
            user_id: The user's UUID.
            start_date: ISO 8601 start date filter.
            end_date: ISO 8601 end date filter.
            workout_type: Filter by workout type.
            source_name: Filter by source name.
            min_duration: Minimum duration in seconds.
            max_duration: Maximum duration in seconds.
            limit: Maximum number of results (1-100).
            offset: Number of results to skip.
            sort_by: Field to sort by.
            sort_order: Sort order (asc/desc).
            
        Returns:
            List of Workout objects.
        """
        params: dict[str, Any] = {
            "start_date": start_date,
            "end_date": end_date,
            "workout_type": workout_type,
            "source_name": source_name,
            "min_duration": min_duration,
            "max_duration": max_duration,
            "limit": limit,
            "offset": offset,
            "sort_by": sort_by,
            "sort_order": sort_order,
        }
        data = self._http.request("GET", f"{self.API_VERSION}/users/{user_id}/workouts", params=params)
        return [Workout.model_validate(w) for w in data]

    async def aget_workouts(
        self,
        user_id: str | UUID,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        workout_type: str | None = None,
        source_name: str | None = None,
        min_duration: int | None = None,
        max_duration: int | None = None,
        limit: int | None = 20,
        offset: int | None = 0,
        sort_by: Literal["start_datetime", "end_datetime", "duration_seconds", "type", "source_name"] | None = None,
        sort_order: Literal["asc", "desc"] | None = None,
    ) -> list[Workout]:
        """Get workouts for a user (async).
        
        Args:
            user_id: The user's UUID.
            start_date: ISO 8601 start date filter.
            end_date: ISO 8601 end date filter.
            workout_type: Filter by workout type.
            source_name: Filter by source name.
            min_duration: Minimum duration in seconds.
            max_duration: Maximum duration in seconds.
            limit: Maximum number of results (1-100).
            offset: Number of results to skip.
            sort_by: Field to sort by.
            sort_order: Sort order (asc/desc).
            
        Returns:
            List of Workout objects.
        """
        params: dict[str, Any] = {
            "start_date": start_date,
            "end_date": end_date,
            "workout_type": workout_type,
            "source_name": source_name,
            "min_duration": min_duration,
            "max_duration": max_duration,
            "limit": limit,
            "offset": offset,
            "sort_by": sort_by,
            "sort_order": sort_order,
        }
        data = await self._http.arequest("GET", f"{self.API_VERSION}/users/{user_id}/workouts", params=params)
        return [Workout.model_validate(w) for w in data]

    def get_connections(self, user_id: str | UUID) -> list[Connection]:
        """Get connections for a user.
        
        Args:
            user_id: The user's UUID.
            
        Returns:
            List of Connection objects.
        """
        data = self._http.request("GET", f"{self.API_VERSION}/users/{user_id}/connections")
        return [Connection.model_validate(c) for c in data]

    async def aget_connections(self, user_id: str | UUID) -> list[Connection]:
        """Get connections for a user (async).
        
        Args:
            user_id: The user's UUID.
            
        Returns:
            List of Connection objects.
        """
        data = await self._http.arequest("GET", f"{self.API_VERSION}/users/{user_id}/connections")
        return [Connection.model_validate(c) for c in data]

    def get_heart_rate(self, user_id: str | UUID) -> list[WorkoutStatistic]:
        """Get heart rate data for a user.
        
        Args:
            user_id: The user's UUID.
            
        Returns:
            List of WorkoutStatistic objects with heart rate data.
        """
        data = self._http.request("GET", f"{self.API_VERSION}/users/{user_id}/heart-rate")
        return [WorkoutStatistic.model_validate(s) for s in data]

    async def aget_heart_rate(self, user_id: str | UUID) -> list[WorkoutStatistic]:
        """Get heart rate data for a user (async).
        
        Args:
            user_id: The user's UUID.
            
        Returns:
            List of WorkoutStatistic objects with heart rate data.
        """
        data = await self._http.arequest("GET", f"{self.API_VERSION}/users/{user_id}/heart-rate")
        return [WorkoutStatistic.model_validate(s) for s in data]
