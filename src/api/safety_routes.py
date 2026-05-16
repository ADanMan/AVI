"""
Safety API routes for AVI.
Provides safety checking endpoints for content validation.
"""


from fastapi import APIRouter, Depends, HTTPException

from src.api.auth import APIKey, Role, optional_auth
from src.models.schemas import SafetyCheckRequest, SafetyScores
from src.services.filter_service import FilterService
from src.utils.logger import logger


router = APIRouter(
    prefix="/safety",
    tags=["Safety"],
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
# Helper Functions
# =====================


async def calculate_safety_scores(
    text: str, is_input: bool = True
) -> tuple[SafetyScores, bool]:
    """
    Calculate safety scores for text using FilterService.

    Dynamically calculates scores for all triggered filters.
    Returns scores in [0.0, 1.0] where 1.0 = safe, 0.0 = unsafe.

    Args:
        text: Text to check
        is_input: True for input filtering, False for output

    Returns:
        Tuple of (SafetyScores, filtered)
    """
    try:
        # Run FilterService
        if is_input:
            filter_result = await get_filter_service().filter_input(text, use_llm=False)
        else:
            filter_result = await get_filter_service().filter_output(text, use_llm=False)

        # Convert filter matches to safety scores
        # Score calculation: 1.0 = perfectly safe, 0.0 = completely unsafe
        # Formula: 1.0 - (risk_level / 10.0) * relevance_score
        filter_scores: dict[str, float] = {}

        for match in filter_result.matches:
            category = match.category
            # Calculate safety score from risk_level (1-10) and relevance_score (0-1)
            # risk_level 1 = low risk, 10 = critical risk
            risk_factor = match.risk_level / 10.0
            safety_score = max(0.0, 1.0 - (risk_factor * match.relevance_score))

            # Keep the lowest score for each category (most restrictive)
            if category not in filter_scores:
                filter_scores[category] = safety_score
            else:
                filter_scores[category] = min(filter_scores[category], safety_score)

        # If no matches, all categories are safe
        if not filter_scores:
            filter_scores = {}  # Empty dict, only overall score

        # Overall is minimum of all category scores, or 1.0 if no matches
        overall_score = min(filter_scores.values()) if filter_scores else 1.0

        # Consider filtered if was_modified or overall score below threshold
        filtered = filter_result.was_modified or overall_score < 0.5

        # Create SafetyScores with dynamic fields
        return (
            SafetyScores(overall=overall_score, **filter_scores),
            filtered,
        )

    except Exception as e:
        logger.error(f"Error calculating safety scores: {e}")
        # On error, be conservative and mark as unsafe
        return (
            SafetyScores(overall=0.0),
            True,
        )


# =====================
# Endpoints
# =====================


@router.post("/check", response_model=SafetyScores)
async def check_safety(
    request: SafetyCheckRequest, api_key: APIKey | None = Depends(optional_auth(Role.READONLY))
) -> SafetyScores:
    """
    Check safety of text without sending to LLM.

    Useful for pre-checking user input before submission.
    This endpoint provides content safety validation using AVI's filter service.

    Args:
        request: SafetyCheckRequest with text to check

    Returns:
        SafetyScores: Safety scores for the provided text

    Example:
        ```
        POST /api/v1/safety/check
        {
            "text": "Hello, how are you?"
        }
        ```

        Response:
        ```
        {
            "overall": 1.0,
            "toxicity": 1.0,
            "pii": 1.0
        }
        ```
    """
    try:
        scores, _ = await calculate_safety_scores(request.text, is_input=True)
        return scores

    except Exception as e:
        logger.error(f"Error in check_safety: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Export router
__all__ = ["router"]
