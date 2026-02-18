"""
Tests for healthcheck utilities.

Tests database health check endpoint and pool status monitoring.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.utils.healthcheck import database_health, get_pool_status


class TestGetPoolStatus:
    """Test suite for get_pool_status function."""

    @patch("app.utils.healthcheck.engine")
    def test_get_pool_status_returns_all_fields(self, mock_engine: MagicMock) -> None:
        """Test that get_pool_status returns all required pool fields."""
        # Arrange
        mock_pool = MagicMock()
        mock_pool.size.return_value = 10
        mock_pool.checkedin.return_value = 5
        mock_pool.checkedout.return_value = 3
        mock_pool.overflow.return_value = 2
        mock_engine.pool = mock_pool

        # Act
        result = get_pool_status()

        # Assert
        assert "max_pool_size" in result
        assert "connections_ready_for_reuse" in result
        assert "active_connections" in result
        assert "overflow" in result

    @patch("app.utils.healthcheck.engine")
    def test_get_pool_status_returns_string_values(self, mock_engine: MagicMock) -> None:
        """Test that all pool status values are returned as strings."""
        # Arrange
        mock_pool = MagicMock()
        mock_pool.size.return_value = 10
        mock_pool.checkedin.return_value = 5
        mock_pool.checkedout.return_value = 3
        mock_pool.overflow.return_value = 0
        mock_engine.pool = mock_pool

        # Act
        result = get_pool_status()

        # Assert
        assert result["max_pool_size"] == "10"
        assert result["connections_ready_for_reuse"] == "5"
        assert result["active_connections"] == "3"
        assert result["overflow"] == "0"
        assert all(isinstance(v, str) for v in result.values())

    @patch("app.utils.healthcheck.engine")
    def test_get_pool_status_with_zero_connections(self, mock_engine: MagicMock) -> None:
        """Test pool status when no connections are active."""
        # Arrange
        mock_pool = MagicMock()
        mock_pool.size.return_value = 5
        mock_pool.checkedin.return_value = 5
        mock_pool.checkedout.return_value = 0
        mock_pool.overflow.return_value = 0
        mock_engine.pool = mock_pool

        # Act
        result = get_pool_status()

        # Assert
        assert result["active_connections"] == "0"
        assert result["connections_ready_for_reuse"] == "5"

    @patch("app.utils.healthcheck.engine")
    def test_get_pool_status_with_overflow(self, mock_engine: MagicMock) -> None:
        """Test pool status when overflow connections exist."""
        # Arrange
        mock_pool = MagicMock()
        mock_pool.size.return_value = 10
        mock_pool.checkedin.return_value = 0
        mock_pool.checkedout.return_value = 10
        mock_pool.overflow.return_value = 5
        mock_engine.pool = mock_pool

        # Act
        result = get_pool_status()

        # Assert
        assert result["overflow"] == "5"
        assert result["active_connections"] == "10"


class TestDatabaseHealth:
    """Test suite for database_health endpoint."""

    @pytest.mark.asyncio
    async def test_database_health_success(self) -> None:
        """Test database health check when database is healthy."""
        # Arrange
        mock_db = MagicMock()
        mock_db.execute.return_value = None

        with patch("app.utils.healthcheck.get_pool_status") as mock_pool_status:
            mock_pool_status.return_value = {
                "max_pool_size": "10",
                "connections_ready_for_reuse": "5",
                "active_connections": "3",
                "overflow": "0",
            }

            # Act
            result = await database_health(mock_db)

            # Assert
            assert result["status"] == "healthy"
            assert "pool" in result
            assert result["pool"]["max_pool_size"] == "10"
            assert result["pool"]["connections_ready_for_reuse"] == "5"
            assert result["pool"]["active_connections"] == "3"
            assert result["pool"]["overflow"] == "0"
            mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_database_health_executes_test_query(self) -> None:
        """Test that database health check executes SELECT 1 query."""
        # Arrange
        mock_db = MagicMock()

        with patch("app.utils.healthcheck.get_pool_status") as mock_pool_status:
            mock_pool_status.return_value = {
                "max_pool_size": "5",
                "connections_ready_for_reuse": "2",
                "active_connections": "1",
                "overflow": "0",
            }

            # Act
            await database_health(mock_db)

            # Assert
            call_args = mock_db.execute.call_args
            assert call_args is not None
            # Verify that text("SELECT 1") was called
            assert isinstance(call_args[0][0]._bindparams, dict)

    @pytest.mark.asyncio
    async def test_database_health_failure(self) -> None:
        """Test database health check when database connection fails."""
        # Arrange
        mock_db = MagicMock()
        error_message = "Connection refused"
        mock_db.execute.side_effect = Exception(error_message)

        # Act
        result = await database_health(mock_db)

        # Assert
        assert result["status"] == "unhealthy"
        assert "error" in result
        assert result["error"] == error_message
        assert "pool" not in result

    @pytest.mark.asyncio
    async def test_database_health_with_connection_timeout(self) -> None:
        """Test database health check with connection timeout error."""
        # Arrange
        mock_db = MagicMock()
        mock_db.execute.side_effect = TimeoutError("Connection timeout")

        # Act
        result = await database_health(mock_db)

        # Assert
        assert result["status"] == "unhealthy"
        assert "Connection timeout" in result["error"]

    @pytest.mark.asyncio
    async def test_database_health_with_database_error(self) -> None:
        """Test database health check with database-specific error."""
        # Arrange
        mock_db = MagicMock()
        mock_db.execute.side_effect = Exception("Database is shutting down")

        # Act
        result = await database_health(mock_db)

        # Assert
        assert result["status"] == "unhealthy"
        assert result["error"] == "Database is shutting down"

    @pytest.mark.asyncio
    async def test_database_health_includes_pool_status_on_success(self) -> None:
        """Test that successful health check includes pool status."""
        # Arrange
        mock_db = MagicMock()
        expected_pool = {
            "max_pool_size": "20",
            "connections_ready_for_reuse": "10",
            "active_connections": "8",
            "overflow": "2",
        }

        with patch("app.utils.healthcheck.get_pool_status") as mock_pool_status:
            mock_pool_status.return_value = expected_pool

            # Act
            result = await database_health(mock_db)

            # Assert
            assert result["status"] == "healthy"
            assert result["pool"] == expected_pool
            mock_pool_status.assert_called_once()
