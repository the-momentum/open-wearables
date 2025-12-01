from typing import Any

from fastapi import Request
from pydantic import BaseModel

from app.database import BaseDbModel
from app.integrations.sqladmin.view_models import ColumnConfig, FormConfig, _get_model_fields
from sqladmin import ModelView
from sqladmin.models import ModelViewMeta


class BaseAdminMeta(ModelViewMeta):
    def __new__(mcls, name: str, bases: tuple, attrs: dict, **kwargs: Any) -> ModelViewMeta:
        cls = super().__new__(mcls, name, bases, attrs, **kwargs)

        if "create_schema" in kwargs:
            cls._create_schema = kwargs["create_schema"]

        if "update_schema" in kwargs:
            cls._update_schema = kwargs["update_schema"]

        if "column" in kwargs:
            ColumnConfig(**kwargs["column"]).apply_to_class(cls)
        else:
            if hasattr(cls, "model"):
                cls.column_searchable_list = _get_model_fields(cls)
                cls.column_sortable_list = _get_model_fields(cls)

        if auto_exclude_fields := mcls._get_fields_with_default_factory(cls):
            cls.form_excluded_columns = auto_exclude_fields

        if "form" in kwargs:
            FormConfig(**kwargs["form"]).apply_to_class(cls)

        return cls

    @staticmethod
    def _get_fields_with_default_factory(cls: type) -> list[str]:
        exclude_fields = []

        for schema_attr in ["_create_schema", "_update_schema"]:
            if schema := getattr(cls, schema_attr, None):
                for field_name, field_info in schema.model_fields.items():
                    if getattr(field_info, "default_factory", None):
                        exclude_fields.append(field_name)

        return list(set(exclude_fields))


class BaseAdminView(ModelView, metaclass=BaseAdminMeta):
    _create_schema: type[BaseModel]
    _update_schema: type[BaseModel]

    column_list: str | list[str] = "__all__"

    # by default metaclass excludes fields from schemas with default_factory
    form_excluded_columns: list[str] = []
    # fields with PrimaryKey in SQLAchemy model are always excluded
    # add form_include_pk=True to your target class to override this behavior

    async def on_model_change(
        self,
        data: dict[str, Any],
        model: BaseDbModel,
        is_created: bool,
        request: Request,
    ) -> None:
        schema = self._create_schema if is_created else self._update_schema
        validated_data = schema.model_validate(data)

        update_dict = validated_data.model_dump(exclude_none=True)

        for field_name, field_value in update_dict.items():
            setattr(model, field_name, field_value)
