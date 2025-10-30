from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import DeclarativeBase


class FilterParams(BaseModel):
    """Generic filter parameters for database queries."""
    
    page: int = Field(1, ge=1, description="Page number (1-based)")
    limit: int = Field(20, ge=1, le=100, description="Number of results per page")
    sort_by: str | None = Field(None, description="Field to sort by")
    sort_order: str = Field("asc", description="Sort order (asc/desc)")
    filters: dict[str, str] = Field(default_factory=dict, description="Field filters")

    @field_validator("sort_order")
    @classmethod
    def validate_sort_order(cls, v: str) -> str:
        if v.lower() not in ["asc", "desc"]:
            raise ValueError("sort_order must be 'asc' or 'desc'")
        return v.lower()

    def validate_against_model(self, model: type[DeclarativeBase]) -> None:
        """Validate that sort_by field exists on the model."""
        if self.sort_by and not hasattr(model, self.sort_by):
            raise ValueError(f"Field '{self.sort_by}' does not exist on model {model.__name__}")
