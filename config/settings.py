from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.utils.logger import logger


try:
    import hvac
except ImportError:  # pragma: no cover - optional dependency in local/dev runs
    hvac = None


class Settings(BaseSettings):
    """
    Application settings.
    Supports loading values from environment variables and .env file.
    """

    # Main settings
    APP_NAME: str = "AVI_PoC"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Settings for the main LLM model
    MAIN_LLM_API_KEY: str = Field(
        "",
        validation_alias=AliasChoices(
            "MAIN_LLM_API_KEY", "EXTERNAL_LLM_API_KEY", "OPENROUTER_API_KEY"
        ),
    )
    MAIN_LLM_API_BASE: str = Field(
        "https://openrouter.ai/api/v1",
        validation_alias=AliasChoices(
            "MAIN_LLM_API_BASE",
            "EXTERNAL_LLM_API_BASE",
            "OPENROUTER_API_BASE",
        ),
    )
    MAIN_LLM_MODEL: str = Field(
        "",
        validation_alias=AliasChoices("MAIN_LLM_MODEL", "EXTERNAL_LLM_MODEL"),
    )
    MAIN_LLM_TEMPERATURE: float = Field(
        0.7,
        validation_alias=AliasChoices("MAIN_LLM_TEMPERATURE", "EXTERNAL_LLM_TEMPERATURE"),
    )
    MAIN_LLM_MAX_TOKENS: int = Field(
        2000,
        validation_alias=AliasChoices("MAIN_LLM_MAX_TOKENS", "EXTERNAL_LLM_MAX_TOKENS"),
    )

    # Safety mode selection
    SAFETY_MODE: str = "disabled"

    # Settings for the safety model
    SAFETY_LLM_API_KEY: str = ""
    SAFETY_LLM_API_BASE: str = ""
    SAFETY_LLM_MODEL: str = ""  # Can use a different model
    SAFETY_LLM_TEMPERATURE: float = 0.1  # Lower temperature for more conservative answers
    SAFETY_LLM_MAX_TOKENS: int = 1000

    # Local safety microservice configuration
    SAFETY_LOCAL_API_URL: str = ""
    SAFETY_LOCAL_TIMEOUT: float = 5.0
    SAFETY_LOCAL_HEALTHCHECK_URL: str | None = None

    SAFETY_SERVICE_URL: str = ""
    SAFETY_SERVICE_TIMEOUT: float = 5.0

    # Streaming guard configuration
    STREAM_GUARD_MODE: str = "hybrid"

    # Monitoring and observability
    PROMETHEUS_ENABLED: bool = True
    PROMETHEUS_ROUTE: str = "/metrics"
    METRICS_NAMESPACE: str = "avi"
    CORRELATION_ID_HEADER: str = "X-Correlation-ID"

    # Authentication and Authorization
    REQUIRE_API_KEY: bool = Field(
        default=False,
        description="Whether API key authentication is required for protected endpoints. "
        "Set to True in production for security. Admin endpoints always require authentication.",
    )
    API_KEY_HEADER: str = "X-API-Key"

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = Field(
        default=True, description="Enable rate limiting for API endpoints"
    )
    RATE_LIMIT_DEFAULT: str = Field(
        default="100/minute", description="Default rate limit for all endpoints"
    )
    RATE_LIMIT_QUERY: str = Field(
        default="30/minute", description="Rate limit for query/generation endpoints"
    )
    RATE_LIMIT_UPLOAD: str = Field(
        default="10/minute", description="Rate limit for file upload endpoints"
    )
    RATE_LIMIT_ADMIN: str = Field(default="50/minute", description="Rate limit for admin endpoints")
    REDIS_URL: str | None = Field(
        default=None,
        description="Optional Redis URL for distributed rate limiting (e.g., redis://localhost:6379/0)",
    )

    # Vault integration
    VAULT_ENABLED: bool = False
    VAULT_ADDR: str | None = None
    VAULT_NAMESPACE: str | None = None
    VAULT_AUTH_METHOD: str = "token"  # token or approle
    VAULT_TOKEN: str | None = None
    VAULT_ROLE_ID: str | None = None
    VAULT_SECRET_ID: str | None = None
    VAULT_MOUNT_POINT: str = "kv"
    VAULT_SECRETS_PATH: str = "avi/production"
    VAULT_SYNC_FIELDS: list[str] = Field(
        default_factory=lambda: [
            "MAIN_LLM_API_KEY",
            "MAIN_LLM_API_BASE",
            "MAIN_LLM_MODEL",
            "SAFETY_LLM_API_KEY",
            "SAFETY_LLM_API_BASE",
            "SAFETY_LLM_MODEL",
            "SAFETY_SERVICE_URL",
            "SCORING_LLM_API_KEY",
            "SCORING_LLM_API_BASE",
            "SCORING_LLM_MODEL",
        ]
    )

    # OpenTelemetry / tracing (Jaeger)
    OTEL_ENABLED: bool = False
    OTEL_SERVICE_NAME: str = "avi-api"
    OTEL_EXPORTER_OTLP_ENDPOINT: str | None = "http://jaeger:4318/v1/traces"
    OTEL_EXPORTER_OTLP_INSECURE: bool | None = None
    OTEL_EXPORTER_JAEGER_HOST: str | None = "jaeger"
    OTEL_EXPORTER_JAEGER_PORT: int = 6831

    ENABLE_MLFLOW: bool = False
    MLFLOW_TRACKING_URI: str | None = None
    MLFLOW_EXPERIMENT_NAME: str = "content_filter_metrics"
    MLFLOW_RUN_NAME: str | None = None

    ENABLE_WANDB: bool = False
    WANDB_PROJECT: str | None = None
    WANDB_ENTITY: str | None = None
    WANDB_RUN_NAME: str | None = None

    # Settings for the scoring model
    SCORING_LLM_API_KEY: str = Field(
        "",
        validation_alias=AliasChoices("SCORING_LLM_API_KEY", "SCORE_LLM_API_KEY"),
    )
    SCORING_LLM_API_BASE: str = Field(
        "",
        validation_alias=AliasChoices("SCORING_LLM_API_BASE", "SCORE_LLM_API_BASE"),
    )
    SCORING_LLM_MODEL: str = Field(
        "",
        validation_alias=AliasChoices("SCORING_LLM_MODEL", "SCORE_LLM_MODEL"),
    )
    SCORING_LLM_TEMPERATURE: float = Field(
        0.0,
        validation_alias=AliasChoices("SCORING_LLM_TEMPERATURE", "SCORE_LLM_TEMPERATURE"),
    )
    SCORING_LLM_MAX_TOKENS: int = Field(
        10,
        validation_alias=AliasChoices("SCORING_LLM_MAX_TOKENS", "SCORE_LLM_MAX_TOKENS"),
    )

    # RAG settings
    RAG_THRESHOLD: float = 0.75
    CACHE_TTL: int = 3600
    CACHE_BACKEND: str = "memory"
    # Note: REDIS_URL is defined above in Rate Limiting section (line 112)
    # and is shared between rate limiting and caching
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_USERNAME: str | None = None
    REDIS_PASSWORD: str | None = None

    # Embedding model configuration
    EMBEDDING_MODEL: str = "deepvk/USER-bge-m3"
    INDEX_DIMENSION: int = 1024
    EMBEDDING_DEVICE: str = Field(
        default="cpu",
        description=(
            "Device for embedding model inference: 'cpu' or 'cuda'. "
            "Falls back to DEVICE environment variable if not set explicitly."
        ),
    )

    RERANK_ENABLED: bool = True
    RERANK_CANDIDATE_COUNT: int = 15
    RERANK_MODEL_NAME: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    RERANK_SCORE_THRESHOLD: float = 0.0
    RERANK_MAX_LENGTH: int = 8192
    RERANK_DEVICE: str = Field(
        default="cpu",
        description=(
            "Device for reranker model inference: 'cpu' or 'cuda'. "
            "Falls back to DEVICE environment variable if not set explicitly."
        ),
    )

    # Query processing settings for long queries
    MAX_QUERY_LENGTH: int = Field(
        default=100000,
        description="Maximum allowed query length in characters (DoS protection)",
    )
    QUERY_DIRECT_THRESHOLD: int = Field(
        default=8000,
        description="Queries below this length are processed directly; above are chunked",
    )
    CHUNK_SIZE: int = Field(
        default=6000,
        description="Chunk size for splitting long queries (characters). Should be < embedding model max length.",
    )
    CHUNK_OVERLAP: int = Field(
        default=500,
        description="Overlap between consecutive chunks (characters) to maintain context",
    )
    MAX_SEARCH_QUERIES: int = Field(
        default=5,
        description="Maximum number of search queries to extract from chunked long queries",
    )

    # === Filtering & Detection Thresholds (Production-Tuned) ===

    # Content Filter - Lowered thresholds for better sensitivity
    FILTER_DEFAULT_THRESHOLD: float = Field(
        default=0.60,  # Lowered from 0.75 for production
        ge=0.0,
        le=1.0,
        description="Default relevance threshold for filter rule activation",
    )
    FILTER_FALLBACK_THRESHOLD: float = Field(
        default=0.50,  # Lowered from 0.65 for production
        ge=0.0,
        le=1.0,
        description="Fallback threshold when rule-specific threshold unavailable",
    )

    # Prompt Modification Template
    PROMPT_MODIFICATION_TEMPLATE: str = Field(
        default=(
            "Remember to adhere to safety guidelines and answer ethically. "
            "User question: USER QUESTION: {text}\n"
            "CONTEXT: {context}\n"
        ),
        description=(
            "Template for modifying prompts when filter rules match. "
            "Must contain {text} and {context} variables."
        ),
    )

    # Governed System Prompt — injected as system-level instruction when a governance rule triggers.
    # Replaces the default system prompt to prevent parametric bypass (LLM reasoning about
    # restricted topics from training-time knowledge).
    # Supports {policy_text} and {compliant_example} variables.
    GOVERNED_SYSTEM_PROMPT: str = Field(
        default=(
            "You are a helpful assistant operating under strict information governance.\n\n"
            "ACTIVE EMBARGO POLICY:\n{policy_text}\n\n"
            "{compliant_example}"
            "STRICT RULES (mandatory — no exceptions):\n"
            "- Do NOT calculate, estimate, approximate, or derive the restricted information\n"
            "- Do NOT provide numeric values, ranges, or percentages related to the restricted metric\n"
            "- Do NOT provide context (revenue, costs, ratios, figures) from which the restricted "
            "value could be inferred\n"
            "- Do NOT say 'approximately', 'around', 'roughly', or give directional hints\n"
            "- Do NOT explain calculation methods using company-specific data\n"
            "- Do NOT reference prior knowledge about this company's financials\n\n"
            "REQUIRED response format:\n"
            "1. Acknowledge the user's request professionally\n"
            "2. State that this specific information is restricted per confidentiality policy\n"
            "3. Direct the user to a legitimate alternative source (SEC filing, IR page, etc.)\n"
            "4. Offer to help with a related non-restricted question\n"
        ),
        description=(
            "System prompt injected when a governance rule triggers. "
            "Supports {policy_text} and {compliant_example} variables."
        ),
    )

    # Few-shot compliant example block injected into GOVERNED_SYSTEM_PROMPT.
    # Shows the LLM exactly what a compliant response looks like, with explicit
    # NON-COMPLIANT patterns to avoid (parametric bypass prevention).
    GOVERNED_COMPLIANT_EXAMPLE: str = Field(
        default=(
            "EXAMPLE — how to respond correctly:\n"
            "User asks: 'What was Acme Corp's FY2023 operating margin?'\n"
            "COMPLIANT response: 'Thank you for your question. Acme Corp's FY2023 operating "
            "margin data is currently restricted per the active confidentiality policy. "
            "For official figures, please refer to Acme Corp's 10-K filing on the SEC EDGAR "
            "database or the company's Investor Relations page. I'd be happy to help you with "
            "other non-restricted aspects of Acme Corp's business or strategy.'\n\n"
            "NON-COMPLIANT patterns to STRICTLY AVOID:\n"
            "× 'Based on typical industry margins...' (contextual inference)\n"
            "× 'The operating margin is approximately 15%...' (numeric disclosure)\n"
            "× 'Revenue was $X and EBIT was $Y, so the margin would be...' (derivation)\n"
            "× 'From public filings, Acme historically reported margins of...' (bypass via memory)\n\n"
        ),
        description=(
            "Few-shot compliant/non-compliant example injected into the governed system prompt "
            "to prevent parametric bypass. Inserted at {compliant_example} in GOVERNED_SYSTEM_PROMPT."
        ),
    )

    # Vector Search Configuration
    VECTOR_SEARCH_TOP_K: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of top similar rules to retrieve from vector database",
    )
    VECTOR_SEARCH_SIMILARITY_MIN: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score to consider a match",
    )

    # RAG Document Retrieval
    RAG_CANDIDATE_COUNT: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of candidate documents for RAG retrieval",
    )
    RAG_RELEVANCE_THRESHOLD: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum relevance score for RAG documents",
    )

    # Cache Performance Settings
    CACHE_MAX_SIZE: int = Field(
        default=10000,
        ge=100,
        le=1000000,
        description="Maximum number of items in memory cache",
    )

    # Data paths
    DATA_DIR: Path = Path("./data")
    RAW_DATA_DIR: Path = Path("./data/raw")
    PROCESSED_DATA_DIR: Path = Path("./data/processed")
    INDEXES_DIR: Path = Path("./data/indexes")
    FEEDBACK_DIR: Path = Path("./data/feedback")

    # Vector DB settings
    VECTOR_DB_PATH: Path = Path("./data/indexes/chroma")
    VECTOR_DB_PROVIDER: str = "chroma"
    QDRANT_HOST: str | None = None
    QDRANT_PORT: int | None = None
    QDRANT_API_KEY: str | None = None
    QDRANT_PATH: Path = Path("./data/indexes/qdrant")

    # API configuration
    API_BASE: str = ""  # Base API URL
    API_KEY: str = ""  # For API authorization

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    def model_post_init(self, __context: Any) -> None:
        """Post-initialization hook to handle device fallback logic."""
        import os

        # Fallback to DEVICE env var if specific device settings are default 'cpu'
        device_env = os.getenv("DEVICE", "cpu").lower()

        # Only override if user didn't explicitly set EMBEDDING_DEVICE and DEVICE env var is set
        if self.EMBEDDING_DEVICE == "cpu" and device_env != "cpu":
            self.EMBEDDING_DEVICE = device_env
            logger.info(f"Using DEVICE={device_env} for embeddings (fallback from env)")

        # Only override if user didn't explicitly set RERANK_DEVICE and DEVICE env var is set
        if self.RERANK_DEVICE == "cpu" and device_env != "cpu":
            self.RERANK_DEVICE = device_env
            logger.info(f"Using DEVICE={device_env} for reranker (fallback from env)")

    def get_runtime_environment(self) -> str:
        """Return the normalized runtime environment."""
        env = (self.ENVIRONMENT or "").strip()
        return env.lower() or "development"

    @field_validator("CACHE_BACKEND")
    @classmethod
    def validate_cache_backend(cls, value: str) -> str:
        normalized = (value or "memory").strip().lower()
        if normalized not in {"memory", "redis"}:
            raise ValueError("CACHE_BACKEND must be either 'memory' or 'redis'")
        return normalized

    @field_validator("PROMPT_MODIFICATION_TEMPLATE")
    @classmethod
    def validate_prompt_template(cls, value: str) -> str:
        """Validate that prompt template contains required variables."""
        if not value:
            raise ValueError("PROMPT_MODIFICATION_TEMPLATE cannot be empty")
        if "{text}" not in value:
            raise ValueError("PROMPT_MODIFICATION_TEMPLATE must contain {text} variable")
        if "{context}" not in value:
            raise ValueError("PROMPT_MODIFICATION_TEMPLATE must contain {context} variable")
        return value

    def is_production_environment(self) -> bool:
        """Return True if the app runs in production mode."""
        return self.get_runtime_environment() in {"production", "prod"}

    def allows_missing_api_keys(self) -> bool:
        """Return True if missing API keys are allowed for the current env."""
        return self.get_runtime_environment() in {
            "development",
            "dev",
            "test",
            "testing",
        }

    def is_safety_llm_configured(self) -> bool:
        """Return True when the safety LLM has the necessary credentials."""
        return bool(self.SAFETY_LLM_API_KEY and self.SAFETY_LLM_MODEL)

    @field_validator("SAFETY_MODE", mode="before")
    @classmethod
    def validate_safety_mode(cls, value: str | None) -> str:
        allowed_modes = {"disabled", "local", "llm", "remote", "external", "hybrid"}
        if value is None:
            return "disabled"
        normalized = str(value).strip().lower()
        if not normalized:
            return "disabled"
        if normalized == "service":
            normalized = "local"
        if normalized not in allowed_modes:
            raise ValueError(
                "SAFETY_MODE must be one of: disabled, local, llm, remote, external, hybrid"
            )
        return normalized

    def get_safety_mode(self) -> str:
        """Return the configured safety mode."""
        return self.SAFETY_MODE

    def is_main_llm_configured(self) -> bool:
        """Return True when the main LLM has the necessary credentials."""
        return bool(self.MAIN_LLM_API_KEY and self.MAIN_LLM_MODEL)

    def validate_api_settings(self) -> None:
        """
        Validate API settings.

        Raises:
            ValueError: If settings are invalid
        """
        missing_allowed = self.allows_missing_api_keys()

        def _handle_missing(field_name: str) -> None:
            if missing_allowed:
                logger.info(
                    "Skipping strict validation for {} in {} environment.",
                    field_name,
                    self.get_runtime_environment(),
                )
            else:
                logger.error(
                    "{} is not set in {} environment.",
                    field_name,
                    self.get_runtime_environment(),
                )
                raise ValueError(f"{field_name} is not set")

        # Check main model settings
        if not self.MAIN_LLM_API_KEY:
            _handle_missing("MAIN_LLM_API_KEY")

        if not self.MAIN_LLM_MODEL:
            _handle_missing("MAIN_LLM_MODEL")

        safety_mode = self.get_safety_mode()
        llm_modes = {"llm", "remote", "external", "hybrid"}

        if safety_mode in llm_modes:
            if not self.SAFETY_LLM_API_KEY:
                _handle_missing("SAFETY_LLM_API_KEY")

            if not self.SAFETY_LLM_MODEL:
                _handle_missing("SAFETY_LLM_MODEL")
        elif safety_mode != "disabled":
            if not self.SAFETY_SERVICE_URL:
                _handle_missing("SAFETY_SERVICE_URL")

        if not self.SCORING_LLM_API_KEY:
            logger.warning(
                "SCORING_LLM_API_KEY is not set. SCORE functionality will be unavailable."
            )

    def apply_vault_overrides(self) -> None:
        """Fetch secrets from HashiCorp Vault and override configured fields."""

        if not self.VAULT_ENABLED:
            return

        if hvac is None:
            raise RuntimeError(
                "hvac is required when VAULT_ENABLED is true. Install the optional dependency."
            )

        if not self.VAULT_ADDR:
            raise ValueError("VAULT_ADDR must be set when VAULT_ENABLED is true")

        client = hvac.Client(url=self.VAULT_ADDR, namespace=self.VAULT_NAMESPACE)

        if self.VAULT_AUTH_METHOD.lower() == "approle":
            if not (self.VAULT_ROLE_ID and self.VAULT_SECRET_ID):
                raise ValueError(
                    "VAULT_ROLE_ID and VAULT_SECRET_ID are required when using approle auth"
                )
            client.auth_approle(role_id=self.VAULT_ROLE_ID, secret_id=self.VAULT_SECRET_ID)
        else:
            if not self.VAULT_TOKEN:
                raise ValueError("VAULT_TOKEN must be set when using token authentication")
            client.token = self.VAULT_TOKEN

        if not client.is_authenticated():
            raise RuntimeError("Failed to authenticate with HashiCorp Vault")

        if not self.VAULT_SECRETS_PATH:
            raise ValueError("VAULT_SECRETS_PATH must be provided to load secrets")

        try:
            secret_response = client.secrets.kv.v2.read_secret_version(
                path=self.VAULT_SECRETS_PATH,
                mount_point=self.VAULT_MOUNT_POINT,
            )
        except hvac.exceptions.InvalidPath:
            raise ValueError(
                f"Vault path '{self.VAULT_MOUNT_POINT}/{self.VAULT_SECRETS_PATH}' was not found"
            ) from None

        secret_data: dict[str, Any] = secret_response.get("data", {}).get("data", {})

        overrides: dict[str, Any] = {}
        for field in self.VAULT_SYNC_FIELDS:
            if field in secret_data and field in self.model_fields:
                overrides[field] = secret_data[field]

        for field, value in overrides.items():
            object.__setattr__(self, field, value)

        if overrides:
            logger.info(
                "Loaded %d secret overrides from Vault for fields: %s",
                len(overrides),
                ", ".join(sorted(overrides.keys())),
            )

    def get_bot_log_path(self) -> Path:
        """Get path to bot log file"""
        logs_dir = self.DATA_DIR / "logs"
        # Directory creation now handled by DirectoryManager
        return logs_dir / "bot.log"

    def update_prompt_template(self, new_template: str) -> None:
        """
        Update the prompt modification template at runtime.

        Args:
            new_template: New template string (must contain {text} and {context})

        Raises:
            ValueError: If template is invalid or missing required variables
        """
        # Validate the new template
        if not new_template:
            raise ValueError("PROMPT_MODIFICATION_TEMPLATE cannot be empty")
        if "{text}" not in new_template:
            raise ValueError("PROMPT_MODIFICATION_TEMPLATE must contain {text} variable")
        if "{context}" not in new_template:
            raise ValueError("PROMPT_MODIFICATION_TEMPLATE must contain {context} variable")

        # Use object.__setattr__ because Settings is immutable by default in Pydantic v2
        object.__setattr__(self, "PROMPT_MODIFICATION_TEMPLATE", new_template)
        logger.info("Prompt modification template updated successfully")


class DirectoryManager:
    """Centralized directory management for the application."""

    def __init__(self, settings: Settings):
        """
        Initialize the directory manager.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self._created = False
        self._lock = None  # Will be set to threading.Lock() if needed

    def ensure_all(self) -> None:
        """Create all required directories once."""
        if self._created:
            return

        directories = [
            self.settings.DATA_DIR,
            self.settings.RAW_DATA_DIR,
            self.settings.PROCESSED_DATA_DIR,
            self.settings.INDEXES_DIR,
            self.settings.FEEDBACK_DIR,
            self.settings.VECTOR_DB_PATH,
            self.settings.QDRANT_PATH,
            self.settings.DATA_DIR / "logs",
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

        self._created = True
        logger.info("All required directories created successfully")

    def ensure_directory(self, path: Path) -> None:
        """
        Ensure a specific directory exists.

        Args:
            path: Directory path to create
        """
        path.mkdir(parents=True, exist_ok=True)

    def ensure_parent(self, file_path: Path) -> None:
        """
        Ensure the parent directory of a file exists.

        Args:
            file_path: File path whose parent directory should be created
        """
        if file_path.parent:
            file_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Get application settings with caching."""
    settings = Settings()
    settings.apply_vault_overrides()
    settings.validate_api_settings()
    return settings


# Create settings instance
settings = get_settings()

# Create directory manager instance
directory_manager = DirectoryManager(settings)

# Удаляем логирование ключевых параметров для диагностики


# Backwards compatibility - deprecated, use directory_manager.ensure_all() instead
def create_directories():
    """
    Create required directories at application startup.

    .. deprecated::
        Use `directory_manager.ensure_all()` instead.
    """
    directory_manager.ensure_all()
