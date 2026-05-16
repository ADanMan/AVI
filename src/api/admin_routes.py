"""
Admin API routes for system management.

Provides endpoints for API key management, system configuration, and admin operations.
All endpoints require ADMIN role.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.api.auth import APIKey, APIKeyManager, Role, get_api_key_manager, require_role
from src.utils.logger import logger

# Create admin router
router = APIRouter(
    prefix="/admin",  # Admin routes under /api/v1/admin
    tags=["Admin - API Key Management"],
    dependencies=[Depends(require_role(Role.ADMIN))],  # All admin routes require ADMIN role
    responses={
        403: {"description": "Insufficient permissions"},
        401: {"description": "Invalid or missing API key"},
    },
)


# =====================
# Request/Response Models
# =====================


class CreateAPIKeyRequest(BaseModel):
    """Request model for creating a new API key."""

    name: str = Field(
        ..., description="Human-readable name for the key", min_length=1, max_length=100
    )
    role: Role = Field(default=Role.USER, description="Access role (admin, user, readonly)")
    expires_days: int | None = Field(
        default=None,
        description="Number of days until expiration (None = never expires)",
        ge=1,
        le=3650,  # Max 10 years
    )
    metadata: dict = Field(
        default_factory=dict, description="Optional metadata (tags, owner, etc.)"
    )


class CreateAPIKeyResponse(BaseModel):
    """Response model for API key creation."""

    api_key: str = Field(
        ..., description="The plaintext API key (SAVE THIS - it won't be shown again!)"
    )
    key_hash: str = Field(..., description="SHA-256 hash of the key (for reference)")
    name: str
    role: Role
    created_at: datetime
    expires_at: datetime | None
    message: str = Field(
        default="API key created successfully. Save the key securely - it cannot be retrieved later!"
    )


class APIKeyListItem(BaseModel):
    """List item model for API keys (without sensitive data)."""

    key_hash: str = Field(..., description="SHA-256 hash (first 16 chars for reference)")
    name: str
    role: Role
    created_at: datetime
    expires_at: datetime | None
    is_active: bool
    last_used: datetime | None
    is_expired: bool
    metadata: dict


class RevokeAPIKeyRequest(BaseModel):
    """Request model for revoking an API key."""

    key_hash: str = Field(..., description="SHA-256 hash of the key to revoke")


class DeleteAPIKeyRequest(BaseModel):
    """Request model for deleting an API key."""

    key_hash: str = Field(..., description="SHA-256 hash of the key to delete")


class APIKeyOperationResponse(BaseModel):
    """Generic response for API key operations."""

    success: bool
    message: str
    key_hash: str | None = None


# =====================
# API Key Management Endpoints
# =====================


@router.post(
    "/keys",
    response_model=CreateAPIKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new API key",
    description="""
    Create a new API key with specified role and optional expiration.

    **IMPORTANT:** The plaintext API key is returned ONLY once in this response.
    Save it securely - it cannot be retrieved later!

    Roles:
    - `admin`: Full access including key management
    - `user`: Standard access to query, filter, RAG, documents
    - `readonly`: Read-only access to status and stats
    """,
)
async def create_api_key(
    request: CreateAPIKeyRequest,
    current_api_key: APIKey = Depends(require_role(Role.ADMIN)),
    manager: APIKeyManager = Depends(get_api_key_manager),
) -> CreateAPIKeyResponse:
    """
    Create a new API key.

    Only ADMIN role can create API keys.
    """
    try:
        # Create the key
        plaintext_key, api_key = manager.create_api_key(
            name=request.name,
            role=request.role,
            expires_days=request.expires_days,
            metadata=request.metadata,
        )

        logger.info(
            f"Admin '{current_api_key.name}' created new API key '{api_key.name}' with role '{api_key.role.value}'"
        )

        return CreateAPIKeyResponse(
            api_key=plaintext_key,
            key_hash=api_key.key_hash,
            name=api_key.name,
            role=api_key.role,
            created_at=api_key.created_at,
            expires_at=api_key.expires_at,
        )

    except Exception as e:
        logger.error(f"Failed to create API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create API key: {e!s}",
        )


@router.get(
    "/keys",
    response_model=list[APIKeyListItem],
    summary="List all API keys",
    description="""
    List all API keys in the system (without plaintext keys).

    Shows key metadata including:
    - Hash prefix (for identification)
    - Name and role
    - Creation/expiration dates
    - Active status
    - Last used timestamp
    """,
)
async def list_api_keys(
    current_api_key: APIKey = Depends(require_role(Role.ADMIN)),
    manager: APIKeyManager = Depends(get_api_key_manager),
) -> list[APIKeyListItem]:
    """
    List all API keys.

    Only ADMIN role can list API keys.
    """
    try:
        keys = manager.list_keys()

        return [
            APIKeyListItem(
                key_hash=k.key_hash[:16] + "...",  # Show only first 16 chars
                name=k.name,
                role=k.role,
                created_at=k.created_at,
                expires_at=k.expires_at,
                is_active=k.is_active,
                last_used=k.last_used,
                is_expired=k.is_expired(),
                metadata=k.metadata,
            )
            for k in keys
        ]

    except Exception as e:
        logger.error(f"Failed to list API keys: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list API keys: {e!s}",
        )


@router.post(
    "/keys/revoke",
    response_model=APIKeyOperationResponse,
    summary="Revoke API key",
    description="""
    Revoke (deactivate) an API key.

    The key will remain in the system but cannot be used for authentication.
    Use DELETE to permanently remove a key.
    """,
)
async def revoke_api_key(
    request: RevokeAPIKeyRequest,
    current_api_key: APIKey = Depends(require_role(Role.ADMIN)),
    manager: APIKeyManager = Depends(get_api_key_manager),
) -> APIKeyOperationResponse:
    """
    Revoke an API key by its hash.

    Only ADMIN role can revoke API keys.
    """
    try:
        success = manager.revoke_key(request.key_hash)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"API key with hash '{request.key_hash[:16]}...' not found",
            )

        logger.info(
            f"Admin '{current_api_key.name}' revoked API key with hash '{request.key_hash[:16]}...'"
        )

        return APIKeyOperationResponse(
            success=True,
            message="API key revoked successfully",
            key_hash=request.key_hash[:16] + "...",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to revoke API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke API key: {e!s}",
        )


@router.delete(
    "/keys",
    response_model=APIKeyOperationResponse,
    summary="Delete API key",
    description="""
    Permanently delete an API key from the system.

    This action cannot be undone. Use revoke if you want to keep the key in the system.
    """,
)
async def delete_api_key(
    request: DeleteAPIKeyRequest,
    current_api_key: APIKey = Depends(require_role(Role.ADMIN)),
    manager: APIKeyManager = Depends(get_api_key_manager),
) -> APIKeyOperationResponse:
    """
    Permanently delete an API key.

    Only ADMIN role can delete API keys.
    """
    try:
        success = manager.delete_key(request.key_hash)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"API key with hash '{request.key_hash[:16]}...' not found",
            )

        logger.info(
            f"Admin '{current_api_key.name}' deleted API key with hash '{request.key_hash[:16]}...'"
        )

        return APIKeyOperationResponse(
            success=True,
            message="API key deleted permanently",
            key_hash=request.key_hash[:16] + "...",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete API key: {e!s}",
        )


__all__ = ["router"]
