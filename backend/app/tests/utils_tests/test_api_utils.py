"""
Tests for API utility functions.

Tests the format_response decorator that adds HATEOAS formatting
to API responses.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.responses import JSONResponse

from app.utils.api_utils import format_response


class TestFormatResponseDecorator:
    """Test suite for format_response decorator."""

    @pytest.mark.asyncio
    async def test_format_response_single_item(self) -> None:
        """Should format single item response with HATEOAS links."""

        # Arrange
        @format_response()
        async def test_endpoint(**kwargs) -> None:
            mock_item = MagicMock()
            mock_item.__tablename__ = "user"
            mock_item.id_str = "123"
            return mock_item

        mock_request = MagicMock()
        mock_request.base_url = "http://localhost:8000/"
        mock_request.url = "http://localhost:8000/api/v1/users/123"

        with patch("app.utils.api_utils.get_hateoas_item") as mock_hateoas:
            mock_hateoas.return_value = {
                "id": "123",
                "name": "Test User",
                "_links": [{"rel": "self", "href": "http://localhost:8000/api/v1/users/123"}],
            }

            # Act
            result = await test_endpoint(request=mock_request)

        # Assert
        assert isinstance(result, JSONResponse)
        assert result.status_code == 200
        mock_hateoas.assert_called_once()

    @pytest.mark.asyncio
    async def test_format_response_list(self) -> None:
        """Should format list response with HATEOAS links."""
        # Arrange
        mock_item1 = MagicMock()
        mock_item1.__tablename__ = "user"
        mock_item2 = MagicMock()
        mock_item2.__tablename__ = "user"

        @format_response()
        async def test_endpoint(**kwargs) -> None:
            return [mock_item1, mock_item2]

        mock_request = MagicMock()
        mock_request.base_url = "http://localhost:8000/"
        mock_request.url = "http://localhost:8000/api/v1/users?page=1&limit=10"

        with patch("app.utils.api_utils.get_hateoas_list") as mock_hateoas:
            mock_hateoas.return_value = {
                "items": [{"id": "1"}, {"id": "2"}],
                "_links": [{"rel": "self", "href": "http://localhost:8000/api/v1/users?page=1&limit=10"}],
            }

            # Act
            result = await test_endpoint(request=mock_request, page=1, limit=10)

        # Assert
        assert isinstance(result, JSONResponse)
        assert result.status_code == 200
        mock_hateoas.assert_called_once_with([mock_item1, mock_item2], 1, 10, "http://localhost:8000")

    @pytest.mark.asyncio
    async def test_format_response_custom_status_code(self) -> None:
        """Should use custom status code when provided."""

        # Arrange
        @format_response(status_code=201)
        async def test_endpoint(**kwargs) -> None:
            mock_item = MagicMock()
            mock_item.__tablename__ = "user"
            mock_item.id_str = "123"
            return mock_item

        mock_request = MagicMock()
        mock_request.base_url = "http://localhost:8000/"
        mock_request.url = "http://localhost:8000/api/v1/users/123"

        with patch("app.utils.api_utils.get_hateoas_item") as mock_hateoas:
            mock_hateoas.return_value = {"id": "123", "_links": []}

            # Act
            result = await test_endpoint(request=mock_request)

        # Assert
        assert result.status_code == 201

    @pytest.mark.asyncio
    async def test_format_response_with_extra_rels(self) -> None:
        """Should pass extra relations to HATEOAS formatter."""
        # Arrange
        extra_rels = [{"rel": "connections", "endpoint": "/connections", "method": "GET"}]

        @format_response(extra_rels=extra_rels)
        async def test_endpoint(**kwargs) -> None:
            mock_item = MagicMock()
            mock_item.__tablename__ = "user"
            mock_item.id_str = "123"
            return mock_item

        mock_request = MagicMock()
        mock_request.base_url = "http://localhost:8000/"
        mock_request.url = "http://localhost:8000/api/v1/users/123"

        with patch("app.utils.api_utils.get_hateoas_item") as mock_hateoas:
            mock_hateoas.return_value = {
                "id": "123",
                "_links": [
                    {"rel": "self", "href": "http://localhost:8000/api/v1/users/123"},
                    {
                        "rel": "connections",
                        "href": "http://localhost:8000/api/v1/users/123/connections",
                        "method": "GET",
                    },
                ],
            }

            # Act
            await test_endpoint(request=mock_request)

        # Assert
        mock_hateoas.assert_called_once()
        call_args = mock_hateoas.call_args
        assert call_args[0][2] == "http://localhost:8000/api/v1/users/123"
        assert call_args[0][3] == extra_rels

    @pytest.mark.asyncio
    async def test_format_response_missing_request(self) -> None:
        """Should raise ValueError when request is not in kwargs."""

        # Arrange
        @format_response()
        async def test_endpoint() -> None:
            return MagicMock()

        # Act & Assert
        with pytest.raises(ValueError, match="Request object not found in kwargs"):
            await test_endpoint()

    @pytest.mark.asyncio
    async def test_format_response_strips_trailing_slash(self) -> None:
        """Should strip trailing slash from base_url."""

        # Arrange
        @format_response()
        async def test_endpoint(**kwargs) -> None:
            mock_item = MagicMock()
            mock_item.__tablename__ = "user"
            mock_item.id_str = "123"
            return mock_item

        mock_request = MagicMock()
        mock_request.base_url = "http://localhost:8000/"  # Has trailing slash
        mock_request.url = "http://localhost:8000/api/v1/users/123"

        with patch("app.utils.api_utils.get_hateoas_item") as mock_hateoas:
            mock_hateoas.return_value = {"id": "123", "_links": []}

            # Act
            await test_endpoint(request=mock_request)

        # Assert
        call_args = mock_hateoas.call_args
        base_url = call_args[0][1]
        assert not base_url.endswith("/")
        assert base_url == "http://localhost:8000"

    @pytest.mark.asyncio
    async def test_format_response_preserves_function_metadata(self) -> None:
        """Should preserve wrapped function's name and docstring."""

        # Arrange
        @format_response()
        async def test_endpoint(**kwargs) -> None:
            """Test endpoint docstring."""
            mock_item = MagicMock()
            mock_item.__tablename__ = "user"
            mock_item.id_str = "123"
            return mock_item

        # Assert
        assert test_endpoint.__name__ == "test_endpoint"
        assert test_endpoint.__doc__ == "Test endpoint docstring."

    @pytest.mark.asyncio
    async def test_format_response_empty_list(self) -> None:
        """Should handle empty list response correctly."""

        # Arrange
        @format_response()
        async def test_endpoint(**kwargs) -> None:
            return []

        mock_request = MagicMock()
        mock_request.base_url = "http://localhost:8000/"
        mock_request.url = "http://localhost:8000/api/v1/users?page=1&limit=10"

        with patch("app.utils.api_utils.get_hateoas_list") as mock_hateoas:
            mock_hateoas.return_value = {
                "items": [],
                "_links": [{"rel": "self", "href": "http://localhost:8000/api/v1/users?page=1&limit=10"}],
            }

            # Act
            result = await test_endpoint(request=mock_request, page=1, limit=10)

        # Assert
        assert isinstance(result, JSONResponse)
        # Check that it was called with correct parameters (using ANY for empty list comparison)

        mock_hateoas.assert_called_once()
        args = mock_hateoas.call_args[0]
        assert args[0] == []
        assert args[1:] == (1, 10, "http://localhost:8000")

    @pytest.mark.asyncio
    async def test_format_response_with_complex_extra_rels(self) -> None:
        """Should handle multiple extra relations with overwrites."""
        # Arrange
        extra_rels = [
            {"rel": "connections", "endpoint": "/connections", "method": "GET"},
            {"rel": "records", "endpoint": "/records", "method": "GET"},
            {"rel": "custom_delete", "endpoint": "/archive", "method": "POST", "overwrite": "delete"},
        ]

        @format_response(extra_rels=extra_rels)
        async def test_endpoint(**kwargs) -> None:
            mock_item = MagicMock()
            mock_item.__tablename__ = "user"
            mock_item.id_str = "123"
            return mock_item

        mock_request = MagicMock()
        mock_request.base_url = "http://localhost:8000/"
        mock_request.url = "http://localhost:8000/api/v1/users/123"

        with patch("app.utils.api_utils.get_hateoas_item") as mock_hateoas:
            mock_hateoas.return_value = {
                "id": "123",
                "_links": [
                    {"rel": "self", "href": "http://localhost:8000/api/v1/users/123"},
                    {"rel": "update", "href": "http://localhost:8000/api/v1/users/123", "method": "PUT"},
                    {
                        "rel": "connections",
                        "href": "http://localhost:8000/api/v1/users/123/connections",
                        "method": "GET",
                    },
                    {"rel": "records", "href": "http://localhost:8000/api/v1/users/123/records", "method": "GET"},
                    {
                        "rel": "custom_delete",
                        "href": "http://localhost:8000/api/v1/users/123/archive",
                        "method": "POST",
                    },
                ],
            }

            # Act
            await test_endpoint(request=mock_request)

        # Assert
        mock_hateoas.assert_called_once()
        call_args = mock_hateoas.call_args
        assert call_args[0][3] == extra_rels
