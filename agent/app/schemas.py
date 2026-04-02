from pydantic import BaseModel, Field, field_validator

from app.config import settings
from app.database import BaseDbModel


class FilterParams(BaseModel):
    filters: dict[str, str] = Field(default_factory=dict)
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=settings.paging_limit, ge=1)
    sort_by: str | None = Field(default=None)

    @field_validator("filters")
    @classmethod
    def validate_filters(cls, v: dict[str, str]) -> dict[str, str]:
        """Remove empty or whitespace-only filters."""
        return {k: v for k, v in v.items() if v and v.strip()}

    def validate_against_model(self, model_class: type[BaseDbModel]) -> None:
        """Validate that filter and sort fields exist in the model."""
        allowed_fields = {field.name for field in model_class.__table__.columns}

        if invalid := set(self.filters.keys()) - allowed_fields:
            raise ValueError(f"Invalid filter fields: {invalid}")

        if self.sort_by and self.sort_by not in allowed_fields:
            raise ValueError(f"Invalid sort field: {self.sort_by}")
