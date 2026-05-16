"""
Chat API routes for AVI.
Provides streaming and non-streaming chat endpoints with safety filters.
"""

import asyncio
import time
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.api.auth import APIKey, Role, optional_auth
from src.models.schemas import SafetyCheckRequest, SafetyScores
from src.services.filter_service import FilterService
from src.services.llm_adapter import LLMAdapter
from src.utils.logger import logger
from src.utils.token_counter import count_tokens


router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
    responses={404: {"description": "Not found"}},
)

# Lazy initialization of services to avoid blocking at import time
_llm_adapter = None
_filter_service = None


def get_llm_adapter() -> LLMAdapter:
    """Get or create LLMAdapter instance (lazy initialization)."""
    global _llm_adapter
    if _llm_adapter is None:
        _llm_adapter = LLMAdapter()
    return _llm_adapter


def get_filter_service() -> FilterService:
    """Get or create FilterService instance (lazy initialization)."""
    global _filter_service
    if _filter_service is None:
        _filter_service = FilterService()
    return _filter_service


# =====================
# Request/Response Models
# =====================


class ChatRequest(BaseModel):
    """Chat request with safety options."""

    message: str = Field(..., description="User message")
    conversation_id: str | None = Field(None, description="Conversation ID for history")
    enable_avi: bool = Field(True, description="Enable AVI safety filters")
    model: str | None = Field("gpt-4o-mini", description="LLM model to use")
    temperature: float | None = Field(0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int | None = Field(2048, gt=0, le=8192, description="Maximum tokens to generate")


class ChatResponse(BaseModel):
    """Non-streaming chat response."""

    message: str = Field(..., description="Assistant response")
    safety_scores: SafetyScores = Field(..., description="Safety scores")
    filtered: bool = Field(..., description="Whether content was filtered")
    model: str = Field(..., description="Model used")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")
    usage: dict | None = Field(None, description="Token usage (prompt_tokens, completion_tokens, total_tokens)")
    generation_time: float | None = Field(None, description="Generation time in seconds")


class StreamChunk(BaseModel):
    """Streaming response chunk."""

    type: str = Field(..., description="Chunk type: content, safety, metadata, done")
    content: str | None = Field(None, description="Content chunk")
    safety_scores: SafetyScores | None = Field(None, description="Safety scores")
    filtered: bool | None = Field(None, description="Whether content was filtered")
    metadata: dict | None = Field(None, description="Metadata")
    usage: dict | None = Field(None, description="Token usage")
    generation_time: float | None = Field(None, description="Generation time in seconds")


# =====================
# Helper Functions
# =====================


async def calculate_safety_scores(
    text: str, enable_avi: bool, is_input: bool = True
) -> tuple[SafetyScores, bool]:
    """
    Calculate safety scores for text using FilterService.

    Dynamically calculates scores for all triggered filters.
    Returns scores in [0.0, 1.0] where 1.0 = safe, 0.0 = unsafe.

    Args:
        text: Text to check
        enable_avi: Whether AVI is enabled
        is_input: True for input filtering, False for output

    Returns:
        Tuple of (SafetyScores, filtered)
    """
    if not enable_avi:
        # If AVI disabled, return perfect score
        return (
            SafetyScores(overall=1.0),
            False,
        )

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


async def generate_llm_response(
    message: str,
    model: str,
    temperature: float,
    max_tokens: int,
) -> AsyncGenerator[str, None]:
    """
    Generate LLM response using streaming via LLMAdapter.

    Args:
        message: User message
        model: Model name
        temperature: Sampling temperature
        max_tokens: Max tokens to generate

    Yields:
        Content chunks from LLM
    """
    try:
        # Use LLMAdapter for streaming response
        async for chunk in get_llm_adapter().generate_streaming_response(
            query=message,
            context=None,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield chunk

    except Exception as e:
        logger.error(f"Error generating LLM response: {e}")
        yield f"[Error: {e!s}]"


# =====================
# Endpoints
# =====================


@router.post("/complete", response_model=ChatResponse)
async def chat_complete(
    request: ChatRequest,
    api_key: APIKey | None = Depends(optional_auth(Role.USER)),
) -> ChatResponse:
    """
    Complete chat request (non-streaming).

    Returns full response at once with safety scores.
    """
    try:
        logger.info(
            f"Chat complete request: enable_avi={request.enable_avi}, model={request.model}"
        )

        # Start timing
        start_time = time.time()

        # Check input safety
        input_scores, input_filtered = await calculate_safety_scores(
            request.message, request.enable_avi, is_input=True
        )

        if input_filtered:
            generation_time = time.time() - start_time
            prompt_tokens = count_tokens(request.message, request.model or "gpt-4o-mini")
            return ChatResponse(
                message="[FILTERED] Your message was blocked by AVI safety filters.",
                safety_scores=input_scores,
                filtered=True,
                model=request.model or "gpt-4o-mini",
                metadata={"reason": "Input filtered"},
                usage={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": 0,
                    "total_tokens": prompt_tokens,
                },
                generation_time=generation_time,
            )

        # Generate response
        full_response = ""
        async for chunk in generate_llm_response(
            request.message,
            request.model or "gpt-4o-mini",
            request.temperature or 0.7,
            request.max_tokens or 2048,
        ):
            full_response += chunk

        # Calculate usage metrics
        prompt_tokens = count_tokens(request.message, request.model or "gpt-4o-mini")
        completion_tokens = count_tokens(full_response, request.model or "gpt-4o-mini")
        total_tokens = prompt_tokens + completion_tokens

        # Check output safety
        output_scores, output_filtered = await calculate_safety_scores(
            full_response, request.enable_avi, is_input=False
        )

        generation_time = time.time() - start_time

        if output_filtered:
            return ChatResponse(
                message=f"[FILTERED] The AI response was blocked by AVI safety filters. Safety score: {output_scores.overall:.2f}",
                safety_scores=output_scores,
                filtered=True,
                model=request.model or "gpt-4o-mini",
                metadata={"reason": "Output filtered"},
                usage={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                },
                generation_time=generation_time,
            )

        return ChatResponse(
            message=full_response,
            safety_scores=output_scores,
            filtered=False,
            model=request.model or "gpt-4o-mini",
            metadata={},
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
            generation_time=generation_time,
        )

    except Exception as e:
        logger.error(f"Error in chat_complete: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    api_key: APIKey | None = Depends(optional_auth(Role.USER)),
):
    """
    Streaming chat request using Server-Sent Events.

    Streams content chunks and safety information in real-time.
    """

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            logger.info(
                f"Chat stream request: enable_avi={request.enable_avi}, model={request.model}"
            )

            # Start timing
            start_time = time.time()

            # Check input safety
            input_scores, input_filtered = await calculate_safety_scores(
                request.message, request.enable_avi, is_input=True
            )

            if input_filtered:
                # Calculate usage for filtered input
                prompt_tokens = count_tokens(request.message, request.model or "gpt-4o-mini")
                generation_time = time.time() - start_time

                # Send filtered message
                chunk = StreamChunk(
                    type="content",
                    content="[FILTERED] Your message was blocked by AVI safety filters.",
                    filtered=True,
                )
                yield f"data: {chunk.model_dump_json()}\n\n"

                # Send safety scores
                chunk = StreamChunk(
                    type="safety",
                    safety_scores=input_scores,
                    filtered=True,
                )
                yield f"data: {chunk.model_dump_json()}\n\n"

                # Send usage and metadata
                chunk = StreamChunk(
                    type="metadata",
                    metadata={"model": request.model or "gpt-4o-mini"},
                    usage={
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": 0,
                        "total_tokens": prompt_tokens,
                    },
                    generation_time=generation_time,
                )
                yield f"data: {chunk.model_dump_json()}\n\n"

                # Send done
                yield 'data: {"type":"done"}\n\n'
                return

            # Stream LLM response
            full_response = ""
            async for content_chunk in generate_llm_response(
                request.message,
                request.model or "gpt-4o-mini",
                request.temperature or 0.7,
                request.max_tokens or 2048,
            ):
                full_response += content_chunk

                # Send content chunk
                chunk = StreamChunk(type="content", content=content_chunk)
                yield f"data: {chunk.model_dump_json()}\n\n"

                # Small delay to prevent overwhelming client
                await asyncio.sleep(0.01)

            # Calculate usage metrics
            prompt_tokens = count_tokens(request.message, request.model or "gpt-4o-mini")
            completion_tokens = count_tokens(full_response, request.model or "gpt-4o-mini")
            total_tokens = prompt_tokens + completion_tokens
            generation_time = time.time() - start_time

            # Calculate final safety scores
            output_scores, output_filtered = await calculate_safety_scores(
                full_response, request.enable_avi, is_input=False
            )

            # Send safety information
            chunk = StreamChunk(
                type="safety",
                safety_scores=output_scores,
                filtered=output_filtered,
            )
            yield f"data: {chunk.model_dump_json()}\n\n"

            # Send metadata with usage and timing
            chunk = StreamChunk(
                type="metadata",
                metadata={"model": request.model or "gpt-4o-mini"},
                usage={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                },
                generation_time=generation_time,
            )
            yield f"data: {chunk.model_dump_json()}\n\n"

            # Send done signal
            yield 'data: {"type":"done"}\n\n'

        except Exception as e:
            logger.error(f"Error in chat_stream: {e}")
            # Send error chunk
            error_chunk = StreamChunk(
                type="metadata",
                metadata={"error": str(e)},
            )
            yield f"data: {error_chunk.model_dump_json()}\n\n"
            yield 'data: {"type":"done"}\n\n'

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.post("/safety/check", response_model=SafetyScores)
async def check_safety(
    request: SafetyCheckRequest,
    api_key: APIKey | None = Depends(optional_auth(Role.READONLY)),
) -> SafetyScores:
    """
    Check safety of text without sending to LLM.

    Useful for pre-checking user input before submission.
    """
    try:
        scores, _ = await calculate_safety_scores(request.text, enable_avi=True, is_input=True)
        return scores

    except Exception as e:
        logger.error(f"Error in check_safety: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Export router
__all__ = ["router"]
