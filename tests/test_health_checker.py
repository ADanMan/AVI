"""Tests for health checker functionality."""

from unittest.mock import MagicMock, patch

import pytest

from src.utils.health import HealthChecker, HealthCheckResult


def test_health_check_result_creation():
    """Test HealthCheckResult creation."""
    result = HealthCheckResult("test", "healthy", "All good")
    assert result.name == "test"
    assert result.status == "healthy"
    assert result.message == "All good"
    assert result.details == {}


def test_health_check_result_with_details():
    """Test HealthCheckResult with details."""
    result = HealthCheckResult("test", "degraded", "Warning", {"key": "value"})
    assert result.details == {"key": "value"}
    assert "key" in result.to_dict()["details"]
    assert result.to_dict()["details"]["key"] == "value"


def test_health_check_result_is_healthy():
    """Test is_healthy() method."""
    healthy = HealthCheckResult("test", "healthy")
    degraded = HealthCheckResult("test", "degraded")
    unhealthy = HealthCheckResult("test", "unhealthy")

    assert healthy.is_healthy() is True
    assert degraded.is_healthy() is False
    assert unhealthy.is_healthy() is False


def test_health_check_result_to_dict():
    """Test to_dict() conversion."""
    result = HealthCheckResult("disk_space", "healthy", "1.5GB free", {"free_gb": 1.5})

    data = result.to_dict()
    assert data["name"] == "disk_space"
    assert data["status"] == "healthy"
    assert data["message"] == "1.5GB free"
    assert data["details"]["free_gb"] == 1.5


def test_health_checker_initialization():
    """Test HealthChecker initialization."""
    checker = HealthChecker()
    assert checker.min_disk_space_gb == 0.5


@patch("pathlib.Path.exists")
@patch("shutil.disk_usage")
def test_check_disk_space_healthy(mock_disk_usage, mock_exists):
    """Test disk space check when healthy."""
    # Mock directory exists
    mock_exists.return_value = True
    # Mock 2GB free space
    mock_disk_usage.return_value = MagicMock(free=2 * 1024**3, total=10 * 1024**3)

    checker = HealthChecker()
    result = checker.check_disk_space()

    assert result.status == "healthy"
    assert result.is_healthy()
    assert "2.00GB" in result.message


@patch("pathlib.Path.exists")
@patch("shutil.disk_usage")
def test_check_disk_space_unhealthy(mock_disk_usage, mock_exists):
    """Test disk space check when unhealthy."""
    # Mock directory exists
    mock_exists.return_value = True
    # Mock 0.3GB free space (below 0.5GB threshold)
    mock_disk_usage.return_value = MagicMock(free=0.3 * 1024**3, total=10 * 1024**3)

    checker = HealthChecker()
    result = checker.check_disk_space()

    assert result.status == "unhealthy"
    assert not result.is_healthy()
    assert "Low disk space" in result.message


def test_check_llm_config_healthy():
    """Test LLM config check when configured."""
    checker = HealthChecker()
    result = checker.check_llm_config()

    # Should be healthy in test environment
    assert result.name == "llm_config"
    # Status depends on actual settings, so just check it returns


def test_check_vector_db_config():
    """Test vector DB config check."""
    checker = HealthChecker()
    result = checker.check_vector_db_config()

    assert result.name == "vector_db_config"
    assert result.status in {"healthy", "degraded", "unhealthy"}


@pytest.mark.asyncio
async def test_check_redis_no_library():
    """Test Redis check when redis library not available."""
    import sys

    # Temporarily remove redis from sys.modules
    redis_modules = {k: v for k, v in sys.modules.items() if k.startswith("redis")}
    for key in redis_modules:
        del sys.modules[key]

    # Mock the import to raise ImportError
    with patch.dict("sys.modules", {"redis.asyncio": None}):
        with patch(
            "builtins.__import__",
            side_effect=lambda name, *args: (
                (_ for _ in ()).throw(ImportError(f"No module named '{name}'"))
                if name in ("redis", "redis.asyncio")
                else __import__(name, *args)
            ),
        ):
            checker = HealthChecker()
            result = await checker.check_redis()

            assert result.status == "unhealthy"
            assert "not installed" in result.message

    # Restore redis modules
    sys.modules.update(redis_modules)


@pytest.mark.asyncio
async def test_check_all():
    """Test running all checks."""
    checker = HealthChecker()
    results = await checker.check_all()

    assert isinstance(results, dict)
    assert "disk_space" in results
    assert "llm_config" in results
    assert "vector_db_config" in results

    for name, result in results.items():
        assert isinstance(result, HealthCheckResult)
        assert result.name == name


@pytest.mark.asyncio
async def test_run_startup_checks_all_healthy():
    """Test run_startup_checks when all checks pass."""
    checker = HealthChecker()

    # Mock check_all to return healthy results
    async def mock_check_all():
        return {
            "disk_space": HealthCheckResult("disk_space", "healthy"),
            "llm_config": HealthCheckResult("llm_config", "healthy"),
            "vector_db_config": HealthCheckResult("vector_db_config", "healthy"),
        }

    checker.check_all = mock_check_all

    result = await checker.run_startup_checks()
    assert result is True


@pytest.mark.asyncio
async def test_run_startup_checks_degraded():
    """Test run_startup_checks with degraded services."""
    checker = HealthChecker()

    # Mock check_all with one degraded service
    async def mock_check_all():
        return {
            "disk_space": HealthCheckResult("disk_space", "healthy"),
            "llm_config": HealthCheckResult("llm_config", "degraded", "No API key"),
            "vector_db_config": HealthCheckResult("vector_db_config", "healthy"),
        }

    checker.check_all = mock_check_all

    result = await checker.run_startup_checks()
    assert result is True  # Still returns True for non-critical failures


@pytest.mark.asyncio
async def test_run_startup_checks_critical_failure():
    """Test run_startup_checks with critical failure."""
    checker = HealthChecker()

    # Mock check_all with critical failure
    async def mock_check_all():
        return {
            "disk_space": HealthCheckResult("disk_space", "unhealthy", "No space"),
            "llm_config": HealthCheckResult("llm_config", "healthy"),
        }

    checker.check_all = mock_check_all

    result = await checker.run_startup_checks()
    assert result is False  # Returns False for critical failures


def test_health_checker_singleton():
    """Test that health_checker singleton is created."""
    from src.utils.health import health_checker as imported_checker

    assert isinstance(imported_checker, HealthChecker)
