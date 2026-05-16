"""
API Key Authentication and Authorization System.

Provides API key-based authentication with role-based access control (RBAC).
Keys are stored hashed (SHA-256) in JSON format for security.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from config.settings import settings
from src.utils.logger import logger


class Role(str, Enum):
    """Available roles for API keys with hierarchical permissions."""

    ADMIN = "admin"  # Full access: all endpoints + key management
    USER = "user"  # Standard access: query, filter, RAG, documents
    READONLY = "readonly"  # Read-only: status, stats, health checks


# Role hierarchy: each role includes permissions of roles below it
ROLE_HIERARCHY = {
    Role.ADMIN: {Role.ADMIN, Role.USER, Role.READONLY},
    Role.USER: {Role.USER, Role.READONLY},
    Role.READONLY: {Role.READONLY},
}


class APIKey(BaseModel):
    """
    API Key model for authentication and authorization.

    Attributes:
        key_hash: SHA-256 hash of the actual API key (never store plaintext!)
        name: Human-readable name/description for the key
        role: Access role (admin, user, readonly)
        created_at: Timestamp when key was created
        expires_at: Optional expiration timestamp
        is_active: Whether the key is currently active
        last_used: Timestamp of last successful authentication
        metadata: Optional additional metadata (tags, owner, etc.)
    """

    key_hash: str = Field(..., description="SHA-256 hash of API key")
    name: str = Field(..., description="Human-readable key name", min_length=1, max_length=100)
    role: Role = Field(default=Role.USER, description="Access role")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    expires_at: datetime | None = Field(default=None, description="Expiration timestamp")
    is_active: bool = Field(default=True, description="Whether key is active")
    last_used: datetime | None = Field(default=None, description="Last use timestamp")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    def is_expired(self) -> bool:
        """Check if the API key has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def is_valid(self) -> bool:
        """Check if the API key is valid (active and not expired)."""
        return self.is_active and not self.is_expired()

    def has_permission(self, required_role: Role) -> bool:
        """Check if this key's role has permission for the required role."""
        return required_role in ROLE_HIERARCHY.get(self.role, set())


class APIKeyManager:
    """
    Manager for API key operations: creation, verification, revocation.

    Uses JSON file storage with SHA-256 hashed keys for security.
    Keys are never stored in plaintext.
    """

    def __init__(self, storage_path: Path | str | None = None):
        """
        Initialize API Key Manager.

        Args:
            storage_path: Path to JSON storage file. Defaults to data/security/api_keys.json
        """
        if storage_path is None:
            storage_path = Path(settings.DATA_DIR) / "security" / "api_keys.json"
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize with empty storage if file doesn't exist
        if not self.storage_path.exists():
            self._save_keys([])
            logger.info(f"Initialized API key storage at {self.storage_path}")

    def generate_key(self) -> str:
        """
        Generate a secure random API key.

        Returns:
            str: API key in format 'avi_<32-char-base64-string>'
        """
        random_part = secrets.token_urlsafe(32)
        return f"avi_{random_part}"

    def hash_key(self, key: str) -> str:
        """
        Hash an API key using SHA-256.

        Args:
            key: Plaintext API key

        Returns:
            str: Hex-encoded SHA-256 hash
        """
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def create_api_key(
        self,
        name: str,
        role: Role = Role.USER,
        expires_days: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[str, APIKey]:
        """
        Create a new API key.

        Args:
            name: Human-readable name for the key
            role: Access role (admin, user, readonly)
            expires_days: Optional number of days until expiration
            metadata: Optional additional metadata

        Returns:
            tuple: (plaintext_key, APIKey object)
                IMPORTANT: The plaintext key is returned ONLY here and never stored!

        Example:
            >>> manager = APIKeyManager()
            >>> key, api_key_obj = manager.create_api_key("My App", Role.USER, expires_days=90)
            >>> print(f"Save this key securely: {key}")
        """
        # Generate plaintext key
        plaintext_key = self.generate_key()

        # Calculate expiration
        expires_at = None
        if expires_days is not None and expires_days > 0:
            expires_at = datetime.utcnow() + timedelta(days=expires_days)

        # Create API key object (with hashed key!)
        api_key = APIKey(
            key_hash=self.hash_key(plaintext_key),
            name=name,
            role=role,
            expires_at=expires_at,
            metadata=metadata or {},
        )

        # Load existing keys, add new one, save
        keys = self._load_keys()
        keys.append(api_key)
        self._save_keys(keys)

        logger.info(f"Created new API key '{name}' with role '{role.value}'")

        # Return BOTH plaintext (for user to save) and object (for reference)
        return plaintext_key, api_key

    def verify_key(self, key: str) -> APIKey | None:
        """
        Verify an API key and return the APIKey object if valid.

        Args:
            key: Plaintext API key to verify

        Returns:
            APIKey object if valid, None if invalid/expired/inactive

        Side effects:
            Updates last_used timestamp if key is valid
        """
        # Hash the provided key
        key_hash = self.hash_key(key)

        # Load all keys and find matching hash
        keys = self._load_keys()
        for api_key in keys:
            if api_key.key_hash == key_hash:
                # Check if key is valid
                if not api_key.is_valid():
                    reason = "inactive" if not api_key.is_active else "expired"
                    logger.warning(f"Rejected {reason} API key: {api_key.name}")
                    return None

                # Update last_used timestamp
                api_key.last_used = datetime.utcnow()
                self._save_keys(keys)

                logger.debug(f"Verified API key: {api_key.name} (role: {api_key.role.value})")
                return api_key

        logger.warning("Invalid API key provided (hash not found)")
        return None

    def list_keys(self) -> list[APIKey]:
        """
        List all API keys.

        Returns:
            List of all APIKey objects (hashes only, never plaintext!)
        """
        return self._load_keys()

    def revoke_key(self, key_hash: str) -> bool:
        """
        Revoke (deactivate) an API key by its hash.

        Args:
            key_hash: SHA-256 hash of the key to revoke

        Returns:
            True if key was found and revoked, False otherwise
        """
        keys = self._load_keys()
        for api_key in keys:
            if api_key.key_hash == key_hash:
                api_key.is_active = False
                self._save_keys(keys)
                logger.info(f"Revoked API key: {api_key.name}")
                return True

        logger.warning(f"Attempted to revoke non-existent key hash: {key_hash[:16]}...")
        return False

    def delete_key(self, key_hash: str) -> bool:
        """
        Permanently delete an API key by its hash.

        Args:
            key_hash: SHA-256 hash of the key to delete

        Returns:
            True if key was found and deleted, False otherwise
        """
        keys = self._load_keys()
        original_count = len(keys)
        keys = [k for k in keys if k.key_hash != key_hash]

        if len(keys) < original_count:
            self._save_keys(keys)
            logger.info(f"Deleted API key with hash: {key_hash[:16]}...")
            return True

        logger.warning(f"Attempted to delete non-existent key hash: {key_hash[:16]}...")
        return False

    def _load_keys(self) -> list[APIKey]:
        """
        Load API keys from JSON storage.

        Returns:
            List of APIKey objects
        """
        if not self.storage_path.exists():
            return []

        try:
            with open(self.storage_path) as f:
                data = json.load(f)
                return [APIKey(**k) for k in data.get("keys", [])]
        except Exception as e:
            logger.error(f"Failed to load API keys from {self.storage_path}: {e}")
            return []

    def _save_keys(self, keys: list[APIKey]) -> None:
        """
        Save API keys to JSON storage.

        Args:
            keys: List of APIKey objects to save
        """
        try:
            with open(self.storage_path, "w") as f:
                json.dump(
                    {"keys": [k.model_dump(mode="json") for k in keys]},
                    f,
                    indent=2,
                    default=str,  # Handle datetime serialization
                )
        except Exception as e:
            logger.error(f"Failed to save API keys to {self.storage_path}: {e}")
            raise


# Global API key manager instance
_api_key_manager: APIKeyManager | None = None


def get_api_key_manager() -> APIKeyManager:
    """
    Get the global API key manager instance (singleton).

    Returns:
        APIKeyManager instance
    """
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
    return _api_key_manager


# Security scheme for Swagger UI - creates "Authorize" button
api_key_header = APIKeyHeader(
    name="X-API-Key",
    description="API Key for authentication. Get your key from admin or bootstrap script.",
    auto_error=False,  # Don't auto-raise errors, we handle them manually
)


async def get_current_api_key(
    x_api_key: str = Depends(api_key_header),
) -> APIKey:
    """
    FastAPI dependency to get and verify the current API key.

    Args:
        x_api_key: API key from X-API-Key header

    Returns:
        APIKey object if valid

    Raises:
        HTTPException: 401 if key is invalid, 403 if key is expired/inactive

    Usage:
        @app.get("/protected")
        async def protected_endpoint(api_key: APIKey = Depends(get_current_api_key)):
            return {"message": f"Hello {api_key.name}"}
    """
    if x_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Click 'Authorize' button and enter your key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    manager = get_api_key_manager()
    api_key = manager.verify_key(x_api_key)

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return api_key


def require_role(required_role: Role):
    """
    FastAPI dependency factory to require a specific role.

    Args:
        required_role: Minimum role required

    Returns:
        Dependency function that checks role permissions

    Usage:
        @app.post("/admin/users")
        async def create_user(api_key: APIKey = Depends(require_role(Role.ADMIN))):
            return {"message": "User created"}
    """

    async def check_role(api_key: APIKey = Depends(get_current_api_key)) -> APIKey:
        if not api_key.has_permission(required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role.value}, your role: {api_key.role.value}",
            )
        return api_key

    return check_role


async def get_optional_api_key(
    x_api_key: str | None = Depends(api_key_header),
) -> APIKey | None:
    """
    FastAPI dependency to get optional API key.

    Returns APIKey if valid key is provided, None otherwise.
    Does not raise exceptions - useful for endpoints that support both authenticated and anonymous access.

    Args:
        x_api_key: Optional API key from X-API-Key header

    Returns:
        APIKey object if valid key provided, None otherwise
    """
    if x_api_key is None:
        return None

    manager = get_api_key_manager()
    return manager.verify_key(x_api_key)


def optional_auth(required_role: Role = Role.READONLY):
    """
    FastAPI dependency factory for optional authentication based on settings.

    If settings.REQUIRE_API_KEY is True, authentication is enforced.
    Otherwise, authentication is optional but role is checked if key is provided.

    Args:
        required_role: Minimum role required if authentication is enforced

    Returns:
        Dependency function that optionally checks authentication

    Usage:
        @app.get("/data")
        async def get_data(api_key: APIKey | None = Depends(optional_auth(Role.USER))):
            if api_key:
                return {"message": f"Hello {api_key.name}"}
            return {"message": "Hello anonymous user"}
    """

    async def check_optional_auth(
        x_api_key: str | None = Depends(api_key_header),
    ) -> APIKey | None:
        # If authentication is required, enforce it
        if settings.REQUIRE_API_KEY:
            if x_api_key is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key required. Click 'Authorize' button and enter your key.",
                    headers={"WWW-Authenticate": "ApiKey"},
                )

            manager = get_api_key_manager()
            api_key = manager.verify_key(x_api_key)

            if api_key is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid API key",
                    headers={"WWW-Authenticate": "ApiKey"},
                )

            if not api_key.has_permission(required_role):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required: {required_role.value}, your role: {api_key.role.value}",
                )

            return api_key

        # Authentication is optional - verify if provided
        if x_api_key is not None:
            manager = get_api_key_manager()
            api_key = manager.verify_key(x_api_key)

            if api_key and not api_key.has_permission(required_role):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required: {required_role.value}, your role: {api_key.role.value}",
                )

            return api_key

        # No key provided and not required
        return None

    return check_optional_auth


__all__ = [
    "ROLE_HIERARCHY",
    "APIKey",
    "APIKeyManager",
    "Role",
    "api_key_header",
    "get_api_key_manager",
    "get_current_api_key",
    "get_optional_api_key",
    "optional_auth",
    "require_role",
]
