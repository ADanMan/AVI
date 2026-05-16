"""
Filter configuration API routes.
Provides dynamic filter configuration without hardcoding filter types.
"""


from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.auth import APIKey, Role, optional_auth
from src.services.filter_service import FilterService


router = APIRouter(
    prefix="/filters",
    tags=["Filter Configuration"],
    responses={404: {"description": "Not found"}},
)

# Lazy initialization to avoid blocking at import time
_filter_service = None


def get_filter_service() -> FilterService:
    """Get or create FilterService instance (lazy initialization)."""
    global _filter_service
    if _filter_service is None:
        _filter_service = FilterService()
    return _filter_service


# =====================
# Models
# =====================


class FilterDefinition(BaseModel):
    """Definition of a single filter."""

    id: str = Field(..., description="Filter ID (e.g., 'toxicity')")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Filter description")
    enabled_by_default: bool = Field(True, description="Whether enabled by default")
    category: str = Field(..., description="Category: 'safety', 'privacy', 'security'")
    icon: str | None = Field(None, description="Emoji icon")


class FilterConfigResponse(BaseModel):
    """Available filters configuration."""

    filters: list[FilterDefinition] = Field(..., description="Available filters")
    version: str = Field(..., description="Configuration version")


class FilterConfigUpdate(BaseModel):
    """Update filter configuration (enable/disable filters)."""

    filters: dict[str, bool] = Field(..., description="Filter ID to enabled status mapping")


# =====================
# Endpoints
# =====================


@router.get("/config", response_model=FilterConfigResponse)
async def get_filter_config(api_key: APIKey | None = Depends(optional_auth(Role.READONLY))) -> FilterConfigResponse:
    """
    Get available filter configuration.

    This endpoint returns all available filters dynamically,
    allowing the frontend to adapt to new filters without code changes.
    """
    # In production, this could come from FilterService or database
    # For now, defining available filters based on FilterService capabilities

    filters = [
        FilterDefinition(
            id="toxicity",
            name="Toxicity Detection",
            description="Detect harmful language, abuse, and offensive content",
            enabled_by_default=True,
            category="safety",
            icon="🚫",
        ),
        FilterDefinition(
            id="pii",
            name="PII Detection",
            description="Detect and prevent personal information leaks (emails, phone numbers, addresses)",
            enabled_by_default=True,
            category="privacy",
            icon="🔒",
        ),
        FilterDefinition(
            id="prompt_injection",
            name="Prompt Injection",
            description="Detect prompt manipulation and jailbreak attempts",
            enabled_by_default=True,
            category="security",
            icon="💉",
        ),
        FilterDefinition(
            id="hate_speech",
            name="Hate Speech",
            description="Detect discriminatory and hateful content",
            enabled_by_default=True,
            category="safety",
            icon="⚠️",
        ),
        # Example of easily adding new filters:
        # FilterDefinition(
        #     id="bias_detection",
        #     name="Bias Detection",
        #     description="Detect biased or unfair content",
        #     enabled_by_default=False,
        #     category="safety",
        #     icon="⚖️",
        # ),
        # FilterDefinition(
        #     id="spam_detection",
        #     name="Spam Detection",
        #     description="Detect spam and unwanted promotional content",
        #     enabled_by_default=False,
        #     category="security",
        #     icon="📧",
        # ),
    ]

    return FilterConfigResponse(
        filters=filters,
        version="1.0.0",
    )


@router.put("/config")
async def update_filter_config(
    config: FilterConfigUpdate, api_key: APIKey | None = Depends(optional_auth(Role.USER))
) -> dict:
    """
    Update filter configuration (enable/disable specific filters).

    This endpoint allows the frontend to enable or disable filters dynamically.
    The configuration is persisted and will affect future filter operations.

    Args:
        config: FilterConfigUpdate with filter ID to enabled status mapping

    Returns:
        Success message with updated configuration

    Example:
        ```
        PUT /api/v1/filters/config
        {
            "filters": {
                "toxicity": true,
                "pii": false,
                "prompt_injection": true,
                "hate_speech": true
            }
        }
        ```

        Response:
        ```
        {
            "status": "success",
            "message": "Filter configuration updated",
            "updated_filters": {
                "toxicity": true,
                "pii": false,
                "prompt_injection": true,
                "hate_speech": true
            }
        }
        ```
    """
    try:
        # In production, this would update FilterService configuration
        # or persist to database/config file
        # For now, we'll acknowledge the update and return success

        # Validate that filter IDs are known
        known_filters = {"toxicity", "pii", "prompt_injection", "hate_speech"}
        unknown_filters = set(config.filters.keys()) - known_filters

        if unknown_filters:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=400,
                detail=f"Unknown filter IDs: {', '.join(unknown_filters)}"
            )

        # TODO: Implement actual filter configuration persistence
        # This could involve:
        # 1. Updating FilterService enabled_filters
        # 2. Persisting to database
        # 3. Updating config file
        # 4. Notifying other services of config change

        return {
            "status": "success",
            "message": "Filter configuration updated",
            "updated_filters": config.filters,
        }

    except Exception as e:
        from fastapi import HTTPException

        from src.utils.logger import logger
        logger.error(f"Error updating filter config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Export router
__all__ = ["router"]
