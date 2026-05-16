import json
from datetime import datetime
from typing import Optional, Union

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, HttpUrl

from config.settings import settings
from src.api.auth import APIKey, Role, optional_auth

# Import settings, chat, filter config, experiments, and integrations routes
from src.api import (
    auth_routes,
    chat_routes,
    experiments_routes,
    filter_config_routes,
    integrations_routes,
    safety_routes,
    settings_routes,
)
from src.core.rag_system import RAGSystem
from src.core.streaming_guard import StreamingGuard, StreamingGuardMode
from src.models.schemas import (
    CSVUploadResponse,
    FilteredContent,
    FilteringOptions,
    IndexingStatusResponse,
    LLMConfigurationUpdate,
    PromptPreviewRequest,
    PromptPreviewResponse,
    PromptTemplateResponse,
    PromptTemplateUpdateRequest,
    QueryRequest,
    QueryResponse,
    RuleDocument,
    RuleLinkRequest,
)
from src.services.indexing_service import IndexingService
from src.services.llm_adapter import LLMAdapter
from src.services.vector_db import VectorDBService
from src.utils.logger import logger


# Create router instead of application
router = APIRouter(
    prefix="/api/v1",  # Prefix for all routes of this router (API versioning)
    # Note: Tags are defined per-endpoint for better organization in Swagger UI
    responses={404: {"description": "Not found"}},  # Common responses for all endpoints
)


# Lazy initialization of system components to avoid blocking at import time
_rag_system = None
_vector_db = None
_indexing_service = None


def get_rag_system() -> RAGSystem:
    """Get or create RAGSystem instance (lazy initialization)."""
    global _rag_system
    if _rag_system is None:
        _rag_system = RAGSystem()
    return _rag_system


def get_vector_db() -> VectorDBService:
    """Get or create VectorDBService instance (lazy initialization)."""
    global _vector_db
    if _vector_db is None:
        _vector_db = VectorDBService()
    return _vector_db


def get_indexing_service() -> IndexingService:
    """Get or create IndexingService instance (lazy initialization)."""
    global _indexing_service
    if _indexing_service is None:
        _indexing_service = IndexingService(get_vector_db())
    return _indexing_service

# =====================
# Query & Generation
# =====================


@router.post(
    "/query",
    response_model=QueryResponse,
    tags=["Query & Generation"],
    summary="Process a user query with filtering and RAG",
    description="""
Primary endpoint for handling user questions. Before generating a reply the system:

1. Checks the text against safety rules.
2. Retrieves related documents for a RAG-enhanced response when needed.
3. Crafts and post-filters the final answer.

Error codes:
- **422** — invalid request (for example, an empty query).
- **500** — unexpected failure when calling the stores or the LLM.
""",
    responses={
        200: {
            "description": "Successful safe response with additional diagnostics.",
            "content": {
                "application/json": {
                    "example": {
                        "response": "The AVI system uses filters and documents to answer safely.",
                        "context_used": True,
                        "relevance_scores": [0.92, 0.87],
                        "processing_time": 0.42,
                        "timestamp": "2024-05-20T11:05:12",
                        "input_filter_result": None,
                        "output_filter_result": None,
                    }
                }
            },
        },
        422: {
            "description": "Request body validation error.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "query"],
                                "msg": "field required",
                                "type": "value_error.missing",
                            }
                        ]
                    }
                }
            },
        },
        500: {
            "description": "Internal service error.",
            "content": {"application/json": {"example": {"detail": "Vector DB is not available"}}},
        },
    },
)
async def process_query(
    request: QueryRequest,
    rag_mode: bool = Query(
        True,
        description="Whether to retrieve related documents (RAG) when answering.",
        examples=[True],
    ),
    api_key: APIKey | None = Depends(optional_auth(Role.USER)),
):
    """
    Process user query through the system.
    Supports both RAG mode and direct LLM queries.
    """
    try:
        result = await get_rag_system().process_query(
            query=request.query,
            use_cache=request.use_cache,
            rag_mode=rag_mode,
            model_name=request.model_name,
            model_provider=request.model_provider,
            llm_parameters=request.llm_parameters,
            use_llm_filter=request.use_llm_filter,
            use_linked_docs=request.use_linked_docs,
            # Granular filtering controls
            input_filtering=request.input_filtering,
            output_filtering=request.output_filtering,
        )
        return result

    except Exception as e:
        logger.error(f"Error processing query: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/query/stream",
    tags=["Query & Generation"],
    summary="Receive a streaming response",
    description="""
Processes the query in streaming mode and sends response chunks as they are generated.
The stream uses the **Server-Sent Events** format (`text/event-stream`).

Error codes:
- **422** — validation errors in the request body.
- **500** — failure when communicating with the external LLM.
""",
    responses={
        200: {
            "description": "Event stream with response chunks.",
            "content": {
                "text/event-stream": {
                    "example": 'data: {"chunk": "Hello,"}\n\n',
                }
            },
        },
        500: {
            "description": "Error generating the response.",
            "content": {"application/json": {"example": {"detail": "External LLM timeout"}}},
        },
    },
)
async def stream_query(
    request: QueryRequest,
    stream_mode: StreamingGuardMode | None = Query(
        None,
        description="Streaming moderation mode: rule-only, llm-only, hybrid, bypass.",
        examples=["hybrid"],
    ),
    api_key: APIKey | None = Depends(optional_auth(Role.USER)),
):
    """
    Processes a query in streaming mode, returning parts of the response as they are generated.

    Args:
        request (QueryRequest): User query

    Returns:
        StreamingResponse: Streaming response with generated text parts
    """
    try:
        # Apply INPUT filtering with granular controls (before streaming starts)
        input_opts = request.input_filtering or FilteringOptions()

        # Backward compatibility for use_llm_filter
        if request.use_llm_filter and request.input_filtering is None:
            logger.warning(
                "use_llm_filter is deprecated for streaming. Use input_filtering.enable_safety_llm instead."
            )
            input_opts.enable_safety_llm = request.use_llm_filter

        # Filter the input query before streaming
        input_filter_result = await get_rag_system().filter_service.filter_input(
            request.query,
            use_llm=input_opts.enable_safety_llm,
            use_linked_docs=request.use_linked_docs,
            enable_vector_rules=input_opts.enable_vector_rules,
            enable_prompt_modification=input_opts.enable_prompt_modification,
        )

        # Use the modified query if filtering modified it
        effective_query = input_filter_result.modified_text or request.query
        logger.info(
            "Streaming query input filtering: modified=%s, matches=%d",
            input_filter_result.was_modified,
            len(input_filter_result.matches) if input_filter_result.matches else 0,
        )

        guard_mode = stream_mode or StreamingGuardMode.from_value(settings.STREAM_GUARD_MODE)
        guard = StreamingGuard(
            content_filter=get_rag_system().content_filter,
            mode=guard_mode,
        )

        base_adapter = get_rag_system().external_llm
        override_requested = any(
            [
                (request.model_name or "").strip(),
                (request.model_provider or "").strip(),
                request.llm_parameters,
            ]
        )

        if override_requested:
            provider_hint_raw = (
                (request.model_provider or "")
                or getattr(base_adapter, "provider", None)
                or getattr(base_adapter, "kind", "external")
            )
            provider_hint = (
                provider_hint_raw.strip().lower()
                if isinstance(provider_hint_raw, str)
                else "external"
            )
            model_override = (request.model_name or "").strip() or None
            selected_adapter = LLMAdapter(
                role=provider_hint or getattr(base_adapter, "kind", "external"),
                provider=provider_hint or None,
                model_name_override=model_override,
                llm_parameters=request.llm_parameters,
            )
            logger.info(
                "Streaming query using custom adapter provider=%s model=%s params=%s",
                provider_hint,
                model_override or getattr(selected_adapter, "model", None),
                request.llm_parameters,
            )
        else:
            selected_adapter = base_adapter

        async def response_generator():
            try:
                # Send input filter result first (before streaming starts)
                input_filter_payload = {
                    "event": "input_filter_result",
                    "filter_result": input_filter_result.model_dump(mode="json"),
                }
                yield f"data: {json.dumps(input_filter_payload)}\n\n"

                async for chunk in selected_adapter.generate_streaming_response(
                    query=effective_query, context=None
                ):
                    decision = await guard.process_chunk(chunk)

                    if decision.allowed and decision.content:
                        yield f"data: {json.dumps(decision.to_payload())}\n\n"

                    if decision.stop_stream:
                        stop_payload = {
                            "event": "guard_blocked",
                            "reason": decision.reason,
                            "mode": guard.mode.value,
                            "metrics": guard.metrics.to_dict(),
                        }
                        if decision.filter_result and decision.filter_result.matches:
                            stop_payload["matches"] = [
                                match.dict() for match in decision.filter_result.matches
                            ]
                        yield f"data: {json.dumps(stop_payload)}\n\n"
                        break
            finally:
                metrics_payload = {
                    "event": "guard_metrics",
                    "mode": guard.mode.value,
                    "metrics": guard.metrics.to_dict(),
                }
                yield f"data: {json.dumps(metrics_payload)}\n\n"

        return StreamingResponse(response_generator(), media_type="text/event-stream")

    except Exception as e:
        logger.error(f"Error in streaming processing: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


# =====================
# Upload & Data Management
# =====================


@router.post(
    "/upload/documents",
    response_model=CSVUploadResponse,
    tags=["Upload & Data Management"],
    summary="Upload new knowledge documents (CSV)",
    description="""
Accepts a CSV file with documents to index in the vector database. Required columns:
- **id** — unique row identifier;
- **text** — document content.

Optional columns: `category`, `source`, `rule_ids` (comma-separated list of rules).

Error codes:
- **400** — file is missing required columns or fails validation;
- **409** — document already exists (reserved for future checks);
- **500** — internal error during processing.
""",
    responses={
        200: {
            "description": "Documents were added to the index successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "processed_documents": 125,
                        "file_name": "docs.csv",
                        "errors": None,
                        "warnings": ["Row 8: rule_ids not provided"],
                        "timestamp": "2024-05-20T11:02:44",
                    }
                }
            },
        },
        400: {
            "description": "CSV validation error.",
            "content": {"application/json": {"example": {"detail": ["Missing columns: ['text']"]}}},
        },
        409: {
            "description": "Conflict: document already exists (future validation).",
            "content": {
                "application/json": {"example": {"detail": "Document doc_1 already exists"}}
            },
        },
        500: {
            "description": "Internal error while uploading.",
            "content": {
                "application/json": {"example": {"detail": "Cannot connect to vector database"}}
            },
        },
    },
)
async def upload_documents_csv(
    file: UploadFile = File(...),
    text_columns: str = Form(
        ...,
        description="Names of columns that contain text (comma-separated, must include `text`).",
        examples=["text"],
    ),
    metadata_columns: str | None = Form(
        None,
        description="Additional metadata columns separated by commas (for example, category,source,rule_ids).",
        examples=["category,source,rule_ids"],
    ),
    batch_size: int = Form(
        1000,
        gt=0,
        description="Batch size when processing the CSV (used for streaming uploads).",
        examples=[500],
    ),
    api_key: APIKey | None = Depends(optional_auth(Role.USER)),
):
    try:
        df = pd.read_csv(file.file)
        errors = get_indexing_service().validate_documents_csv(df)
        if errors:
            raise HTTPException(status_code=400, detail=errors)
        # Process rule_ids
        df["rule_ids"] = df.get("rule_ids", "").apply(
            lambda x: x.split(",") if pd.notnull(x) else []
        )
        # Add documents
        documents = []
        for _, row in df.iterrows():
            doc = {
                "text": row["text"],
                "metadata": {
                    "document_id": row["id"],
                    "category": row.get("category"),
                    "source": row.get("source"),
                    "rule_ids": row["rule_ids"],
                },
            }
            documents.append(doc)
        get_vector_db().add_documents(documents)
        # Create links
        for _, row in df.iterrows():
            for rule_id in row["rule_ids"]:
                try:
                    await get_vector_db().link_rule_to_documents(
                        rule_id=rule_id.strip(),
                        document_ids=[row["id"]],
                        is_approved=True,
                    )
                except Exception as e:
                    logger.error(f"Error creating link {rule_id}->{row['id']}: {e!s}")
        return CSVUploadResponse(
            status="success",
            processed_documents=len(df),
            file_name=file.filename,
            errors=None,
            warnings=None,
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error uploading documents: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/upload/rules",
    response_model=CSVUploadResponse,
    tags=["Upload & Data Management"],
    summary="Upload safety rules (CSV)",
    description="""
Accepts a CSV file with safety rules. Required columns: **id**, **text**, **risk_level**.
Optional columns: `category`, `threshold`, `document_ids` (comma-separated).

Error codes:
- **400** — file does not meet expectations (missing columns or invalid values);
- **409** — rule already exists (reserved for future validation);
- **500** — internal error while persisting data.
""",
    responses={
        200: {
            "description": "Rules added successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "processed_documents": 32,
                        "file_name": "rules.csv",
                        "errors": None,
                        "warnings": None,
                        "timestamp": "2024-05-20T11:15:01",
                    }
                }
            },
        },
        400: {
            "description": "CSV validation error.",
            "content": {
                "application/json": {
                    "example": {"detail": ["Column risk_level must be an integer"]}
                }
            },
        },
        409: {
            "description": "Conflict while creating the rule.",
            "content": {
                "application/json": {"example": {"detail": "Rule rule-toxic-001 already exists"}}
            },
        },
        500: {
            "description": "Internal error while processing the file.",
            "content": {
                "application/json": {"example": {"detail": "Failed to write rules to vector store"}}
            },
        },
    },
)
async def upload_rules_csv(
    file: UploadFile = File(...),
    text_columns: str = Form(
        ...,
        description="Columns that contain rule text (comma-separated, must include `text`).",
        examples=["text"],
    ),
    metadata_columns: str | None = Form(
        None,
        description="Metadata columns such as category,risk_level,threshold,document_ids (comma-separated).",
        examples=["category,risk_level,threshold,document_ids"],
    ),
    batch_size: int = Form(
        1000,
        gt=0,
        description="Batch size when processing the CSV (used for streaming uploads).",
        examples=[500],
    ),
    api_key: APIKey | None = Depends(optional_auth(Role.USER)),
):
    try:
        df = pd.read_csv(file.file)
        errors = get_indexing_service().validate_rules_csv(df)
        if errors:
            raise HTTPException(status_code=400, detail=errors)
        # Process document_ids
        df["document_ids"] = df.get("document_ids", "").apply(
            lambda x: x.split(",") if pd.notnull(x) else []
        )
        # Add rules to vector DB
        rules = []
        for _, row in df.iterrows():
            rule = FilteredContent(
                text=row["text"],
                category=row.get("category", "other"),
                risk_level=row["risk_level"],
                threshold=row.get("threshold", 0.75),
            )
            rules.append(rule)
        get_vector_db().add_filter_rules_batch(rules)
        # Automatic link creation
        if "document_ids" in df.columns:
            for _, row in df.iterrows():
                if row["document_ids"]:
                    await get_vector_db().link_rule_to_documents(
                        rule_id=row["id"],
                        document_ids=row["document_ids"],
                        is_approved=True,
                    )
        return CSVUploadResponse(
            status="success", processed_documents=len(df), file_name=file.filename
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error uploading rules: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/cache/clear",
    tags=["Upload & Data Management"],
    summary="Clear cached responses",
    description="""
Removes stored query results and resets cache counters.

Error codes:
- **500** — cache clearing failed because of an internal error.
""",
    responses={
        200: {
            "description": "Cache cleared successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "message": "Cache successfully cleared",
                    }
                }
            },
        },
        500: {
            "description": "Failed to complete the operation.",
            "content": {"application/json": {"example": {"detail": "Cache backend unavailable"}}},
        },
    },
)
async def clear_cache(api_key: APIKey | None = Depends(optional_auth(Role.USER))):
    """
    Clears the system cache.

    Returns:
        Dict: Result of the cache clearing operation
    """
    try:
        get_rag_system().clear_cache()
        return {"status": "success", "message": "Cache successfully cleared"}

    except Exception as e:
        logger.error(f"Error clearing cache: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/indexing/status",
    response_model=IndexingStatusResponse,
    tags=["Upload & Data Management"],
    summary="Get indexing status",
    description="""
Returns the current status of the indexing operation, including progress, counts, and timing information.

The status can be:
- **idle** — no indexing operation is currently running or has completed
- **in_progress** — indexing is currently running
- **completed** — indexing completed successfully
- **failed** — indexing failed with an error

Error codes:
- **500** — failed to retrieve indexing status
""",
    responses={
        200: {
            "description": "Indexing status retrieved successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "status": {
                            "status": "in_progress",
                            "progress_percentage": 45.5,
                            "indexed_rules": 25,
                            "indexed_documents": 150,
                            "indexed_links": 75,
                            "total_rules": 50,
                            "total_documents": 300,
                            "total_links": 150,
                            "start_time": "2024-05-20T10:00:00",
                            "end_time": None,
                            "duration_seconds": 120.5,
                            "error_message": None,
                            "current_operation": "Indexing documents",
                        },
                        "timestamp": "2024-05-20T10:02:30",
                    }
                }
            },
        },
        500: {
            "description": "Failed to retrieve status.",
            "content": {"application/json": {"example": {"detail": "Internal error"}}},
        },
    },
)
async def get_indexing_status(api_key: APIKey | None = Depends(optional_auth(Role.READONLY))):
    """
    Get the current status of the indexing operation.

    Returns:
        IndexingStatusResponse: Current indexing status with progress information
    """
    try:
        status = await get_indexing_service().get_indexing_status()
        return IndexingStatusResponse(status=status, timestamp=datetime.now())
    except Exception as e:
        logger.error(f"Error getting indexing status: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/indexing/status/stream",
    tags=["Upload & Data Management"],
    summary="Stream indexing status updates (SSE)",
    description="""
Streams real-time updates of the indexing status using Server-Sent Events (SSE).

The stream will send periodic updates while indexing is in progress and automatically
close when indexing completes or fails.

To use this endpoint:
1. Connect to the stream using EventSource API or similar SSE client
2. Listen for `data` events containing JSON status updates
3. The stream will close automatically when indexing finishes

Error codes:
- **500** — failed to stream status updates
""",
    responses={
        200: {
            "description": "Event stream with status updates.",
            "content": {
                "text/event-stream": {
                    "example": 'data: {"status": "in_progress", "progress_percentage": 45.5}\n\n',
                }
            },
        },
        500: {
            "description": "Failed to stream updates.",
            "content": {"application/json": {"example": {"detail": "Internal error"}}},
        },
    },
)
async def stream_indexing_status(api_key: APIKey | None = Depends(optional_auth(Role.READONLY))):
    """
    Stream real-time indexing status updates using Server-Sent Events (SSE).

    This endpoint provides live updates of the indexing progress, automatically
    closing the stream when indexing completes or fails.

    Returns:
        StreamingResponse: SSE stream with status updates
    """
    import asyncio

    async def status_generator():
        """Generate status updates for SSE stream."""
        try:
            previous_status = None
            while True:
                # Get current status
                status = await get_indexing_service().get_indexing_status()
                status_dict = status.model_dump(mode="json")

                # Only send if status changed or we're still in progress
                if status_dict != previous_status:
                    yield f"data: {json.dumps(status_dict)}\n\n"
                    previous_status = status_dict

                # If indexing is complete or failed, close the stream
                if status.status in ["completed", "failed", "idle"]:
                    # Send final status
                    yield f"data: {json.dumps(status_dict)}\n\n"
                    # Send end event
                    yield f"event: end\ndata: {json.dumps({'status': status.status})}\n\n"
                    break

                # Wait before next update
                await asyncio.sleep(0.5)  # Update every 500ms

        except Exception as e:
            logger.error(f"Error in status stream: {e!s}")
            error_msg = {"error": str(e), "status": "error"}
            yield f"data: {json.dumps(error_msg)}\n\n"

    return StreamingResponse(status_generator(), media_type="text/event-stream")


@router.post(
    "/reindex",
    tags=["Upload & Data Management"],
    summary="🔄 Start data reindexing",
    description="""
Launches background reindexing of documents and rules from CSV files.

**Process:**
1. Exports current vector database state to CSV (backup)
2. Reads CSV files from `./data/raw/` directory
3. Rebuilds vector database collections

**Note:** Indexing mode will be automatically enabled if it's currently disabled.

**Requirements:**
- CSV files must exist in `./data/raw/` directory
- Use `/upload/csv` endpoint to upload files first if needed

Error codes:
- **404** — CSV files not found in data directory
- **409** — another indexing operation is already in progress
- **500** — failed to start the reindexing task
""",
    responses={
        200: {
            "description": "Background task started.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "started",
                        "message": "Reindexing started in the background",
                        "indexing_enabled": True
                    }
                }
            },
        },
        404: {
            "description": "CSV files not found.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Rules CSV file not found: ./data/raw/filter_rules.csv. Please upload CSV files first using /api/v1/upload/csv endpoint."
                    }
                }
            },
        },
        409: {
            "description": "Indexing is already in progress.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Reindexing is already in progress. Please wait for it to complete."
                    }
                }
            },
        },
        500: {
            "description": "Failed to initiate reindexing.",
            "content": {
                "application/json": {"example": {"detail": "Failed to schedule reindex job"}}
            },
        },
    },
)
async def reindex_data(
    background_tasks: BackgroundTasks,
    api_key: APIKey | None = Depends(optional_auth(Role.USER)),
):
    """
    Starts data reindexing in the background.
    Automatically enables indexing mode if disabled.
    """
    # Automatically enable indexing mode if disabled
    indexing_was_disabled = False
    if not get_rag_system().get_indexing_mode():
        logger.info("Enabling indexing mode for reindexing")
        get_rag_system().set_indexing_mode(True)
        indexing_was_disabled = True

    # Check if indexing is already in progress
    if get_indexing_service().is_indexing_in_progress():
        raise HTTPException(
            status_code=409,
            detail="Reindexing is already in progress. Please wait for it to complete.",
        )

    try:

        async def perform_reindex():
            await get_indexing_service().reindex_all()

        background_tasks.add_task(perform_reindex)
        return {
            "status": "started",
            "message": "Reindexing started in the background",
            "indexing_enabled": True,
            "indexing_was_auto_enabled": indexing_was_disabled,
        }
    except Exception as e:
        logger.error(f"Error starting reindexing: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/upload/csv",
    tags=["Upload & Data Management"],
    summary="📤 Upload and index CSV files",
    description="""
Upload CSV files directly to the raw data directory and trigger automatic reindexing.

**📋 Required files (all three must be provided):**
- **rules_file** — Safety rules CSV (columns: id, text, risk_level, category?, threshold?)
- **documents_file** — Knowledge documents CSV (columns: id, text, category?, source?)
- **links_file** — Rule-document relationships CSV (columns: rule_id, document_id, is_approved?)

**✨ Features:**
- Validates CSV structure before saving
- Automatically enables indexing mode if disabled
- Triggers background reindexing after upload
- Files are saved to `./data/raw/`

**📝 CSV Format Examples:**

filter_rules.csv:
```csv
id,text,risk_level,category,threshold
rule-001,Offensive language detected,high,toxicity,0.8
```

vector_documents.csv:
```csv
id,text,category,source
doc-001,Company policy guidelines,policy,manual
```

links.csv:
```csv
rule_id,document_id,is_approved
rule-001,doc-001,true
```

**Note:** All three CSV files are required. If you only have rules or documents,
use the individual upload endpoints: `/api/v1/upload/rules` or `/api/v1/upload/documents`.

Error codes:
- **400** — invalid file format or missing required columns
- **409** — indexing is already in progress
- **500** — failed to save or index the files
""",
    responses={
        200: {
            "description": "Files uploaded and indexed successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "message": "CSV files uploaded and indexing started",
                        "uploaded_files": ["filter_rules.csv", "vector_documents.csv"],
                        "saved_to": "./data/raw",
                        "indexing_enabled": True
                    }
                }
            },
        },
        400: {
            "description": "Invalid file format.",
            "content": {
                "application/json": {
                    "example": {"detail": "No CSV files provided"}
                }
            },
        },
        409: {
            "description": "Indexing is already in progress.",
            "content": {
                "application/json": {
                    "example": {"detail": "Reindexing is already in progress"}
                }
            },
        },
        500: {
            "description": "Failed to process files.",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to save CSV files"}
                }
            },
        },
    },
)
async def upload_csv_files(
    background_tasks: BackgroundTasks,
    rules_file: UploadFile = File(..., description="📋 Safety rules CSV file (filter_rules.csv format)"),
    documents_file: UploadFile = File(..., description="📄 Knowledge documents CSV file (vector_documents.csv format)"),
    links_file: UploadFile = File(..., description="🔗 Rule-document links CSV file (links.csv format)"),
    api_key: Optional[APIKey] = Depends(optional_auth(Role.USER)),
):
    """
    Upload CSV files to raw data directory and trigger reindexing.

    All three files must be provided: rules, documents, and links.
    Indexing mode will be automatically enabled if disabled.
    """
    # Automatically enable indexing mode if disabled
    indexing_was_disabled = False
    if not get_rag_system().get_indexing_mode():
        logger.info("Enabling indexing mode for CSV upload")
        get_rag_system().set_indexing_mode(True)
        indexing_was_disabled = True

    # Check if indexing is already in progress
    if get_indexing_service().is_indexing_in_progress():
        raise HTTPException(
            status_code=409,
            detail="Cannot upload CSV files: reindexing is already in progress.",
        )

    try:
        from config.settings import directory_manager, settings

        # Ensure raw data directory exists
        directory_manager.ensure_directory(settings.RAW_DATA_DIR)

        uploaded_files = []

        # Save rules file
        if rules_file:
            if not rules_file.filename.endswith('.csv'):
                raise HTTPException(status_code=400, detail=f"Rules file must be a CSV file, got: {rules_file.filename}")

            # Validate CSV structure
            content = await rules_file.read()
            await rules_file.seek(0)  # Reset file pointer for saving

            try:
                import io
                df = pd.read_csv(io.BytesIO(content))
                errors = get_indexing_service().validate_rules_csv(df)
                if errors:
                    raise HTTPException(status_code=400, detail=f"Rules CSV validation failed: {errors}")
            except pd.errors.EmptyDataError:
                raise HTTPException(status_code=400, detail="Rules CSV file is empty")
            except HTTPException:
                raise  # Re-raise HTTPException as-is
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid rules CSV format: {str(e)}")

            rules_path = settings.RAW_DATA_DIR / "filter_rules.csv"
            with open(rules_path, "wb") as f:
                f.write(content)
            uploaded_files.append("filter_rules.csv")

            # Record CSV upload metrics
            from src.monitoring.metrics import content_filter_metrics
            content_filter_metrics.record_csv_upload("rules", len(content))

            logger.info(f"Saved rules file to {rules_path} ({len(content)} bytes)")

        # Save documents file
        if documents_file:
            if not documents_file.filename.endswith('.csv'):
                raise HTTPException(status_code=400, detail=f"Documents file must be a CSV file, got: {documents_file.filename}")

            # Validate CSV structure
            content = await documents_file.read()
            await documents_file.seek(0)  # Reset file pointer for saving

            try:
                import io
                df = pd.read_csv(io.BytesIO(content))
                errors = get_indexing_service().validate_documents_csv(df)
                if errors:
                    raise HTTPException(status_code=400, detail=f"Documents CSV validation failed: {errors}")
            except pd.errors.EmptyDataError:
                raise HTTPException(status_code=400, detail="Documents CSV file is empty")
            except HTTPException:
                raise  # Re-raise HTTPException as-is
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid documents CSV format: {str(e)}")

            docs_path = settings.RAW_DATA_DIR / "vector_documents.csv"
            with open(docs_path, "wb") as f:
                f.write(content)
            uploaded_files.append("vector_documents.csv")

            # Record CSV upload metrics
            from src.monitoring.metrics import content_filter_metrics
            content_filter_metrics.record_csv_upload("documents", len(content))

            logger.info(f"Saved documents file to {docs_path} ({len(content)} bytes)")

        # Save links file (optional)
        if links_file:
            if not links_file.filename.endswith('.csv'):
                raise HTTPException(status_code=400, detail=f"Links file must be a CSV file, got: {links_file.filename}")

            # Validate CSV structure
            content = await links_file.read()
            await links_file.seek(0)  # Reset file pointer for saving

            try:
                import io
                df = pd.read_csv(io.BytesIO(content))
                errors = get_indexing_service().validate_links_csv(df)
                if errors:
                    raise HTTPException(status_code=400, detail=f"Links CSV validation failed: {errors}")
            except pd.errors.EmptyDataError:
                raise HTTPException(status_code=400, detail="Links CSV file is empty")
            except HTTPException:
                raise  # Re-raise HTTPException as-is
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid links CSV format: {str(e)}")

            links_path = settings.RAW_DATA_DIR / "links.csv"
            with open(links_path, "wb") as f:
                f.write(content)
            uploaded_files.append("links.csv")

            # Record CSV upload metrics
            from src.monitoring.metrics import content_filter_metrics
            content_filter_metrics.record_csv_upload("links", len(content))

            logger.info(f"Saved links file to {links_path} ({len(content)} bytes)")

        # Trigger reindexing in the background
        # Skip export since we just uploaded fresh CSV files
        async def perform_reindex():
            await get_indexing_service().reindex_all(skip_export=True)

        background_tasks.add_task(perform_reindex)

        return {
            "status": "success",
            "message": "CSV files uploaded and indexing started in the background",
            "uploaded_files": uploaded_files,
            "saved_to": str(settings.RAW_DATA_DIR),
            "indexing_enabled": True,
            "indexing_was_auto_enabled": indexing_was_disabled,
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error uploading CSV files: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/export/csv",
    tags=["Upload & Data Management"],
    summary="📥 Export current data to CSV files",
    description="""
Export the current vector database data to CSV files in the raw data directory.

**Creates backup files:**
- **filter_rules.csv** — all current safety rules
- **vector_documents.csv** — all current knowledge documents
- **links.csv** — all current rule-document relationships

**Use cases:**
- Create backup before making changes
- Export data for manual editing
- Prepare data for version control

**Note:** Indexing mode will be automatically enabled if it's currently disabled.

The files are saved to `./data/raw/` and can be edited manually or re-uploaded.

Error codes:
- **500** — failed to export data
""",
    responses={
        200: {
            "description": "Data exported successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "exported_rules": 42,
                        "exported_documents": 125,
                        "exported_links": 87,
                        "output_directory": "./data/raw",
                        "indexing_enabled": True
                    }
                }
            },
        },
        500: {
            "description": "Failed to export data.",
            "content": {
                "application/json": {
                    "example": {"detail": "Error during export"}
                }
            },
        },
    },
)
async def export_to_csv(
    api_key: APIKey | None = Depends(optional_auth(Role.USER)),
):
    """
    Export current vector database data to CSV files.
    Automatically enables indexing mode if disabled.
    """
    # Automatically enable indexing mode if disabled
    if not get_rag_system().get_indexing_mode():
        logger.info("Enabling indexing mode for CSV export")
        get_rag_system().set_indexing_mode(True)

    try:
        result = await get_indexing_service().export_to_csv()
        return result
    except Exception as e:
        logger.error(f"Error exporting data: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/rules/{rule_id}/documents/{document_id}",
    response_model=RuleDocument,
    tags=["Rules & Documents Management"],
    summary="Link a document to a rule",
    description="Creates an association between a rule and a document. Returns 409 if indexing is disabled.",
    responses={
        200: {
            "description": "Link created successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "rule_id": "rule-toxic-001",
                        "document_id": "doc_42",
                        "is_approved": True,
                        "relevance_score": 0.91,
                    }
                }
            },
        },
        404: {
            "description": "Rule or document not found.",
            "content": {"application/json": {"example": {"detail": "Document not found"}}},
        },
        409: {
            "description": "Linking unavailable because indexing is disabled.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Reindexing is unavailable: document indexing is disabled."
                    }
                }
            },
        },
        500: {
            "description": "Internal error while creating the link.",
            "content": {"application/json": {"example": {"detail": "Failed to create link"}}},
        },
    },
)
async def create_manual_link(
    rule_id: str,
    document_id: str,
    is_approved: bool = Query(True),
    api_key: APIKey | None = Depends(optional_auth(Role.USER)),
) -> RuleDocument:
    if not get_rag_system().get_indexing_mode():
        raise HTTPException(
            status_code=409,
            detail="Manual linking is unavailable: document indexing is disabled.",
        )
    try:
        # Use LinksManager to create the link
        link = await get_rag_system().links_manager.create_link(rule_id, document_id, is_approved)
        get_rag_system().cache.clear()  # Clear cache after modifying links
        return link[0] if isinstance(link, list) else link
    except Exception as e:
        logger.error(f"Error creating link: {e!s}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/rules/{rule_id}/documents",
    response_model=list[RuleDocument],
    description="Batch link documents to a rule. Creates multiple links between a single rule and multiple documents.",
    tags=["Rules & Documents Management"],
    summary="Batch link documents to a rule",
    responses={
        200: {"description": "Links created successfully"},
        400: {"description": "Invalid request (empty document list, duplicate rule_id in request)"},
        404: {"description": "Rule or document not found"},
        409: {"description": "Indexing is disabled"},
        500: {"description": "Internal error"},
    },
)
async def link_documents_to_rule(
    rule_id: str,
    request: RuleLinkRequest,
    background_tasks: BackgroundTasks,
    api_key: APIKey | None = Depends(optional_auth(Role.USER)),
):
    """
    Batch link multiple documents to a single rule.

    This endpoint allows linking multiple documents to a rule in a single request,
    which is more efficient than making multiple individual link requests.

    Args:
        rule_id: The ID of the rule to link documents to (from path)
        request: RuleLinkRequest containing document_ids and is_approved flag
        background_tasks: FastAPI background tasks for async operations

    Returns:
        list[RuleDocument]: List of created link objects

    Raises:
        HTTPException 400: If document_ids list is empty or rule_id mismatch
        HTTPException 404: If rule or any document is not found
        HTTPException 409: If indexing is disabled
        HTTPException 500: If internal error occurs

    Example:
        POST /rules/rule-123/documents
        {
            "rule_id": "rule-123",
            "document_ids": ["doc-1", "doc-2", "doc-3"],
            "is_approved": true
        }
    """
    # Check if indexing is enabled
    if not get_rag_system().get_indexing_mode():
        raise HTTPException(
            status_code=409,
            detail="Batch linking is unavailable: document indexing is disabled.",
        )

    # Validate request
    if not request.document_ids or len(request.document_ids) == 0:
        raise HTTPException(
            status_code=400,
            detail="document_ids list cannot be empty. Provide at least one document ID.",
        )

    # Validate that rule_id in request matches path parameter
    if request.rule_id != rule_id:
        raise HTTPException(
            status_code=400,
            detail=f"rule_id mismatch: path parameter '{rule_id}' does not match request body '{request.rule_id}'",
        )

    # Check for duplicate document IDs
    if len(request.document_ids) != len(set(request.document_ids)):
        raise HTTPException(
            status_code=400,
            detail="Duplicate document IDs detected in request. Each document ID should appear only once.",
        )

    try:
        # Verify rule exists
        rule = await get_vector_db().get_rule(rule_id)
        if not rule:
            raise HTTPException(
                status_code=404,
                detail=f"Rule '{rule_id}' not found. Cannot create links to non-existent rule.",
            )

        # Verify all documents exist
        all_documents = await get_vector_db().get_all_documents()
        existing_doc_ids = {doc.get("document_id") or doc.get("id") for doc in all_documents}

        missing_docs = [doc_id for doc_id in request.document_ids if doc_id not in existing_doc_ids]
        if missing_docs:
            raise HTTPException(
                status_code=404,
                detail=f"Documents not found: {', '.join(missing_docs)}. All documents must exist before linking.",
            )

        # Create batch links using LinksManager
        links = await get_rag_system().links_manager.batch_create_links(
            rule_id=rule_id,
            document_ids=request.document_ids,
            is_approved=request.is_approved,
        )

        # Clear cache after modifying links
        get_rag_system().cache.clear()

        logger.info(
            f"Batch link created: rule '{rule_id}' -> {len(request.document_ids)} documents "
            f"(approved: {request.is_approved})"
        )

        return links

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error creating batch links for rule '{rule_id}': {e!s}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while creating batch links: {e!s}",
        )


@router.delete(
    "/rules/{rule_id}/documents/{document_id}",
    response_model=dict[str, bool],
    tags=["Rules & Documents Management"],
    summary="Remove a link between a rule and a document",
    description="Deletes an existing link. Returns 409 if indexing is disabled.",
    responses={
        200: {
            "description": "Link removed.",
            "content": {"application/json": {"example": {"success": True}}},
        },
        404: {
            "description": "Link not found.",
            "content": {"application/json": {"example": {"detail": "Link not found"}}},
        },
        409: {
            "description": "Removal unavailable while indexing is disabled.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Removing links is unavailable: document indexing is disabled."
                    }
                }
            },
        },
        500: {
            "description": "Error removing the link.",
            "content": {"application/json": {"example": {"detail": "Failed to remove link"}}},
        },
    },
)
async def remove_document_link(
    rule_id: str,
    document_id: str,
    api_key: APIKey | None = Depends(optional_auth(Role.USER)),
):
    if not get_rag_system().get_indexing_mode():
        raise HTTPException(
            status_code=409,
            detail="Removing links is unavailable: document indexing is disabled.",
        )
    try:
        # Use LinksManager to delete the link
        success = await get_rag_system().links_manager.delete_link(rule_id, document_id)
        get_rag_system().cache.clear()
        return {"success": success}
    except Exception as e:
        logger.error(f"Error removing link: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch(
    "/rules/{rule_id}/documents/{document_id}/approve",
    response_model=RuleDocument,
    tags=["Rules & Documents Management"],
    summary="Approve a link between a rule and a document",
    description="Approves an automatically created link. Returns 409 if indexing is disabled.",
    responses={
        200: {
            "description": "Link approved.",
            "content": {
                "application/json": {
                    "example": {
                        "rule_id": "rule-toxic-001",
                        "document_id": "doc_42",
                        "is_approved": True,
                        "relevance_score": 0.91,
                    }
                }
            },
        },
        404: {
            "description": "Link not found.",
            "content": {"application/json": {"example": {"detail": "Link not found"}}},
        },
        409: {
            "description": "Operation unavailable while indexing is disabled.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Reindexing is unavailable: document indexing is disabled."
                    }
                }
            },
        },
        500: {
            "description": "Internal error when approving the link.",
            "content": {"application/json": {"example": {"detail": "Failed to approve link"}}},
        },
    },
)
async def approve_document_link(
    rule_id: str,
    document_id: str,
    background_tasks: BackgroundTasks,
    api_key: APIKey | None = Depends(optional_auth(Role.USER)),
):
    # Check if indexing is enabled
    if not get_rag_system().get_indexing_mode():
        raise HTTPException(
            status_code=409,
            detail="Approving links is unavailable: document indexing is disabled.",
        )

    try:
        # Use LinksManager to approve the link
        updated_link = await get_rag_system().links_manager.approve_link(rule_id, document_id, True)

        if updated_link is None:
            raise HTTPException(
                status_code=404,
                detail=f"Link between rule '{rule_id}' and document '{document_id}' not found",
            )

        # Clear cache after approval
        get_rag_system().cache.clear()

        return updated_link
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving link: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/rules",
    response_model=list[dict],
    tags=["Rules & Documents Management"],
    summary="Get the list of all rules",
    description="Returns the complete set of filtering rules with metadata.",
    responses={
        200: {
            "description": "Array of rules with details.",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": "rule-toxic-001",
                            "text": "Toxic statements are not allowed",
                            "category": "toxicity",
                            "risk_level": 5,
                        }
                    ]
                }
            },
        },
        500: {
            "description": "Failed to retrieve the list of rules.",
            "content": {"application/json": {"example": {"detail": "Vector DB query failed"}}},
        },
    },
)
async def get_all_rules(api_key: APIKey | None = Depends(optional_auth(Role.READONLY))):
    """Get all filtering rules"""
    try:
        rules = await get_vector_db().get_all_rules()
        return rules
    except Exception as e:
        logger.error(f"Error getting rules: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/rules/{rule_id}",
    response_model=dict,
    tags=["Rules & Documents Management"],
    summary="Get a rule by identifier",
    description="Returns a filtering rule together with metadata.",
    responses={
        200: {
            "description": "Rule found.",
            "content": {
                "application/json": {
                    "example": {
                        "id": "rule-toxic-001",
                        "text": "Toxic statements are not allowed",
                        "risk_level": 5,
                        "category": "toxicity",
                    }
                }
            },
        },
        404: {
            "description": "Rule not found.",
            "content": {"application/json": {"example": {"detail": "Rule not found"}}},
        },
        500: {
            "description": "Error while reading the rule.",
            "content": {"application/json": {"example": {"detail": "Vector DB not reachable"}}},
        },
    },
)
async def get_rule_by_id(
    rule_id: str,
    api_key: APIKey | None = Depends(optional_auth(Role.READONLY)),
):
    """Get a specific rule by ID"""
    try:
        rule = await get_vector_db().get_rule(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
        return rule
    except Exception as e:
        logger.error(f"Error getting rule by ID: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


# =====================
# Links & Debug
# =====================


@router.get(
    "/debug/links",
    response_model=list[dict],
    description="Get all links (for debugging)",
    tags=["Links & Debug"],
    include_in_schema=False,
)
async def get_all_links(api_key: APIKey | None = Depends(optional_auth(Role.READONLY))):
    """Debug endpoint to get all links"""
    try:
        links = await get_vector_db().get_all_links()
        return links

    except Exception as e:
        logger.error(f"Error getting all links: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/documents/{document_id}/rules",
    response_model=list[dict],
    description="Get rules linked to a document",
    tags=["Links & Debug"],
    include_in_schema=False,
)
async def get_linked_rules(
    document_id: str,
    only_approved: bool = Query(True, description="Show only approved links"),
    api_key: APIKey | None = Depends(optional_auth(Role.READONLY)),
):
    """Get the list of rules linked to a document"""
    try:
        rules = await get_rag_system().vector_db.get_rules_for_document(
            document_id=document_id, only_approved=only_approved
        )
        return rules

    except Exception as e:
        logger.error(f"Error getting linked rules: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


# =====================
# LLM & System Management
# =====================


# Health endpoint - always public for monitoring/healthchecks (no auth required)
@router.get(
    "/health",
    tags=["Health"],
    summary="Check system health",
    description="Returns the status of all system components. Public endpoint for monitoring and Docker healthchecks.",
    responses={
        200: {
            "description": "Components are healthy or partially available.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "components": {
                            "external_llm": "healthy",
                            "safety_llm": "not_configured",
                            "vector_db": "healthy",
                        },
                        "requested_safety_mode": "disabled",
                        "active_safety_mode": "disabled",
                        "timestamp": "2024-05-20T11:20:00",
                    }
                }
            },
        },
        500: {
            "description": "Failed to fetch component statuses.",
            "content": {"application/json": {"example": {"detail": "Safety LLM connection error"}}},
        },
    },
)
async def check_system_health():
    """Check the health of the entire system (public endpoint, no auth required)"""
    try:
        external_llm_status = await get_rag_system().check_llm_connection()
        safety_service = get_rag_system().content_filter.safety_llm
        requested_mode = get_rag_system().content_filter.requested_mode.value
        active_mode = get_rag_system().content_filter.active_mode.value
        if safety_service:
            safety_llm_status = await safety_service.check_connection()
            safety_health = "healthy" if safety_llm_status else "unhealthy"
        else:
            safety_health = "not_configured"

        components_status = {
            "external_llm": "healthy" if external_llm_status else "unhealthy",
            "safety_llm": safety_health,
            "vector_db": "healthy",
        }

        system_healthy = all(status == "healthy" for status in components_status.values())

        return {
            "status": "healthy" if system_healthy else "degraded",
            "components": components_status,
            "requested_safety_mode": requested_mode,
            "active_safety_mode": active_mode,
            "timestamp": datetime.now(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class UpdateAPIBaseRequest(BaseModel):
    """Model for the request to update the base URL of the API."""

    base_url: HttpUrl | None = None
    api_type: str = Field("openai", pattern="^(openai|azure|custom)$")
    api_version: str | None = None


@router.get(
    "/stats",
    tags=["LLM & System Management"],
    summary="Get system statistics",
    description="Provides metrics for the vector database, cache, and filters.",
    responses={
        200: {
            "description": "Summary metrics for the components.",
            "content": {
                "application/json": {
                    "example": {
                        "vector_db": {"total_documents": 150, "total_rules": 25},
                        "cache": {
                            "size": 512,
                            "hits": 340,
                            "misses": 120,
                            "hit_rate": 73.9,
                        },
                        "filter": {"threshold": 0.8, "status": "active"},
                        "system_status": "healthy",
                    }
                }
            },
        },
        500: {
            "description": "Failed to collect statistics.",
            "content": {"application/json": {"example": {"detail": "Vector DB stats unavailable"}}},
        },
    },
)
async def get_system_stats(api_key: APIKey | None = Depends(optional_auth(Role.READONLY))):
    """
    Get overall system statistics.

    Returns:
        Dict: System statistics, including information about vector DB,
            cache, and content filter.
    """
    try:
        return await get_rag_system().get_system_stats()
    except Exception as e:
        logger.error(f"Error getting statistics: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/llm/external/status",
    tags=["LLM & System Management"],
    summary="Check the connection to the primary LLM",
    description="Returns the connection status and the name of the model in use.",
    responses={
        200: {
            "description": "Connection status retrieved.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "connected",
                        "model": "gpt-4o-mini",
                        "timestamp": "2024-05-20T11:25:00",
                    }
                }
            },
        },
        500: {
            "description": "Failed to verify the LLM status.",
            "content": {"application/json": {"example": {"detail": "External LLM auth error"}}},
        },
    },
)
async def check_external_llm_status(api_key: APIKey | None = Depends(optional_auth(Role.READONLY))):
    """Check the status of the external LLM"""
    try:
        is_connected = await get_rag_system().external_llm.check_connection()
        return {
            "status": "connected" if is_connected else "disconnected",
            "model": settings.MAIN_LLM_MODEL,
            "timestamp": datetime.now(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Endpoints for Safety LLM management
@router.get(
    "/llm/safety/status",
    tags=["LLM & System Management"],
    summary="Check the status of the Safety LLM",
    description="Reports whether the auxiliary filtering model is available. Consider using GET /settings/safety instead.",
    responses={
        200: {
            "description": "Safety status retrieved.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "not_configured",
                        "model": "gpt-4o-mini-guard",
                        "mode": "disabled",
                        "active_mode": "disabled",
                        "timestamp": "2024-05-20T11:25:30",
                    }
                }
            },
        },
        500: {
            "description": "Failed to contact the Safety LLM.",
            "content": {"application/json": {"example": {"detail": "Safety LLM ping failed"}}},
        },
    },
)
async def check_safety_llm_status(api_key: APIKey | None = Depends(optional_auth(Role.READONLY))):
    """Check the status of the Safety LLM. Consider using GET /settings/safety instead."""
    try:
        safety_service = get_rag_system().content_filter.safety_llm
        requested_mode = get_rag_system().content_filter.requested_mode.value
        active_mode = get_rag_system().content_filter.active_mode.value
        if not safety_service:
            return {
                "status": "not_configured",
                "model": settings.SAFETY_LLM_MODEL,
                "mode": requested_mode,
                "active_mode": active_mode,
                "timestamp": datetime.now(),
            }

        is_connected = await safety_service.check_connection()
        return {
            "status": "connected" if is_connected else "disconnected",
            "model": settings.SAFETY_LLM_MODEL,
            "mode": requested_mode,
            "active_mode": active_mode,
            "timestamp": datetime.now(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =====================
# Prompt Template Management
# =====================


@router.get(
    "/prompt/template",
    response_model=PromptTemplateResponse,
    tags=["Prompt Template Management"],
    summary="Get current prompt modification template",
    description="""
Retrieves the current template used for modifying prompts when filter rules match.

The template must contain two required variables:
- `{text}` - the user's query text
- `{context}` - the RAG context from retrieved documents

This endpoint does NOT modify existing filter behavior - it only allows you to customize
the template used for prompt modification.
""",
)
async def get_prompt_template(api_key: APIKey | None = Depends(optional_auth(Role.READONLY))):
    """Get the current prompt modification template."""
    return PromptTemplateResponse(
        template=settings.PROMPT_MODIFICATION_TEMPLATE,
        required_variables=["text", "context"],
    )


@router.patch(
    "/prompt/template",
    response_model=PromptTemplateResponse,
    tags=["Prompt Template Management"],
    summary="Update prompt modification template",
    description="""
Updates the template used for modifying prompts when filter rules match.

**Requirements:**
- Template MUST contain `{text}` variable (user query)
- Template MUST contain `{context}` variable (RAG context)

**Example template:**
```
"Instruction: {text}\\nContext: {context}"
```

**Validation:**
- Returns 400 if required variables are missing
- Returns 422 if template format is invalid

This change affects future prompt modifications but does NOT modify existing filter behavior.
""",
    responses={
        200: {
            "description": "Template updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "template": "New instruction: {text}\\nContext: {context}",
                        "required_variables": ["text", "context"],
                    }
                }
            },
        },
        400: {
            "description": "Template missing required variables",
            "content": {
                "application/json": {
                    "example": {"detail": "Template must contain {text} variable"}
                }
            },
        },
    },
)
async def update_prompt_template(
    request: PromptTemplateUpdateRequest,
    api_key: APIKey | None = Depends(optional_auth(Role.ADMIN)),
):
    """Update the prompt modification template."""
    try:
        settings.update_prompt_template(request.template)
        logger.info("Prompt template updated via API")
        return PromptTemplateResponse(
            template=settings.PROMPT_MODIFICATION_TEMPLATE,
            required_variables=["text", "context"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/prompt/preview",
    response_model=PromptPreviewResponse,
    tags=["Prompt Template Management"],
    summary="Preview how prompt will look with actual query",
    description="""
Shows how the final prompt will look when the template is applied with a real query.

This endpoint:
1. Retrieves RAG context for the query (if use_rag=true)
2. Applies the current template with the query and context
3. Returns the final prompt text WITHOUT calling the LLM

Use this to test how your template will work before sending actual queries.

**Note:** This does NOT trigger actual filtering or LLM calls - it's just a preview.
""",
    responses={
        200: {
            "description": "Prompt preview generated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "original_query": "How do I implement auth?",
                        "final_prompt": "Remember to adhere to safety guidelines. USER QUESTION: How do I implement auth?\\nCONTEXT: Use OAuth 2.0...\\n",
                        "context_used": "Source: auth_docs\\nUse OAuth 2.0...",
                        "template_used": "Remember to adhere to safety guidelines. USER QUESTION: {text}\\nCONTEXT: {context}\\n",
                        "processing_time": 0.15,
                    }
                }
            },
        },
    },
)
async def preview_prompt(
    request: PromptPreviewRequest,
    api_key: APIKey | None = Depends(optional_auth(Role.USER)),
):
    """
    Preview how the prompt will look with the current template and actual query.

    This endpoint retrieves RAG context and applies the template without calling the LLM.
    """
    import time

    start_time = time.time()

    try:
        rag_system = get_rag_system()
        context_string = None
        context_docs = None

        # Retrieve RAG context if requested
        if request.use_rag:
            from src.services.filter_service import FilterService

            filter_service = FilterService(get_vector_db())

            # Get context (similar to process_query logic)
            input_filter_result = await filter_service.filter_input(
                request.query,
                use_llm=False,  # Don't use LLM, just get context
                use_linked_docs=request.use_linked_docs,
                enable_vector_rules=True,
                enable_prompt_modification=False,  # Don't modify yet
            )

            # Try linked documents first if rules matched
            if request.use_linked_docs and input_filter_result.matches:
                context_docs = await rag_system._get_context_from_matches(input_filter_result.matches)

            # Fall back to vector search if no linked docs
            if not context_docs:
                from src.services.rag_service import RAGService

                rag_service = RAGService(llm_adapter=rag_system.llm_adapter)
                context_docs = await rag_service.retrieve_context(
                    request.query, top_k=settings.RAG_CANDIDATE_COUNT
                )

            # Build context string
            if context_docs:
                context_string = "\n\n".join(
                    [
                        f"Source: {doc.get('metadata', {}).get('source', 'N/A')}\n{doc.get('text', '')}"
                        for doc in context_docs
                    ]
                )

        # Apply template
        final_prompt = settings.PROMPT_MODIFICATION_TEMPLATE.format(
            text=request.query,
            context=context_string or ""
        )

        processing_time = time.time() - start_time

        return PromptPreviewResponse(
            original_query=request.query,
            final_prompt=final_prompt,
            context_used=context_string,
            context_documents=context_docs,
            template_used=settings.PROMPT_MODIFICATION_TEMPLATE,
            processing_time=processing_time,
        )

    except Exception as e:
        logger.error(f"Error generating prompt preview: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Include Settings Routes ==========
# All settings and configuration endpoints are now in settings_routes.py
router.include_router(auth_routes.router, tags=["Authentication"])
router.include_router(settings_routes.router, tags=["System Configuration"])
router.include_router(chat_routes.router, tags=["Chat"])
router.include_router(safety_routes.router, tags=["Safety"])
router.include_router(filter_config_routes.router, tags=["Filter Configuration"])
router.include_router(experiments_routes.router, tags=["Experiments"])
router.include_router(integrations_routes.router, tags=["Integrations"])


# Module-level __getattr__ for lazy initialization compatibility
def __getattr__(name: str):
    """
    Module-level attribute access for lazy initialization.

    This allows backward compatibility for code that imports these variables directly:
        from src.api.routes import rag_system, vector_db, indexing_service
    """
    if name == "rag_system":
        return get_rag_system()
    elif name == "vector_db":
        return get_vector_db()
    elif name == "indexing_service":
        return get_indexing_service()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
