import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from config.settings import create_directories, settings
from src.api.middleware import CorrelationIdMiddleware, RequestMetricsMiddleware
from src.api.routes import router
from src.monitoring.tracing import configure_tracing
from src.utils.logger import logger, setup_logger

os.environ["TOKENIZERS_PARALLELISM"] = "false"


def create_application(lifespan=None) -> FastAPI:
    """
    Create and configure a FastAPI application instance.

    This function initializes the main FastAPI app, sets up routes,
    and adds necessary documentation.

    Args:
        lifespan: Optional lifespan context manager for startup/shutdown

    Returns:
        FastAPI: Configured application
    """
    # Define metadata for API documentation tags
    tags_metadata = [
        {
            "name": "Query & Generation",
            "description": "Process user queries through the AVI system with filtering and RAG capabilities. "
            "Supports both streaming and non-streaming modes.",
        },
        {
            "name": "Upload & Data Management",
            "description": "Upload and manage documents, rules, and system data. "
            "Includes endpoints for CSV uploads, cache management, and reindexing.",
        },
        {
            "name": "Rules & Documents Management",
            "description": "Manage filtering rules and documents. "
            "Create, read, update, delete rules and documents, and manage their relationships.",
        },
        {
            "name": "LLM & System Management",
            "description": "Monitor and manage LLM connections and system health. "
            "Check status of external LLM, safety LLM, and vector database.",
        },
        {
            "name": "System Configuration",
            "description": "Runtime configuration management for all AVI components. "
            "Configure LLM, RAG, cache, safety, rate limiting, monitoring, and more.",
        },
        {
            "name": "Chat",
            "description": "Chat API with AVI safety filters. "
            "Provides streaming and non-streaming chat endpoints with real-time safety scoring.",
        },
        {
            "name": "Filter Configuration",
            "description": "Dynamic filter configuration without hardcoding. "
            "Get available filters and their settings for frontend adaptation.",
        },
        {
            "name": "Experiments",
            "description": "Experiment tracking and notebook execution. "
            "Run benchmark notebooks and track experiment results with MLflow integration.",
        },
        {
            "name": "Integrations",
            "description": "External service integrations status. "
            "Check availability of Prometheus, MLflow, Grafana, and other services.",
        },
        {
            "name": "Admin - API Key Management",
            "description": "Admin operations for API key management. "
            "Create, list, revoke, and delete API keys. Requires ADMIN role.",
        },
    ]

    # Create application instance with detailed documentation
    app = FastAPI(
        title="AVI - AI Validation Interface",
        description="""
# AVI - AI Validation Interface

**AVI** is a comprehensive content filtering and safe LLM usage system that provides:

- 🛡️ **Multi-layer Safety Filtering**: Vector-based rules, LLM-based sanitization, and prompt injection detection
- 🔍 **RAG System**: Retrieve relevant documents to enhance LLM responses with context
- 📊 **Real-time Monitoring**: Track safety metrics, performance, and filter effectiveness
- ⚙️ **Runtime Configuration**: Dynamically configure LLM settings, safety modes, caching, and more
- 🔑 **API Key Management**: Secure authentication with role-based access control
- 🧪 **Experiment Tracking**: Run benchmarks and track results with MLflow integration

## Authentication

Most endpoints require authentication using an **AVI API key** (not your LLM provider key).

**Two ways to authenticate:**

1. **Swagger UI** (recommended): Click the **"Authorize" 🔓** button above and enter your AVI API key
2. **HTTP Header**: Include your API key in the `X-API-Key` header:

```http
X-API-Key: avi_your_api_key_here
```

**Note:** Your LLM provider API keys (OpenAI, Anthropic, etc.) are configured separately via environment variables and are NOT used for AVI authentication.

## Quick Start

1. **Process a Query** - `POST /api/v1/query` - Send user queries through the safety pipeline
2. **Check Health** - `GET /api/v1/health` - Verify all components are operational
3. **View Metrics** - `GET /api/v1/monitoring/metrics` - See real-time safety and performance data
4. **Configure Settings** - `/api/v1/settings/*` - Customize system behavior at runtime

## API Versioning

All endpoints are versioned under `/api/v1/` for stability and backward compatibility.
        """,
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
        openapi_tags=tags_metadata,
        contact={
            "name": "AVI Project",
            "url": "https://github.com/yourusername/avi",
        },
        license_info={
            "name": "MIT License",
            "url": "https://opensource.org/licenses/MIT",
        },
    )

    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins (for testing)
        allow_methods=["*"],  # Allow all methods
        allow_headers=["*"],  # Allow all headers
    )

    app.add_middleware(RequestMetricsMiddleware)
    app.add_middleware(CorrelationIdMiddleware, header_name=settings.CORRELATION_ID_HEADER)

    # Rate limiting (if enabled and slowapi is available)
    if settings.RATE_LIMIT_ENABLED:
        try:
            from slowapi import _rate_limit_exceeded_handler
            from slowapi.errors import RateLimitExceeded

            from src.api.rate_limit import limiter

            if limiter is not None:
                app.state.limiter = limiter
                app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
                logger.info("Rate limiting enabled")
            else:
                logger.warning("Rate limiting configured but limiter not available")
        except ImportError:
            logger.warning(
                "slowapi not installed - rate limiting disabled. Install with: pip install slowapi"
            )

    # Connect API routes without an additional prefix (already in router)
    app.include_router(router)

    # Connect admin routes for API key management (requires authentication)
    from src.api.admin_routes import router as admin_router

    app.include_router(admin_router)

    if settings.PROMETHEUS_ENABLED:
        from src.api.prometheus import metrics_endpoint

        app.add_api_route(
            settings.PROMETHEUS_ROUTE,
            metrics_endpoint,
            methods=["GET"],
            include_in_schema=False,
        )

    if settings.OTEL_ENABLED:
        configure_tracing(app)

    return app


def init_application():
    """
    Application and required component initialization.

    This function performs all necessary actions at application startup:
    creates directories, sets up logging, and checks availability
    of all required services.
    """
    try:
        # Create required directories
        create_directories()

        # Set up logging
        setup_logger()

        logger.info("Application successfully initialized")

    except Exception as e:
        logger.error(f"Error initializing application: {e!s}")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for startup and shutdown logic.

    This replaces the deprecated @app.on_event("startup") and
    @app.on_event("shutdown") decorators.
    """
    # Startup
    init_application()

    # Production configuration validation
    from src.utils.production_validators import validate_production_config

    if settings.is_production_environment():
        logger.info("Running production configuration validation...")
        passed, errors = validate_production_config()

        if not passed:
            error_msg = "Production validation failed:\n" + "\n".join(
                f"  ❌ {error}" for error in errors
            )
            logger.error(error_msg)
            raise RuntimeError(
                f"Production validation failed with {len(errors)} error(s). "
                "See logs above for details. Application startup aborted."
            )

        logger.info("✅ Production validation passed - all checks OK")
    else:
        # In dev/test mode, show warnings but don't block startup
        passed, errors = validate_production_config()
        if not passed:
            logger.warning(
                f"Configuration validation warnings (non-blocking in {settings.get_runtime_environment()}):"
            )
            for error in errors:
                logger.warning(f"  ⚠️  {error}")
        else:
            logger.info("✅ Configuration validation passed")

    # Run pre-flight health checks
    from src.utils.health import health_checker

    health_passed = await health_checker.run_startup_checks()

    if not health_passed:
        logger.warning("Some critical health checks failed, but application will continue")

    # Log LLM mode status
    import os

    test_mode = os.environ.get("AVI_TEST_MODE") == "1"
    has_main_key = bool(settings.MAIN_LLM_API_KEY.strip()) if settings.MAIN_LLM_API_KEY else False
    has_safety_key = (
        bool(settings.SAFETY_LLM_API_KEY.strip()) if settings.SAFETY_LLM_API_KEY else False
    )

    if test_mode or (not has_main_key and settings.allows_missing_api_keys()):
        logger.warning(
            "System started in MOCK mode. LLM responses will be faked. "
            "Set MAIN_LLM_API_KEY in .env to use real LLM endpoints."
        )
    elif has_main_key:
        logger.info(
            "System started in PRODUCTION mode. Using real LLM endpoints. "
            f"Main LLM: {settings.MAIN_LLM_MODEL}, "
            f"Safety LLM: {'configured' if has_safety_key else 'not configured'}"
        )

    logger.info("Application started and ready to work")

    yield

    # Shutdown
    if settings.OTEL_ENABLED:
        try:
            from opentelemetry import trace

            trace.get_tracer_provider().shutdown()
            logger.info("OpenTelemetry tracer provider shut down")
        except Exception as e:
            logger.warning(f"Error shutting down OTEL tracer: {e}")

    logger.info("Application shut down correctly")


# Export app for testing and running
app = create_application(lifespan=lifespan)

if __name__ == "__main__":
    # Run server with settings from configuration
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG, workers=1)
