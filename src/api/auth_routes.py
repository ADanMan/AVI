"""
Authentication API routes.

Provides public endpoints for API key validation and authentication flows.
"""

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from src.api.auth import get_api_key_manager
from src.utils.logger import logger

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
    responses={404: {"description": "Not found"}},
)


# =====================
# Request/Response Models
# =====================


class ValidateKeyResponse(BaseModel):
    """Response model for API key validation."""

    valid: bool = Field(..., description="Whether the key is valid")
    message: str = Field(..., description="Validation message")
    key_name: str | None = Field(None, description="Name of the key if valid")
    role: str | None = Field(None, description="Role of the key if valid")


# =====================
# Endpoints
# =====================


@router.post(
    "/validate",
    response_model=ValidateKeyResponse,
    summary="Validate API key",
    description="""
    Validate an API key without requiring authentication.

    This endpoint is used by the UI to verify API keys during login.
    It does NOT require an existing API key to access.

    Returns information about the key if valid, or an error message if invalid.
    """,
)
async def validate_api_key(
    x_api_key: str = Header(..., alias="X-API-Key", description="API key to validate"),
) -> ValidateKeyResponse:
    """
    Validate an API key.

    This is a public endpoint that does NOT require authentication.
    It's used by the UI login form to verify API keys.

    Args:
        x_api_key: API key from X-API-Key header

    Returns:
        ValidateKeyResponse with validation result

    Example:
        ```
        POST /api/v1/auth/validate
        Headers:
            X-API-Key: avi_your_key_here

        Response:
        {
            "valid": true,
            "message": "API key is valid",
            "key_name": "My Application",
            "role": "user"
        }
        ```
    """
    try:
        manager = get_api_key_manager()
        api_key = manager.verify_key(x_api_key)

        if api_key is None:
            return ValidateKeyResponse(
                valid=False,
                message="Invalid API key or key has expired",
            )

        # Key is valid
        return ValidateKeyResponse(
            valid=True,
            message="API key is valid",
            key_name=api_key.name,
            role=api_key.role.value,
        )

    except Exception as e:
        logger.error(f"Error validating API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error validating API key: {e!s}",
        )


__all__ = ["router"]
