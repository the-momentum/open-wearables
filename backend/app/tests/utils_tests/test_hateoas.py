"""
Tests for HATEOAS utilities.

Tests URL building, link generation, and HATEOAS response formatting
for both individual items and collections.
"""

import pytest
from unittest.mock import MagicMock

from app.utils.hateoas import (
    _build_query,
    _generate_item_links,
    _generate_collection_links,
    get_hateoas_item,
    get_hateoas_list,
)


class TestBuildQuery:
    """Test suite for _build_query function."""

    def test_build_query_with_id(self):
        """Should build correct URL with entity ID."""
        # Arrange
        base_url = "http://localhost:8000"
        name = "user"
        inst_id = "123e4567-e89b-12d3-a456-426614174000"

        # Act
        result = _build_query(base_url, name, inst_id)

        # Assert
        assert "http://localhost:8000/api/v1/users/123e4567-e89b-12d3-a456-426614174000" == result
        assert inst_id in result
        assert f"{name}s" in result

    def test_build_query_without_id(self):
        """Should build correct URL without entity ID."""
        # Arrange
        base_url = "http://localhost:8000"
        name = "user"

        # Act
        result = _build_query(base_url, name)

        # Assert
        assert result == "http://localhost:8000/api/v1/users/"
        assert result.endswith("users/")

    def test_build_query_with_empty_string_id(self):
        """Should build correct URL with empty string ID."""
        # Arrange
        base_url = "http://localhost:8000"
        name = "developer"
        inst_id = ""

        # Act
        result = _build_query(base_url, name, inst_id)

        # Assert
        assert result == "http://localhost:8000/api/v1/developers/"
        assert result.endswith("/")

    def test_build_query_pluralizes_name(self):
        """Should correctly pluralize entity name by adding 's'."""
        # Arrange
        base_url = "http://localhost:8000"
        name = "apikey"
        inst_id = "key123"

        # Act
        result = _build_query(base_url, name, inst_id)

        # Assert
        assert "apikeys" in result
        assert f"{name}s" in result


class TestGenerateItemLinks:
    """Test suite for _generate_item_links function."""

    def test_generate_item_links_basic(self):
        """Should generate basic CRUD links for an item."""
        # Arrange
        built_url = "http://localhost:8000/api/v1/users/123"
        url = "http://localhost:8000/api/v1/users/123"

        # Act
        result = _generate_item_links(built_url, url)

        # Assert
        assert len(result) == 3
        assert {"rel": "self", "href": url} in result
        assert {"rel": "update", "href": built_url, "method": "PUT"} in result
        assert {"rel": "delete", "href": built_url, "method": "DELETE"} in result

    def test_generate_item_links_with_extra_rels(self):
        """Should include extra relations in the links."""
        # Arrange
        built_url = "http://localhost:8000/api/v1/users/123"
        url = "http://localhost:8000/api/v1/users/123"
        extra_rels = [
            {"rel": "connections", "endpoint": "/connections", "method": "GET"}
        ]

        # Act
        result = _generate_item_links(built_url, url, extra_rels)

        # Assert
        assert len(result) == 4
        connections_link = next((link for link in result if link["rel"] == "connections"), None)
        assert connections_link is not None
        assert connections_link["href"] == "http://localhost:8000/api/v1/users/123/connections"
        assert connections_link["method"] == "GET"

    def test_generate_item_links_with_overwrite(self):
        """Should overwrite existing relation when specified."""
        # Arrange
        built_url = "http://localhost:8000/api/v1/users/123"
        url = "http://localhost:8000/api/v1/users/123"
        extra_rels = [
            {"rel": "custom_delete", "endpoint": "/archive", "method": "POST", "overwrite": "delete"}
        ]

        # Act
        result = _generate_item_links(built_url, url, extra_rels)

        # Assert
        # Should not have the original 'delete' link
        delete_links = [link for link in result if link["rel"] == "delete"]
        assert len(delete_links) == 0

        # Should have the custom_delete link
        custom_delete = next((link for link in result if link["rel"] == "custom_delete"), None)
        assert custom_delete is not None
        assert custom_delete["href"] == "http://localhost:8000/api/v1/users/123/archive"

    def test_generate_item_links_multiple_extra_rels(self):
        """Should handle multiple extra relations."""
        # Arrange
        built_url = "http://localhost:8000/api/v1/users/123"
        url = "http://localhost:8000/api/v1/users/123"
        extra_rels = [
            {"rel": "connections", "endpoint": "/connections", "method": "GET"},
            {"rel": "records", "endpoint": "/records", "method": "GET"},
            {"rel": "export", "endpoint": "/export", "method": "POST"}
        ]

        # Act
        result = _generate_item_links(built_url, url, extra_rels)

        # Assert
        assert len(result) == 6  # 3 basic + 3 extra
        assert any(link["rel"] == "connections" for link in result)
        assert any(link["rel"] == "records" for link in result)
        assert any(link["rel"] == "export" for link in result)


class TestGenerateCollectionLinks:
    """Test suite for _generate_collection_links function."""

    def test_generate_collection_links_first_page(self):
        """Should generate links for first page of collection."""
        # Arrange
        page = 1
        limit = 10
        base_url = "http://localhost:8000/api/v1/users"

        # Act
        result = _generate_collection_links(page, limit, base_url)

        # Assert
        assert len(result) == 2  # self and next, no prev on first page
        assert {"rel": "self", "href": f"{base_url}?page=1&limit=10", "method": "GET"} in result
        assert {"rel": "next", "href": f"{base_url}?page=2&limit=10", "method": "GET"} in result
        assert not any(link["rel"] == "prev" for link in result)

    def test_generate_collection_links_middle_page(self):
        """Should generate links for middle page with prev and next."""
        # Arrange
        page = 5
        limit = 20
        base_url = "http://localhost:8000/api/v1/developers"

        # Act
        result = _generate_collection_links(page, limit, base_url)

        # Assert
        assert len(result) == 3  # self, next, and prev
        assert {"rel": "self", "href": f"{base_url}?page=5&limit=20", "method": "GET"} in result
        assert {"rel": "next", "href": f"{base_url}?page=6&limit=20", "method": "GET"} in result
        assert {"rel": "prev", "href": f"{base_url}?page=4&limit=20"} in result

    def test_generate_collection_links_with_different_limits(self):
        """Should correctly include limit parameter in URLs."""
        # Arrange
        page = 2
        limit = 50
        base_url = "http://localhost:8000/api/v1/users"

        # Act
        result = _generate_collection_links(page, limit, base_url)

        # Assert
        self_link = next(link for link in result if link["rel"] == "self")
        assert "limit=50" in self_link["href"]
        next_link = next(link for link in result if link["rel"] == "next")
        assert "limit=50" in next_link["href"]


class TestGetHateoasItem:
    """Test suite for get_hateoas_item function."""

    def test_get_hateoas_item_basic(self):
        """Should create HATEOAS item with links."""
        # Arrange
        mock_instance = MagicMock()
        mock_instance.__tablename__ = "user"
        mock_instance.id_str = "123e4567-e89b-12d3-a456-426614174000"

        base_url = "http://localhost:8000"
        url = "http://localhost:8000/api/v1/users/123e4567-e89b-12d3-a456-426614174000"

        # Mock the base_to_dict function through the instance
        with pytest.mock.patch("app.utils.hateoas.base_to_dict") as mock_base_to_dict:
            mock_base_to_dict.return_value = {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "first_name": "John",
                "last_name": "Doe"
            }

            # Act
            result = get_hateoas_item(mock_instance, base_url, url)

        # Assert
        assert "id" in result
        assert "first_name" in result
        assert "_links" in result
        assert len(result["_links"]) == 3
        assert any(link["rel"] == "self" for link in result["_links"])
        assert any(link["rel"] == "update" for link in result["_links"])
        assert any(link["rel"] == "delete" for link in result["_links"])

    def test_get_hateoas_item_with_extra_rels(self):
        """Should create HATEOAS item with extra relations."""
        # Arrange
        mock_instance = MagicMock()
        mock_instance.__tablename__ = "user"
        mock_instance.id_str = "123"

        base_url = "http://localhost:8000"
        url = "http://localhost:8000/api/v1/users/123"
        extra_rels = [
            {"rel": "connections", "endpoint": "/connections", "method": "GET"}
        ]

        with pytest.mock.patch("app.utils.hateoas.base_to_dict") as mock_base_to_dict:
            mock_base_to_dict.return_value = {"id": "123", "name": "Test User"}

            # Act
            result = get_hateoas_item(mock_instance, base_url, url, extra_rels)

        # Assert
        assert "_links" in result
        assert len(result["_links"]) == 4
        assert any(link["rel"] == "connections" for link in result["_links"])


class TestGetHateoasList:
    """Test suite for get_hateoas_list function."""

    def test_get_hateoas_list_basic(self):
        """Should create HATEOAS list with items and pagination links."""
        # Arrange
        mock_item1 = MagicMock()
        mock_item1.__tablename__ = "user"
        mock_item2 = MagicMock()
        mock_item2.__tablename__ = "user"

        items = [mock_item1, mock_item2]
        page = 1
        limit = 10
        base_url = "http://localhost:8000"

        with pytest.mock.patch("app.utils.hateoas.base_to_dict") as mock_base_to_dict:
            mock_base_to_dict.side_effect = [
                {"id": "1", "name": "User 1"},
                {"id": "2", "name": "User 2"}
            ]

            # Act
            result = get_hateoas_list(items, page, limit, base_url)

        # Assert
        assert "items" in result
        assert "items" in result
        assert "_links" in result
        assert len(result["items"]) == 2
        assert result["items"][0]["id"] == "1"
        assert result["items"][1]["id"] == "2"

    def test_get_hateoas_list_empty(self):
        """Should handle empty list correctly."""
        # Arrange
        items = []
        page = 1
        limit = 10
        base_url = "http://localhost:8000"

        # Act
        result = get_hateoas_list(items, page, limit, base_url)

        # Assert
        assert "items" in result
        assert "items" in result
        assert "_links" in result
        assert len(result["items"]) == 0
        # Links should still be generated
        assert len(result["_links"]) > 0

    def test_get_hateoas_list_with_pagination(self):
        """Should create correct pagination links."""
        # Arrange
        mock_item = MagicMock()
        mock_item.__tablename__ = "developer"

        items = [mock_item]
        page = 3
        limit = 25
        base_url = "http://localhost:8000"

        with pytest.mock.patch("app.utils.hateoas.base_to_dict") as mock_base_to_dict:
            mock_base_to_dict.return_value = {"id": "1"}

            # Act
            result = get_hateoas_list(items, page, limit, base_url)

        # Assert
        assert "_links" in result
        self_link = next(link for link in result["_links"] if link["rel"] == "self")
        assert "page=3" in self_link["href"]
        assert "limit=25" in self_link["href"]

        next_link = next(link for link in result["_links"] if link["rel"] == "next")
        assert "page=4" in next_link["href"]

        prev_link = next(link for link in result["_links"] if link["rel"] == "prev")
        assert "page=2" in prev_link["href"]
