"""Tests for FilterParams validation against a model."""

import pytest

from app.models import User
from app.schemas.utils.query_params import FilterParams
from app.utils.exceptions import InvalidInputError


class TestValidateAgainstModel:
    def test_known_fields_pass(self) -> None:
        FilterParams(sort_by="created_at", filters={"email": "a@b.c"}).validate_against_model(User)

    def test_unknown_sort_field_is_invalid_input(self) -> None:
        with pytest.raises(InvalidInputError, match="Field 'nope' does not exist on model User"):
            FilterParams(sort_by="nope").validate_against_model(User)

    def test_unknown_filter_field_is_invalid_input(self) -> None:
        with pytest.raises(InvalidInputError, match="Field 'nope' does not exist on model User"):
            FilterParams(filters={"nope": "x"}).validate_against_model(User)
