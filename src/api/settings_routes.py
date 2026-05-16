"""
Settings and configuration management endpoints.

Provides runtime configuration management for all AVI system components.
"""

from dataclasses import asdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from src.api.auth import APIKey, Role, optional_auth

from config.settings import settings
from src.models.schemas import (
    CacheConfigResponse,
    CacheConfigUpdate,
    ConfigUpdateResponse,
    FilteringConfigResponse,
    FilteringConfigUpdate,
    FilteringOptions,
    IndexingConfigResponse,
    IndexingConfigUpdate,
    LLMConfigResponse,
    LLMConfigUpdate,
    MonitoringConfigResponse,
    MonitoringConfigUpdate,
    RAGConfigResponse,
    RAGConfigUpdate,
    RateLimitConfigResponse,
    RateLimitConfigUpdate,
    SafetyConfigResponse,
    SafetyConfigUpdate,
    SystemSettingsResponse,
)
from src.services.config_manager import (
    CacheConfig,
    FilteringConfig,
    IndexingConfig,
    LLMConfig,
    MonitoringConfig,
    RAGConfig,
    RateLimitConfig,
    SafetyConfig,
    get_config_manager,
)
from src.utils.logger import logger


router = APIRouter(
    prefix="/settings",  # Settings routes under /api/v1/settings
)


# ========== Unified Settings Endpoint ==========


@router.get(
    "/",
    response_model=SystemSettingsResponse,
    tags=["System Configuration"],
    summary="Get all system settings",
    description="Returns complete system configuration including LLM, RAG, cache, safety, rate limiting, monitoring, and indexing settings.",
    responses={
        200: {
            "description": "System settings retrieved successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "llm": {
                            "main": {"model": "openai/gpt-4o-mini", "temperature": 0.7},
                            "safety": None,
                            "scoring": None,
                        },
                        "rag": {"threshold": 0.75, "rerank_enabled": True},
                        "cache": {"backend": "memory", "ttl": 3600},
                        "safety": {"mode": "disabled", "stream_guard_mode": "hybrid"},
                        "rate_limit": {"enabled": True, "query_limit": "30/minute"},
                        "monitoring": {"prometheus_enabled": True, "otel_enabled": False},
                        "indexing": {"enabled": True, "batch_size": 100},
                        "timestamp": "2025-11-11T12:00:00",
                    }
                }
            },
        },
        500: {
            "description": "Failed to retrieve system settings.",
            "content": {"application/json": {"example": {"detail": "Internal server error"}}},
        },
    },
)
async def get_all_settings(api_key: APIKey | None = Depends(optional_auth(Role.READONLY))):
    """Get complete system configuration."""
    try:
        config_manager = get_config_manager()

        # Get all configs
        llm_configs = config_manager.get_all_llm_configs()
        rag_config = config_manager.get_rag_config()
        cache_config = config_manager.get_cache_config()
        safety_config = config_manager.get_safety_config()
        rate_limit_config = config_manager.get_rate_limit_config()
        monitoring_config = config_manager.get_monitoring_config()
        indexing_config = config_manager.get_indexing_config()
        filtering_config = config_manager.get_filtering_config()

        # Import here to avoid circular dependency
        from src.api.routes import rag_system

        # Get active safety mode from ContentFilterService
        active_safety_mode = (
            rag_system.content_filter.active_mode.value
            if hasattr(rag_system, "content_filter") and rag_system.content_filter
            else safety_config.mode
        )

        return SystemSettingsResponse(
            llm=LLMConfigResponse(**llm_configs),
            rag=RAGConfigResponse(**asdict(rag_config)),
            cache=CacheConfigResponse(**cache_config.to_dict(include_password=False)),
            safety=SafetyConfigResponse(
                mode=safety_config.mode,
                active_mode=active_safety_mode,
                stream_guard_mode=safety_config.stream_guard_mode,
            ),
            rate_limit=RateLimitConfigResponse(**asdict(rate_limit_config)),
            monitoring=MonitoringConfigResponse(**asdict(monitoring_config)),
            indexing=IndexingConfigResponse(**asdict(indexing_config)),
            filtering=FilteringConfigResponse(
                default_input_filtering=FilteringOptions(
                    **filtering_config.default_input_filtering
                ),
                default_output_filtering=FilteringOptions(
                    **filtering_config.default_output_filtering
                ),
            ),
            timestamp=datetime.now(),
        )
    except Exception as e:
        logger.error(f"Failed to retrieve system settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== LLM Configuration Endpoints ==========


@router.get(
    "/settings/llm",
    response_model=LLMConfigResponse,
    tags=["System Configuration"],
    summary="Get LLM configurations",
    description="Returns all LLM configurations (main, safety, scoring).",
)
async def get_llm_settings(api_key: APIKey | None = Depends(optional_auth(Role.READONLY))):
    """Get all LLM configurations."""
    try:
        config_manager = get_config_manager()
        llm_configs = config_manager.get_all_llm_configs()
        return LLMConfigResponse(**llm_configs)
    except Exception as e:
        logger.error(f"Failed to get LLM settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/settings/llm/{role}",
    response_model=ConfigUpdateResponse,
    tags=["System Configuration"],
    summary="Update LLM configuration",
    description="Update configuration for main, safety, or scoring LLM. API keys cannot be changed via this endpoint for security reasons.",
    responses={
        200: {"description": "LLM configuration updated successfully."},
        400: {"description": "Invalid configuration provided."},
        404: {"description": "LLM role not configured."},
        500: {"description": "Failed to update LLM configuration."},
    },
)
async def update_llm_settings(
    role: str, config_update: LLMConfigUpdate, api_key: APIKey | None = Depends(optional_auth(Role.USER))
):
    """Update LLM configuration for a specific role."""
    if role not in ["main", "safety", "scoring"]:
        raise HTTPException(
            status_code=400, detail=f"Invalid role: {role}. Must be 'main', 'safety', or 'scoring'."
        )

    try:
        config_manager = get_config_manager()
        current_config = config_manager.get_llm_config(role)  # type: ignore[arg-type]

        if not current_config:
            raise HTTPException(
                status_code=404,
                detail=f"LLM role '{role}' not configured. Set {role.upper()}_LLM_* environment variables first.",
            )

        # Merge updates (preserve API key and base for security)
        updated_config = LLMConfig(
            model=config_update.model or current_config.model,
            api_key=current_config.api_key,  # Don't allow API key changes via API
            api_base=current_config.api_base,  # Keep base URL from env
            temperature=(
                config_update.temperature
                if config_update.temperature is not None
                else current_config.temperature
            ),
            max_tokens=config_update.max_tokens or current_config.max_tokens,
            top_p=(
                config_update.top_p if config_update.top_p is not None else current_config.top_p
            ),
            timeout=config_update.timeout or current_config.timeout,
            system_prompt=(
                config_update.system_prompt
                if config_update.system_prompt is not None
                else current_config.system_prompt
            ),
        )

        # Update configuration
        config_manager.update_llm_config(role, updated_config)  # type: ignore[arg-type]

        logger.info(f"LLM config updated for role '{role}': model={updated_config.model}")

        return ConfigUpdateResponse(
            status="updated",
            category=f"llm.{role}",
            config=updated_config.to_dict(include_api_key=False),
            timestamp=datetime.now(),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update LLM config for role '{role}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== RAG Configuration Endpoints ==========


@router.get(
    "/settings/rag",
    response_model=RAGConfigResponse,
    tags=["System Configuration"],
    summary="Get RAG settings",
    description="Returns RAG (Retrieval-Augmented Generation) configuration including threshold and reranking settings.",
)
async def get_rag_settings(api_key: APIKey | None = Depends(optional_auth(Role.READONLY))):
    """Get RAG configuration."""
    try:
        config_manager = get_config_manager()
        rag_config = config_manager.get_rag_config()
        return RAGConfigResponse(**asdict(rag_config))
    except Exception as e:
        logger.error(f"Failed to get RAG settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/settings/rag",
    response_model=ConfigUpdateResponse,
    tags=["System Configuration"],
    summary="Update RAG settings",
    description="Update RAG configuration including threshold and reranking parameters. Changes take effect immediately.",
)
async def update_rag_settings(
    config_update: RAGConfigUpdate, api_key: APIKey | None = Depends(optional_auth(Role.USER))
):
    """Update RAG configuration."""
    try:
        config_manager = get_config_manager()
        current_config = config_manager.get_rag_config()

        # Merge updates
        updated_config = RAGConfig(
            threshold=(
                config_update.threshold
                if config_update.threshold is not None
                else current_config.threshold
            ),
            rerank_enabled=(
                config_update.rerank_enabled
                if config_update.rerank_enabled is not None
                else current_config.rerank_enabled
            ),
            rerank_candidate_count=(
                config_update.rerank_candidate_count or current_config.rerank_candidate_count
            ),
            rerank_model_name=config_update.rerank_model_name or current_config.rerank_model_name,
            rerank_score_threshold=(
                config_update.rerank_score_threshold
                if config_update.rerank_score_threshold is not None
                else current_config.rerank_score_threshold
            ),
            rerank_max_length=config_update.rerank_max_length or current_config.rerank_max_length,
        )

        # Update configuration
        config_manager.update_rag_config(updated_config)

        # Apply to settings for immediate effect
        settings.RAG_THRESHOLD = updated_config.threshold
        settings.RERANK_ENABLED = updated_config.rerank_enabled
        settings.RERANK_CANDIDATE_COUNT = updated_config.rerank_candidate_count
        settings.RERANK_MODEL_NAME = updated_config.rerank_model_name
        settings.RERANK_SCORE_THRESHOLD = updated_config.rerank_score_threshold
        settings.RERANK_MAX_LENGTH = updated_config.rerank_max_length

        logger.info(
            f"RAG config updated: threshold={updated_config.threshold}, rerank={updated_config.rerank_enabled}"
        )

        return ConfigUpdateResponse(
            status="updated",
            category="rag",
            config=asdict(updated_config),
            timestamp=datetime.now(),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update RAG config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Cache Configuration Endpoints ==========


@router.get(
    "/settings/cache",
    response_model=CacheConfigResponse,
    tags=["System Configuration"],
    summary="Get cache settings",
    description="Returns cache configuration including backend, TTL, and Redis settings.",
)
async def get_cache_settings(api_key: APIKey | None = Depends(optional_auth(Role.READONLY))):
    """Get cache configuration."""
    try:
        config_manager = get_config_manager()
        cache_config = config_manager.get_cache_config()
        return CacheConfigResponse(**cache_config.to_dict(include_password=False))
    except Exception as e:
        logger.error(f"Failed to get cache settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/settings/cache",
    response_model=ConfigUpdateResponse,
    tags=["System Configuration"],
    summary="Update cache settings",
    description="Update cache configuration. Changing backend requires service restart for full effect.",
)
async def update_cache_settings(
    config_update: CacheConfigUpdate, api_key: APIKey | None = Depends(optional_auth(Role.USER))
):
    """Update cache configuration."""
    try:
        config_manager = get_config_manager()
        current_config = config_manager.get_cache_config()

        # Merge updates
        updated_config = CacheConfig(
            ttl=config_update.ttl or current_config.ttl,
            backend=config_update.backend or current_config.backend,  # type: ignore[arg-type]
            redis_url=(
                config_update.redis_url
                if config_update.redis_url is not None
                else current_config.redis_url
            ),
            redis_host=config_update.redis_host or current_config.redis_host,
            redis_port=config_update.redis_port or current_config.redis_port,
            redis_db=(
                config_update.redis_db
                if config_update.redis_db is not None
                else current_config.redis_db
            ),
            redis_username=current_config.redis_username,  # Keep from env
            redis_password=current_config.redis_password,  # Keep from env (security)
        )

        # Update configuration
        config_manager.update_cache_config(updated_config)

        # Apply to settings
        settings.CACHE_TTL = updated_config.ttl
        settings.CACHE_BACKEND = updated_config.backend
        if updated_config.redis_url:
            settings.REDIS_URL = updated_config.redis_url
        settings.REDIS_HOST = updated_config.redis_host
        settings.REDIS_PORT = updated_config.redis_port
        settings.REDIS_DB = updated_config.redis_db

        # Note: Cache backend change requires reinitializing cache
        # This is handled by RAGSystem.reinitialize_cache() if needed
        logger.info(
            f"Cache config updated: backend={updated_config.backend}, ttl={updated_config.ttl}"
        )

        return ConfigUpdateResponse(
            status="updated",
            category="cache",
            config=updated_config.to_dict(include_password=False),
            timestamp=datetime.now(),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update cache config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Safety Configuration Endpoints ==========


@router.get(
    "/settings/safety",
    response_model=SafetyConfigResponse,
    tags=["System Configuration"],
    summary="Get safety settings",
    description="Returns safety filtering configuration including mode and stream guard settings.",
)
async def get_safety_settings(api_key: APIKey | None = Depends(optional_auth(Role.READONLY))):
    """Get safety configuration."""
    try:
        config_manager = get_config_manager()
        safety_config = config_manager.get_safety_config()

        # Get active mode from ContentFilterService
        from src.core.rag_system import rag_system

        active_mode = (
            rag_system.content_filter.active_mode.value
            if hasattr(rag_system, "content_filter") and rag_system.content_filter
            else safety_config.mode
        )

        return SafetyConfigResponse(
            mode=safety_config.mode,
            active_mode=active_mode,
            stream_guard_mode=safety_config.stream_guard_mode,
        )
    except Exception as e:
        logger.error(f"Failed to get safety settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/settings/safety",
    response_model=ConfigUpdateResponse,
    tags=["System Configuration"],
    summary="Update safety settings",
    description="Update safety filtering configuration. Changes may require ContentFilterService reinitialization.",
)
async def update_safety_settings(
    config_update: SafetyConfigUpdate, api_key: APIKey | None = Depends(optional_auth(Role.USER))
):
    """Update safety configuration."""
    try:
        config_manager = get_config_manager()
        current_config = config_manager.get_safety_config()

        # Merge updates
        updated_config = SafetyConfig(
            mode=config_update.mode or current_config.mode,  # type: ignore[arg-type]
            stream_guard_mode=config_update.stream_guard_mode or current_config.stream_guard_mode,  # type: ignore[arg-type]
        )

        # Update configuration
        config_manager.update_safety_config(updated_config)

        # Apply to settings
        settings.SAFETY_MODE = updated_config.mode
        settings.STREAM_GUARD_MODE = updated_config.stream_guard_mode

        # Reinitialize ContentFilterService with new mode
        from src.api.routes import rag_system  # type: ignore[attr-defined]
        from src.core.content_filter import create_content_filter_service

        rag_system.content_filter = create_content_filter_service(
            vector_db=rag_system.vector_db, mode=updated_config.mode
        )

        active_mode = rag_system.content_filter.active_mode.value

        logger.info(
            f"Safety config updated: mode={updated_config.mode}, active={active_mode}, stream_guard={updated_config.stream_guard_mode}"
        )

        return ConfigUpdateResponse(
            status="updated",
            category="safety",
            config={
                **asdict(updated_config),
                "active_mode": active_mode,
            },
            timestamp=datetime.now(),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update safety config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Rate Limiting Configuration Endpoints ==========


@router.get(
    "/settings/rate-limit",
    response_model=RateLimitConfigResponse,
    tags=["System Configuration"],
    summary="Get rate limiting settings",
    description="Returns rate limiting configuration for different endpoint categories.",
)
async def get_rate_limit_settings(api_key: APIKey | None = Depends(optional_auth(Role.READONLY))):
    """Get rate limiting configuration."""
    try:
        config_manager = get_config_manager()
        rate_limit_config = config_manager.get_rate_limit_config()
        return RateLimitConfigResponse(**asdict(rate_limit_config))
    except Exception as e:
        logger.error(f"Failed to get rate limit settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/settings/rate-limit",
    response_model=ConfigUpdateResponse,
    tags=["System Configuration"],
    summary="Update rate limiting settings",
    description="Update rate limiting configuration. Changes take effect immediately for new requests.",
)
async def update_rate_limit_settings(
    config_update: RateLimitConfigUpdate, api_key: APIKey | None = Depends(optional_auth(Role.USER))
):
    """Update rate limiting configuration."""
    try:
        config_manager = get_config_manager()
        current_config = config_manager.get_rate_limit_config()

        # Merge updates
        updated_config = RateLimitConfig(
            enabled=(
                config_update.enabled
                if config_update.enabled is not None
                else current_config.enabled
            ),
            default_limit=config_update.default_limit or current_config.default_limit,
            query_limit=config_update.query_limit or current_config.query_limit,
            upload_limit=config_update.upload_limit or current_config.upload_limit,
            admin_limit=config_update.admin_limit or current_config.admin_limit,
            redis_url=current_config.redis_url,  # Keep from env
        )

        # Update configuration
        config_manager.update_rate_limit_config(updated_config)

        # Apply to settings
        settings.RATE_LIMIT_ENABLED = updated_config.enabled
        settings.RATE_LIMIT_DEFAULT = updated_config.default_limit
        settings.RATE_LIMIT_QUERY = updated_config.query_limit
        settings.RATE_LIMIT_UPLOAD = updated_config.upload_limit
        settings.RATE_LIMIT_ADMIN = updated_config.admin_limit

        logger.info(
            f"Rate limit config updated: enabled={updated_config.enabled}, query={updated_config.query_limit}"
        )

        return ConfigUpdateResponse(
            status="updated",
            category="rate_limit",
            config=asdict(updated_config),
            timestamp=datetime.now(),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update rate limit config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Monitoring Configuration Endpoints ==========


@router.get(
    "/settings/monitoring",
    response_model=MonitoringConfigResponse,
    tags=["System Configuration"],
    summary="Get monitoring settings",
    description="Returns monitoring and observability configuration (Prometheus, OpenTelemetry, MLflow, W&B).",
)
async def get_monitoring_settings(api_key: APIKey | None = Depends(optional_auth(Role.READONLY))):
    """Get monitoring configuration."""
    try:
        config_manager = get_config_manager()
        monitoring_config = config_manager.get_monitoring_config()
        return MonitoringConfigResponse(**asdict(monitoring_config))
    except Exception as e:
        logger.error(f"Failed to get monitoring settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/settings/monitoring",
    response_model=ConfigUpdateResponse,
    tags=["System Configuration"],
    summary="Update monitoring settings",
    description="Update monitoring configuration. Some changes may require service restart.",
)
async def update_monitoring_settings(
    config_update: MonitoringConfigUpdate, api_key: APIKey | None = Depends(optional_auth(Role.USER))
):
    """Update monitoring configuration."""
    try:
        config_manager = get_config_manager()
        current_config = config_manager.get_monitoring_config()

        # Merge updates
        updated_config = MonitoringConfig(
            prometheus_enabled=(
                config_update.prometheus_enabled
                if config_update.prometheus_enabled is not None
                else current_config.prometheus_enabled
            ),
            prometheus_route=config_update.prometheus_route or current_config.prometheus_route,
            otel_enabled=(
                config_update.otel_enabled
                if config_update.otel_enabled is not None
                else current_config.otel_enabled
            ),
            otel_service_name=config_update.otel_service_name or current_config.otel_service_name,
            otel_endpoint=(
                config_update.otel_endpoint
                if config_update.otel_endpoint is not None
                else current_config.otel_endpoint
            ),
            mlflow_enabled=(
                config_update.mlflow_enabled
                if config_update.mlflow_enabled is not None
                else current_config.mlflow_enabled
            ),
            mlflow_tracking_uri=(
                config_update.mlflow_tracking_uri
                if config_update.mlflow_tracking_uri is not None
                else current_config.mlflow_tracking_uri
            ),
            mlflow_experiment_name=current_config.mlflow_experiment_name,
            wandb_enabled=(
                config_update.wandb_enabled
                if config_update.wandb_enabled is not None
                else current_config.wandb_enabled
            ),
            wandb_project=(
                config_update.wandb_project
                if config_update.wandb_project is not None
                else current_config.wandb_project
            ),
        )

        # Update configuration
        config_manager.update_monitoring_config(updated_config)

        # Apply to settings
        settings.PROMETHEUS_ENABLED = updated_config.prometheus_enabled
        settings.PROMETHEUS_ROUTE = updated_config.prometheus_route
        settings.OTEL_ENABLED = updated_config.otel_enabled
        settings.OTEL_SERVICE_NAME = updated_config.otel_service_name
        settings.OTEL_EXPORTER_OTLP_ENDPOINT = updated_config.otel_endpoint
        settings.ENABLE_MLFLOW = updated_config.mlflow_enabled
        settings.MLFLOW_TRACKING_URI = updated_config.mlflow_tracking_uri
        settings.ENABLE_WANDB = updated_config.wandb_enabled
        settings.WANDB_PROJECT = updated_config.wandb_project

        logger.info(
            f"Monitoring config updated: prometheus={updated_config.prometheus_enabled}, otel={updated_config.otel_enabled}"
        )

        return ConfigUpdateResponse(
            status="updated",
            category="monitoring",
            config=asdict(updated_config),
            timestamp=datetime.now(),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update monitoring config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Indexing Configuration Endpoints ==========


@router.get(
    "/settings/indexing",
    response_model=IndexingConfigResponse,
    tags=["System Configuration"],
    summary="Get indexing settings",
    description="Returns document and rule indexing configuration.",
)
async def get_indexing_settings(api_key: APIKey | None = Depends(optional_auth(Role.READONLY))):
    """Get indexing configuration."""
    try:
        config_manager = get_config_manager()
        indexing_config = config_manager.get_indexing_config()

        # Sync with RAGSystem indexing mode
        from src.core.rag_system import rag_system

        indexing_config.enabled = rag_system.get_indexing_mode()

        return IndexingConfigResponse(**asdict(indexing_config))
    except Exception as e:
        logger.error(f"Failed to get indexing settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/settings/indexing",
    response_model=ConfigUpdateResponse,
    tags=["System Configuration"],
    summary="Update indexing settings",
    description="Update indexing configuration including batch size and auto-reindex settings.",
)
async def update_indexing_settings(
    config_update: IndexingConfigUpdate, api_key: APIKey | None = Depends(optional_auth(Role.USER))
):
    """Update indexing configuration."""
    try:
        config_manager = get_config_manager()
        current_config = config_manager.get_indexing_config()

        # Merge updates
        updated_config = IndexingConfig(
            enabled=(
                config_update.enabled
                if config_update.enabled is not None
                else current_config.enabled
            ),
            batch_size=config_update.batch_size or current_config.batch_size,
            auto_reindex_on_startup=(
                config_update.auto_reindex_on_startup
                if config_update.auto_reindex_on_startup is not None
                else current_config.auto_reindex_on_startup
            ),
            index_documents=(
                config_update.index_documents
                if config_update.index_documents is not None
                else current_config.index_documents
            ),
            index_rules=(
                config_update.index_rules
                if config_update.index_rules is not None
                else current_config.index_rules
            ),
        )

        # Update configuration
        config_manager.update_indexing_config(updated_config)

        # Apply to RAGSystem
        from src.api.routes import rag_system  # type: ignore[attr-defined]

        rag_system.set_indexing_mode(updated_config.enabled)

        logger.info(
            f"Indexing config updated: enabled={updated_config.enabled}, batch_size={updated_config.batch_size}"
        )

        return ConfigUpdateResponse(
            status="updated",
            category="indexing",
            config=asdict(updated_config),
            timestamp=datetime.now(),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update indexing config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Filtering Configuration Endpoints ==========


@router.get(
    "/settings/filtering",
    response_model=FilteringConfigResponse,
    tags=["System Configuration"],
    summary="Get filtering settings",
    description="Returns default filtering configuration for input and output processing.",
)
async def get_filtering_settings(api_key: APIKey | None = Depends(optional_auth(Role.READONLY))):
    """Get filtering configuration."""
    try:
        config_manager = get_config_manager()
        filtering_config = config_manager.get_filtering_config()

        return FilteringConfigResponse(
            default_input_filtering=FilteringOptions(**filtering_config.default_input_filtering),
            default_output_filtering=FilteringOptions(**filtering_config.default_output_filtering),
        )
    except Exception as e:
        logger.error(f"Failed to get filtering settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/settings/filtering",
    response_model=ConfigUpdateResponse,
    tags=["System Configuration"],
    summary="Update filtering settings",
    description="Update default filtering configuration. Changes affect all new queries that don't specify their own filtering options.",
)
async def update_filtering_settings(
    config_update: FilteringConfigUpdate, api_key: APIKey | None = Depends(optional_auth(Role.USER))
):
    """Update filtering configuration."""
    try:
        config_manager = get_config_manager()
        current_config = config_manager.get_filtering_config()

        # Merge updates
        updated_input = (
            config_update.default_input_filtering.model_dump()
            if config_update.default_input_filtering
            else current_config.default_input_filtering
        )
        updated_output = (
            config_update.default_output_filtering.model_dump()
            if config_update.default_output_filtering
            else current_config.default_output_filtering
        )

        updated_config = FilteringConfig(
            default_input_filtering=updated_input, default_output_filtering=updated_output
        )

        # Update configuration
        config_manager.update_filtering_config(updated_config)

        logger.info("Filtering config updated with new default filtering options")

        return ConfigUpdateResponse(
            status="updated",
            category="filtering",
            config={
                "default_input_filtering": updated_config.default_input_filtering,
                "default_output_filtering": updated_config.default_output_filtering,
            },
            timestamp=datetime.now(),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update filtering config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Configuration Summary Endpoint ==========


@router.get(
    "/settings/summary",
    tags=["System Configuration"],
    summary="Get configuration summary",
    description="Returns high-level summary of all system configurations.",
)
async def get_config_summary(api_key: APIKey | None = Depends(optional_auth(Role.READONLY))):
    """Get configuration summary."""
    try:
        config_manager = get_config_manager()
        summary = config_manager.get_config_summary()
        return JSONResponse(content=summary)
    except Exception as e:
        logger.error(f"Failed to get config summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Configuration Reset Endpoints ==========


@router.post(
    "/settings/reset",
    tags=["System Configuration"],
    summary="Reset all settings to defaults",
    description="Reset all system configurations to their default values from environment settings. "
    "This will reload all settings from .env file and environment variables.",
    responses={
        200: {
            "description": "All settings reset successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "reset_categories": [
                            "llm",
                            "rag",
                            "cache",
                            "safety",
                            "rate_limit",
                            "monitoring",
                            "indexing",
                            "filtering",
                        ],
                        "configurations": {
                            "llm": {"main": {"model": "openai/gpt-4o-mini", "temperature": 0.7}},
                            "rag": {"threshold": 0.75, "rerank_enabled": True},
                            "cache": {"backend": "memory", "ttl": 3600},
                        },
                        "timestamp": "2025-11-14T12:00:00",
                    }
                }
            },
        },
        500: {"description": "Failed to reset settings."},
    },
)
async def reset_all_settings(api_key: APIKey | None = Depends(optional_auth(Role.USER))):
    """Reset all system configurations to default values."""
    try:
        config_manager = get_config_manager()
        result = config_manager.reset_to_defaults()

        # Apply to settings for immediate effect
        settings.RAG_THRESHOLD = config_manager.get_rag_config().threshold
        settings.RERANK_ENABLED = config_manager.get_rag_config().rerank_enabled
        settings.CACHE_TTL = config_manager.get_cache_config().ttl
        settings.CACHE_BACKEND = config_manager.get_cache_config().backend
        settings.SAFETY_MODE = config_manager.get_safety_config().mode
        settings.STREAM_GUARD_MODE = config_manager.get_safety_config().stream_guard_mode
        settings.RATE_LIMIT_ENABLED = config_manager.get_rate_limit_config().enabled
        settings.PROMETHEUS_ENABLED = config_manager.get_monitoring_config().prometheus_enabled

        # Reinitialize ContentFilterService with reset safety mode
        try:
            from src.api.routes import rag_system
            from src.core.content_filter import create_content_filter_service

            rag_system.content_filter = create_content_filter_service(
                vector_db=rag_system.vector_db, mode=config_manager.get_safety_config().mode
            )
        except Exception as reinit_error:
            logger.warning(f"Failed to reinitialize ContentFilterService: {reinit_error}")

        logger.info("All system settings reset to defaults")

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Failed to reset all settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/settings/reset/{category}",
    tags=["System Configuration"],
    summary="Reset specific category to defaults",
    description="Reset a specific configuration category to its default values from environment settings.",
    responses={
        200: {
            "description": "Category settings reset successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "reset_categories": ["rag"],
                        "configurations": {
                            "rag": {
                                "threshold": 0.75,
                                "rerank_enabled": True,
                                "rerank_candidate_count": 15,
                            }
                        },
                        "timestamp": "2025-11-14T12:00:00",
                    }
                }
            },
        },
        400: {"description": "Invalid category provided."},
        500: {"description": "Failed to reset category settings."},
    },
)
async def reset_category_settings(category: str, api_key: APIKey | None = Depends(optional_auth(Role.USER))):
    """
    Reset specific configuration category to default values.

    Valid categories: llm, rag, cache, safety, rate_limit, monitoring, indexing, filtering
    """
    try:
        config_manager = get_config_manager()
        result = config_manager.reset_to_defaults(category=category)

        # Apply to settings for immediate effect based on category
        if category == "rag":
            rag_config = config_manager.get_rag_config()
            settings.RAG_THRESHOLD = rag_config.threshold
            settings.RERANK_ENABLED = rag_config.rerank_enabled
            settings.RERANK_CANDIDATE_COUNT = rag_config.rerank_candidate_count
            settings.RERANK_MODEL_NAME = rag_config.rerank_model_name
            settings.RERANK_SCORE_THRESHOLD = rag_config.rerank_score_threshold
            settings.RERANK_MAX_LENGTH = rag_config.rerank_max_length

        elif category == "cache":
            cache_config = config_manager.get_cache_config()
            settings.CACHE_TTL = cache_config.ttl
            settings.CACHE_BACKEND = cache_config.backend
            if cache_config.redis_url:
                settings.REDIS_URL = cache_config.redis_url
            settings.REDIS_HOST = cache_config.redis_host
            settings.REDIS_PORT = cache_config.redis_port
            settings.REDIS_DB = cache_config.redis_db

        elif category == "safety":
            safety_config = config_manager.get_safety_config()
            settings.SAFETY_MODE = safety_config.mode
            settings.STREAM_GUARD_MODE = safety_config.stream_guard_mode

            # Reinitialize ContentFilterService
            try:
                from src.api.routes import rag_system
                from src.core.content_filter import create_content_filter_service

                rag_system.content_filter = create_content_filter_service(
                    vector_db=rag_system.vector_db, mode=safety_config.mode
                )
            except Exception as reinit_error:
                logger.warning(f"Failed to reinitialize ContentFilterService: {reinit_error}")

        elif category == "rate_limit":
            rate_limit_config = config_manager.get_rate_limit_config()
            settings.RATE_LIMIT_ENABLED = rate_limit_config.enabled
            settings.RATE_LIMIT_DEFAULT = rate_limit_config.default_limit
            settings.RATE_LIMIT_QUERY = rate_limit_config.query_limit
            settings.RATE_LIMIT_UPLOAD = rate_limit_config.upload_limit
            settings.RATE_LIMIT_ADMIN = rate_limit_config.admin_limit

        elif category == "monitoring":
            monitoring_config = config_manager.get_monitoring_config()
            settings.PROMETHEUS_ENABLED = monitoring_config.prometheus_enabled
            settings.PROMETHEUS_ROUTE = monitoring_config.prometheus_route
            settings.OTEL_ENABLED = monitoring_config.otel_enabled
            settings.OTEL_SERVICE_NAME = monitoring_config.otel_service_name
            settings.OTEL_EXPORTER_OTLP_ENDPOINT = monitoring_config.otel_endpoint
            settings.ENABLE_MLFLOW = monitoring_config.mlflow_enabled
            settings.MLFLOW_TRACKING_URI = monitoring_config.mlflow_tracking_uri
            settings.ENABLE_WANDB = monitoring_config.wandb_enabled
            settings.WANDB_PROJECT = monitoring_config.wandb_project

        elif category == "indexing":
            # Indexing reset is handled by RAGSystem
            try:
                from src.api.routes import rag_system

                indexing_config = config_manager.get_indexing_config()
                rag_system.set_indexing_mode(indexing_config.enabled)
            except Exception as indexing_error:
                logger.warning(f"Failed to update RAGSystem indexing mode: {indexing_error}")

        logger.info(f"Settings for category '{category}' reset to defaults")

        return JSONResponse(content=result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to reset {category} settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))
