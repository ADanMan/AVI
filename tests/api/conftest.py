"""
Pytest configuration for API tests.
"""
import os
import tempfile
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from config.settings import settings
from main import app
from src.api.auth import APIKeyManager, Role


@pytest.fixture
async def test_client():
    """Create async test client for API tests."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client


@pytest.fixture
def api_key_manager():
    """Create temporary API key manager for testing."""
    # Create temporary storage for test API keys
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name

    try:
        manager = APIKeyManager(storage_path=temp_path)
        yield manager
    finally:
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)


@pytest.fixture
def admin_api_key(api_key_manager):
    """Create admin API key for testing."""
    plaintext_key, api_key_obj = api_key_manager.create_api_key(
        name="Test Admin Key",
        role=Role.ADMIN,
        metadata={"test": True}
    )
    return plaintext_key


@pytest.fixture
def user_api_key(api_key_manager):
    """Create user API key for testing."""
    plaintext_key, api_key_obj = api_key_manager.create_api_key(
        name="Test User Key",
        role=Role.USER,
        metadata={"test": True}
    )
    return plaintext_key


@pytest.fixture
def readonly_api_key(api_key_manager):
    """Create readonly API key for testing."""
    plaintext_key, api_key_obj = api_key_manager.create_api_key(
        name="Test Readonly Key",
        role=Role.READONLY,
        metadata={"test": True}
    )
    return plaintext_key


@pytest.fixture
async def test_client_with_admin(test_client, admin_api_key):
    """Test client with admin API key in headers."""
    test_client.headers["X-API-Key"] = admin_api_key
    return test_client


@pytest.fixture
async def test_client_with_user(test_client, user_api_key):
    """Test client with user API key in headers."""
    test_client.headers["X-API-Key"] = user_api_key
    return test_client


@pytest.fixture
async def test_client_with_readonly(test_client, readonly_api_key):
    """Test client with readonly API key in headers."""
    test_client.headers["X-API-Key"] = readonly_api_key
    return test_client
