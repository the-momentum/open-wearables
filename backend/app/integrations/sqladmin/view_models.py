from typing import Any, Literal

from sqlalchemy import inspect
from pydantic import BaseModel

def _get_model_fields(cls) -> list[str]:
    inspector = inspect(cls.model)
    return [attr.key for attr in inspector.attrs]

class BaseConfig(BaseModel):
    include: Literal["*"] | list[str] | None = None
    exclude: list[str] | None = None
    
    def model_post_init(self, __context: Any) -> None:
        if self.include is not None and self.exclude is not None:
            raise ValueError("Cannot use both 'include' and 'exclude' in configuration")
    
    def _all_or_value(self, val) -> str | list[str] | None:
        """Convert '*' or ['*'] to '__all__', otherwise return value."""
        return "__all__" if val == "*" or val == ["*"] else val

class ColumnConfig(BaseConfig):
    searchable: list[str] | None = None
    sortable: list[str] | None = None
    
    def apply_to_class(self, cls: type) -> None:
        configs = {
            'column_list': self._all_or_value(self.include) or [],
            'column_exclude_list': self.exclude if self.exclude else [],
            'column_searchable_list': self.searchable if self.searchable else _get_model_fields(cls),
            'column_sortable_list': self.sortable if self.sortable else _get_model_fields(cls),
        }
        
        for attr, value in configs.items():
            value and setattr(cls, attr, value)

class FormConfig(BaseConfig):
    create_rules: list[str] | None = None
    edit_rules: list[str] | None = None
    
    def apply_to_class(self, cls: type) -> None:
        configs = {
            'form_columns': self._all_or_value(self.include) or [],
            'form_excluded_columns': self.exclude if self.exclude else [],
            'form_create_rules': self.create_rules if self.create_rules else [],
            'form_edit_rules': self.edit_rules if self.edit_rules else [],
        }
        
        for attr, value in configs.items():
            value and setattr(cls, attr, value)
