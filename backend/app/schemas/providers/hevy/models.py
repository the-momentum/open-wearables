"""Typed Pydantic models for Hevy API response shapes.

Boundary validation in the SensorBio/Polar style: raw API dicts are parsed
through these before normalization so malformed payloads are logged and
skipped instead of silently producing bad DB writes.

API reference: https://api.hevyapp.com/docs/ (auth: per-user ``api-key``
header, Hevy Pro required). Timestamps are ISO 8601 strings.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HevySet(BaseModel):
    """One set inside a workout exercise (GET /v1/workouts)."""

    model_config = ConfigDict(extra="ignore")

    index: int | None = None
    type: str | None = None  # normal | warmup | dropset | failure
    weight_kg: float | None = None
    reps: float | None = None
    distance_meters: float | None = None
    duration_seconds: float | None = None
    rpe: float | None = None
    custom_metric: float | None = None


class HevyExercise(BaseModel):
    """One exercise inside a workout, with its sets."""

    model_config = ConfigDict(extra="ignore")

    index: int | None = None
    title: str | None = None
    notes: str | None = None
    exercise_template_id: str | None = None
    supersets_id: int | None = None
    sets: list[HevySet] = []


class HevyWorkout(BaseModel):
    """A workout as returned by GET /v1/workouts and inside 'updated' events."""

    model_config = ConfigDict(extra="ignore")

    id: str
    title: str | None = None
    description: str | None = None
    routine_id: str | None = None
    start_time: datetime
    end_time: datetime
    created_at: datetime | None = None
    updated_at: datetime | None = None
    exercises: list[HevyExercise] = []


class HevyPaginatedWorkouts(BaseModel):
    """Response shape of GET /v1/workouts."""

    model_config = ConfigDict(extra="ignore")

    page: int
    page_count: int
    workouts: list[HevyWorkout] = []


class HevyUpdatedWorkoutEvent(BaseModel):
    """'updated' entry from GET /v1/workouts/events (covers new and edited)."""

    model_config = ConfigDict(extra="ignore")

    type: str  # "updated"
    workout: HevyWorkout


class HevyDeletedWorkoutEvent(BaseModel):
    """'deleted' entry from GET /v1/workouts/events."""

    model_config = ConfigDict(extra="ignore")

    type: str  # "deleted"
    id: str
    deleted_at: datetime | None = None


class HevyPaginatedWorkoutEvents(BaseModel):
    """Response shape of GET /v1/workouts/events."""

    model_config = ConfigDict(extra="ignore")

    page: int
    page_count: int
    events: list[dict] = []


class HevyUserInfo(BaseModel):
    """Response shape of GET /v1/user/info (used to validate an API key)."""

    model_config = ConfigDict(extra="ignore")

    id: str
    username: str | None = None
    name: str | None = None
    url: str | None = None

    @property
    def display_name(self) -> str | None:
        """The Hevy handle when present (unique, stable), else the free-text name."""
        return self.username or self.name
