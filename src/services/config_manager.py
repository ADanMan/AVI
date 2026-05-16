"""
Centralized configuration manager for AVI system.

Provides runtime configuration management for all system components:
- LLM configurations (main, safety, scoring)
- RAG settings (threshold, reranking)
- Cache settings (TTL, backend)
- Safety settings (mode, stream guard)
- Rate limiting settings
- Monitoring settings (Prometheus, OpenTelemetry)
- Indexing settings

All config updates are thread-safe and validated before application.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from threading import RLock
from typing import Any, Literal

from config.settings import settings
from src.utils.logger import logger


# Type aliases
LLMRole = Literal["main", "safety", "scoring"]
CacheBackend = Literal["memory", "redis"]
SafetyMode = Literal["disabled", "external", "local", "hybrid", "plugin"]
StreamGuardMode = Literal["rule-only", "llm-only", "hybrid", "bypass"]


@dataclass
class LLMConfig:
    """Configuration for a single LLM instance."""

    model: str
    api_key: str
    api_base: str
    temperature: float
    max_tokens: int
    top_p: float = 1.0
    timeout: float = 30.0
    system_prompt: str | None = None

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []

        if not self.model or not self.model.strip():
            errors.append("model cannot be empty")

        if self.temperature < 0.0 or self.temperature > 2.0:
            errors.append(f"temperature must be 0.0-2.0, got {self.temperature}")

        if self.max_tokens <= 0:
            errors.append(f"max_tokens must be positive, got {self.max_tokens}")

        if self.top_p < 0.0 or self.top_p > 1.0:
            errors.append(f"top_p must be 0.0-1.0, got {self.top_p}")

        if self.timeout <= 0:
            errors.append(f"timeout must be positive, got {self.timeout}")

        return errors

    def to_dict(self, include_api_key: bool = False) -> dict[str, Any]:
        """Convert to dict, optionally masking API key."""
        data = asdict(self)
        if not include_api_key:
            data["api_key"] = "***" if self.api_key else None
        return data


@dataclass
class RAGConfig:
    """RAG (Retrieval-Augmented Generation) configuration."""

    threshold: float = 0.75
    rerank_enabled: bool = True
    rerank_candidate_count: int = 15
    rerank_model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    rerank_score_threshold: float = 0.0
    rerank_max_length: int = 512

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []

        if self.threshold < 0.0 or self.threshold > 1.0:
            errors.append(f"threshold must be 0.0-1.0, got {self.threshold}")

        if self.rerank_candidate_count <= 0:
            errors.append(
                f"rerank_candidate_count must be positive, got {self.rerank_candidate_count}"
            )

        if self.rerank_score_threshold < 0.0:
            errors.append(
                f"rerank_score_threshold must be >= 0.0, got {self.rerank_score_threshold}"
            )

        if self.rerank_max_length <= 0:
            errors.append(f"rerank_max_length must be positive, got {self.rerank_max_length}")

        if not self.rerank_model_name or not self.rerank_model_name.strip():
            errors.append("rerank_model_name cannot be empty")

        return errors


@dataclass
class CacheConfig:
    """Cache configuration."""

    ttl: int = 3600  # seconds
    backend: CacheBackend = "memory"
    redis_url: str | None = None
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_username: str | None = None
    redis_password: str | None = None

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []

        if self.ttl <= 0:
            errors.append(f"ttl must be positive, got {self.ttl}")

        if self.backend not in {"memory", "redis"}:
            errors.append(f"backend must be 'memory' or 'redis', got {self.backend}")

        if self.backend == "redis":
            if not self.redis_url and not self.redis_host:
                errors.append("redis_url or redis_host required when backend is 'redis'")

        if self.redis_port <= 0 or self.redis_port > 65535:
            errors.append(f"redis_port must be 1-65535, got {self.redis_port}")

        if self.redis_db < 0:
            errors.append(f"redis_db must be >= 0, got {self.redis_db}")

        return errors

    def to_dict(self, include_password: bool = False) -> dict[str, Any]:
        """Convert to dict, optionally masking password."""
        data = asdict(self)
        if not include_password and self.redis_password:
            data["redis_password"] = "***"  # noqa: S105  # Not a password, masking for display
        return data


@dataclass
class SafetyConfig:
    """Safety filtering configuration."""

    mode: SafetyMode = "disabled"
    stream_guard_mode: StreamGuardMode = "hybrid"

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []

        valid_modes = {"disabled", "external", "local", "hybrid", "plugin"}
        if self.mode not in valid_modes:
            errors.append(f"mode must be one of {valid_modes}, got {self.mode}")

        valid_stream_modes = {"rule-only", "llm-only", "hybrid", "bypass"}
        if self.stream_guard_mode not in valid_stream_modes:
            errors.append(
                f"stream_guard_mode must be one of {valid_stream_modes}, got {self.stream_guard_mode}"
            )

        return errors


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""

    enabled: bool = True
    default_limit: str = "100/minute"
    query_limit: str = "30/minute"
    upload_limit: str = "10/minute"
    admin_limit: str = "50/minute"
    redis_url: str | None = None

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []

        # Validate rate limit format (e.g., "100/minute", "10/hour")
        for field_name, limit_str in [
            ("default_limit", self.default_limit),
            ("query_limit", self.query_limit),
            ("upload_limit", self.upload_limit),
            ("admin_limit", self.admin_limit),
        ]:
            if not self._validate_limit_format(limit_str):
                errors.append(
                    f"{field_name} must be in format 'N/unit' (e.g., '100/minute'), got {limit_str}"
                )

        return errors

    @staticmethod
    def _validate_limit_format(limit_str: str) -> bool:
        """Validate rate limit string format."""
        try:
            parts = limit_str.split("/")
            if len(parts) != 2:
                return False

            count = int(parts[0])
            unit = parts[1].lower()

            if count <= 0:
                return False

            valid_units = {"second", "minute", "hour", "day"}
            return unit in valid_units
        except (ValueError, AttributeError):
            return False


@dataclass
class MonitoringConfig:
    """Monitoring and observability configuration."""

    prometheus_enabled: bool = True
    prometheus_route: str = "/metrics"
    otel_enabled: bool = False
    otel_service_name: str = "avi-api"
    otel_endpoint: str | None = None
    mlflow_enabled: bool = False
    mlflow_tracking_uri: str | None = None
    mlflow_experiment_name: str = "content_filter_metrics"
    wandb_enabled: bool = False
    wandb_project: str | None = None

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []

        if not self.prometheus_route or not self.prometheus_route.startswith("/"):
            errors.append(
                f"prometheus_route must start with '/', got {self.prometheus_route or 'empty'}"
            )

        if self.otel_enabled and not self.otel_endpoint:
            errors.append("otel_endpoint required when otel_enabled is True")

        if self.mlflow_enabled and not self.mlflow_tracking_uri:
            errors.append("mlflow_tracking_uri required when mlflow_enabled is True")

        if self.wandb_enabled and not self.wandb_project:
            errors.append("wandb_project required when wandb_enabled is True")

        if not self.otel_service_name or not self.otel_service_name.strip():
            errors.append("otel_service_name cannot be empty")

        return errors


@dataclass
class IndexingConfig:
    """Document indexing configuration."""

    enabled: bool = True
    batch_size: int = 100
    auto_reindex_on_startup: bool = False
    index_documents: bool = True
    index_rules: bool = True

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []

        if self.batch_size <= 0:
            errors.append(f"batch_size must be positive, got {self.batch_size}")

        return errors


@dataclass
class FilteringConfig:
    """Default filtering configuration for input and output processing."""

    # Use dict representation of FilteringOptions to avoid circular imports
    default_input_filtering: dict[str, bool] | None = None
    default_output_filtering: dict[str, bool] | None = None

    def __post_init__(self):
        """Set defaults if not provided."""
        if self.default_input_filtering is None:
            self.default_input_filtering = {
                "enable_vector_rules": True,
                "enable_safety_llm": True,
                "enable_prompt_modification": True,
                "enable_output_cleaning": False,  # N/A for input
            }
        if self.default_output_filtering is None:
            self.default_output_filtering = {
                "enable_vector_rules": True,
                "enable_safety_llm": False,  # Usually not needed for output
                "enable_prompt_modification": False,  # N/A for output
                "enable_output_cleaning": True,
            }

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []

        # Validate that all required keys are present
        required_keys = {
            "enable_vector_rules",
            "enable_safety_llm",
            "enable_prompt_modification",
            "enable_output_cleaning",
        }

        for field_name, config_dict in [
            ("default_input_filtering", self.default_input_filtering),
            ("default_output_filtering", self.default_output_filtering),
        ]:
            if not isinstance(config_dict, dict):
                errors.append(f"{field_name} must be a dict")
                continue

            missing_keys = required_keys - set(config_dict.keys())
            if missing_keys:
                errors.append(f"{field_name} missing keys: {missing_keys}")

            extra_keys = set(config_dict.keys()) - required_keys
            if extra_keys:
                errors.append(f"{field_name} has unexpected keys: {extra_keys}")

            # Validate that all values are booleans
            for key, value in config_dict.items():
                if not isinstance(value, bool):
                    errors.append(f"{field_name}.{key} must be a boolean, got {type(value)}")

        return errors


class ConfigurationManager:
    """
    Centralized manager for all AVI system configurations.

    Provides thread-safe runtime configuration updates for:
    - LLM configurations (main, safety, scoring)
    - RAG settings
    - Cache settings
    - Safety settings
    - Rate limiting
    - Monitoring
    - Indexing

    All configuration changes are validated before application.
    """

    def __init__(self) -> None:
        """Initialize configuration manager with settings from environment."""
        self._lock = RLock()
        self._configs: dict[str, Any] = {
            "llm": {},  # main, safety, scoring
            "rag": None,
            "cache": None,
            "safety": None,
            "rate_limit": None,
            "monitoring": None,
            "indexing": None,
            "filtering": None,
        }
        self._last_updated: dict[str, datetime] = {}
        self._load_from_settings()
        logger.info("ConfigurationManager initialized with settings from environment")

    def _load_from_settings(self) -> None:
        """Load initial configuration from settings.py."""
        # LLM Configurations
        self._configs["llm"]["main"] = LLMConfig(
            model=settings.MAIN_LLM_MODEL or "",
            api_key=settings.MAIN_LLM_API_KEY or "",
            api_base=settings.MAIN_LLM_API_BASE or "https://openrouter.ai/api/v1",
            temperature=settings.MAIN_LLM_TEMPERATURE,
            max_tokens=settings.MAIN_LLM_MAX_TOKENS,
        )

        if settings.SAFETY_LLM_MODEL:
            self._configs["llm"]["safety"] = LLMConfig(
                model=settings.SAFETY_LLM_MODEL,
                api_key=settings.SAFETY_LLM_API_KEY or "",
                api_base=settings.SAFETY_LLM_API_BASE or "",
                temperature=settings.SAFETY_LLM_TEMPERATURE,
                max_tokens=settings.SAFETY_LLM_MAX_TOKENS,
            )

        if settings.SCORING_LLM_MODEL:
            self._configs["llm"]["scoring"] = LLMConfig(
                model=settings.SCORING_LLM_MODEL,
                api_key=settings.SCORING_LLM_API_KEY or "",
                api_base=settings.SCORING_LLM_API_BASE or "",
                temperature=settings.SCORING_LLM_TEMPERATURE,
                max_tokens=settings.SCORING_LLM_MAX_TOKENS,
            )

        # RAG Configuration
        self._configs["rag"] = RAGConfig(
            threshold=settings.RAG_THRESHOLD,
            rerank_enabled=settings.RERANK_ENABLED,
            rerank_candidate_count=settings.RERANK_CANDIDATE_COUNT,
            rerank_model_name=settings.RERANK_MODEL_NAME,
            rerank_score_threshold=settings.RERANK_SCORE_THRESHOLD,
            rerank_max_length=settings.RERANK_MAX_LENGTH,
        )

        # Cache Configuration
        self._configs["cache"] = CacheConfig(
            ttl=settings.CACHE_TTL,
            backend=settings.CACHE_BACKEND,  # type: ignore[arg-type]
            redis_url=settings.REDIS_URL,
            redis_host=settings.REDIS_HOST,
            redis_port=settings.REDIS_PORT,
            redis_db=settings.REDIS_DB,
            redis_username=settings.REDIS_USERNAME,
            redis_password=settings.REDIS_PASSWORD,
        )

        # Safety Configuration
        self._configs["safety"] = SafetyConfig(
            mode=settings.SAFETY_MODE,  # type: ignore[arg-type]
            stream_guard_mode=settings.STREAM_GUARD_MODE,  # type: ignore[arg-type]
        )

        # Rate Limiting Configuration
        self._configs["rate_limit"] = RateLimitConfig(
            enabled=settings.RATE_LIMIT_ENABLED,
            default_limit=settings.RATE_LIMIT_DEFAULT,
            query_limit=settings.RATE_LIMIT_QUERY,
            upload_limit=settings.RATE_LIMIT_UPLOAD,
            admin_limit=settings.RATE_LIMIT_ADMIN,
            redis_url=settings.REDIS_URL,
        )

        # Monitoring Configuration
        self._configs["monitoring"] = MonitoringConfig(
            prometheus_enabled=settings.PROMETHEUS_ENABLED,
            prometheus_route=settings.PROMETHEUS_ROUTE,
            otel_enabled=settings.OTEL_ENABLED,
            otel_service_name=settings.OTEL_SERVICE_NAME,
            otel_endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
            mlflow_enabled=settings.ENABLE_MLFLOW,
            mlflow_tracking_uri=settings.MLFLOW_TRACKING_URI,
            mlflow_experiment_name=settings.MLFLOW_EXPERIMENT_NAME,
            wandb_enabled=settings.ENABLE_WANDB,
            wandb_project=settings.WANDB_PROJECT,
        )

        # Indexing Configuration
        # Note: indexing_enabled is managed by RAGSystem, we sync with it
        self._configs["indexing"] = IndexingConfig(
            enabled=True,  # Will be synced with RAGSystem
            batch_size=100,  # Default batch size for indexing operations
            auto_reindex_on_startup=False,
            index_documents=True,
            index_rules=True,
        )

        # Filtering Configuration
        # Default filtering options for input and output processing
        self._configs["filtering"] = FilteringConfig()

    # ========== LLM Configuration ==========

    def get_llm_config(self, role: LLMRole) -> LLMConfig | None:
        """
        Get LLM configuration for a specific role.

        Args:
            role: LLM role (main, safety, scoring)

        Returns:
            LLM configuration or None if not configured
        """
        with self._lock:
            return self._configs["llm"].get(role)

    def update_llm_config(self, role: LLMRole, config: LLMConfig) -> None:
        """
        Update LLM configuration for a specific role.

        Args:
            role: LLM role (main, safety, scoring)
            config: New LLM configuration

        Raises:
            ValueError: If configuration is invalid
        """
        errors = config.validate()
        if errors:
            raise ValueError(f"Invalid LLM config for role '{role}': {', '.join(errors)}")

        with self._lock:
            self._configs["llm"][role] = config
            self._last_updated[f"llm.{role}"] = datetime.now()
            logger.info(f"LLM config updated for role '{role}': model={config.model}")

    def get_all_llm_configs(self) -> dict[str, dict[str, Any]]:
        """Get all LLM configurations as dictionary."""
        with self._lock:
            return {
                role: config.to_dict(include_api_key=False)
                for role, config in self._configs["llm"].items()
            }

    # ========== RAG Configuration ==========

    def get_rag_config(self) -> RAGConfig:
        """Get RAG configuration."""
        with self._lock:
            return self._configs["rag"]

    def update_rag_config(self, config: RAGConfig) -> None:
        """
        Update RAG configuration.

        Args:
            config: New RAG configuration

        Raises:
            ValueError: If configuration is invalid
        """
        errors = config.validate()
        if errors:
            raise ValueError(f"Invalid RAG config: {', '.join(errors)}")

        with self._lock:
            self._configs["rag"] = config
            self._last_updated["rag"] = datetime.now()
            logger.info(
                f"RAG config updated: threshold={config.threshold}, rerank={config.rerank_enabled}"
            )

    # ========== Cache Configuration ==========

    def get_cache_config(self) -> CacheConfig:
        """Get cache configuration."""
        with self._lock:
            return self._configs["cache"]

    def update_cache_config(self, config: CacheConfig) -> None:
        """
        Update cache configuration.

        Args:
            config: New cache configuration

        Raises:
            ValueError: If configuration is invalid
        """
        errors = config.validate()
        if errors:
            raise ValueError(f"Invalid cache config: {', '.join(errors)}")

        with self._lock:
            self._configs["cache"] = config
            self._last_updated["cache"] = datetime.now()
            logger.info(f"Cache config updated: backend={config.backend}, ttl={config.ttl}")

    # ========== Safety Configuration ==========

    def get_safety_config(self) -> SafetyConfig:
        """Get safety configuration."""
        with self._lock:
            return self._configs["safety"]

    def update_safety_config(self, config: SafetyConfig) -> None:
        """
        Update safety configuration.

        Args:
            config: New safety configuration

        Raises:
            ValueError: If configuration is invalid
        """
        errors = config.validate()
        if errors:
            raise ValueError(f"Invalid safety config: {', '.join(errors)}")

        with self._lock:
            self._configs["safety"] = config
            self._last_updated["safety"] = datetime.now()
            logger.info(
                f"Safety config updated: mode={config.mode}, stream_guard={config.stream_guard_mode}"
            )

    # ========== Rate Limiting Configuration ==========

    def get_rate_limit_config(self) -> RateLimitConfig:
        """Get rate limiting configuration."""
        with self._lock:
            return self._configs["rate_limit"]

    def update_rate_limit_config(self, config: RateLimitConfig) -> None:
        """
        Update rate limiting configuration.

        Args:
            config: New rate limiting configuration

        Raises:
            ValueError: If configuration is invalid
        """
        errors = config.validate()
        if errors:
            raise ValueError(f"Invalid rate limit config: {', '.join(errors)}")

        with self._lock:
            self._configs["rate_limit"] = config
            self._last_updated["rate_limit"] = datetime.now()
            logger.info(
                f"Rate limit config updated: enabled={config.enabled}, query={config.query_limit}"
            )

    # ========== Monitoring Configuration ==========

    def get_monitoring_config(self) -> MonitoringConfig:
        """Get monitoring configuration."""
        with self._lock:
            return self._configs["monitoring"]

    def update_monitoring_config(self, config: MonitoringConfig) -> None:
        """
        Update monitoring configuration.

        Args:
            config: New monitoring configuration

        Raises:
            ValueError: If configuration is invalid
        """
        errors = config.validate()
        if errors:
            raise ValueError(f"Invalid monitoring config: {', '.join(errors)}")

        with self._lock:
            self._configs["monitoring"] = config
            self._last_updated["monitoring"] = datetime.now()
            logger.info(
                f"Monitoring config updated: prometheus={config.prometheus_enabled}, "
                f"otel={config.otel_enabled}"
            )

    # ========== Indexing Configuration ==========

    def get_indexing_config(self) -> IndexingConfig:
        """Get indexing configuration."""
        with self._lock:
            return self._configs["indexing"]

    def update_indexing_config(self, config: IndexingConfig) -> None:
        """
        Update indexing configuration.

        Args:
            config: New indexing configuration

        Raises:
            ValueError: If configuration is invalid
        """
        errors = config.validate()
        if errors:
            raise ValueError(f"Invalid indexing config: {', '.join(errors)}")

        with self._lock:
            self._configs["indexing"] = config
            self._last_updated["indexing"] = datetime.now()
            logger.info(
                f"Indexing config updated: enabled={config.enabled}, batch_size={config.batch_size}"
            )

    # ========== Unified Configuration ==========

    def get_all_configs(self, include_secrets: bool = False) -> dict[str, Any]:
        """
        Get all configurations as dictionary.

        Args:
            include_secrets: Whether to include API keys and passwords

        Returns:
            Dictionary with all configurations
        """
        with self._lock:
            return {
                "llm": {
                    role: config.to_dict(include_api_key=include_secrets)
                    for role, config in self._configs["llm"].items()
                },
                "rag": asdict(self._configs["rag"]),
                "cache": self._configs["cache"].to_dict(include_password=include_secrets),
                "safety": asdict(self._configs["safety"]),
                "rate_limit": asdict(self._configs["rate_limit"]),
                "monitoring": asdict(self._configs["monitoring"]),
                "indexing": asdict(self._configs["indexing"]),
                "last_updated": {k: v.isoformat() for k, v in self._last_updated.items()},
            }

    def export_config_json(self, include_secrets: bool = False) -> str:
        """
        Export all configurations as JSON string.

        Args:
            include_secrets: Whether to include API keys and passwords

        Returns:
            JSON string with all configurations
        """
        return json.dumps(self.get_all_configs(include_secrets=include_secrets), indent=2)

    # ========== Filtering Configuration ==========

    def get_filtering_config(self) -> FilteringConfig:
        """
        Get filtering configuration.

        Returns:
            Current filtering configuration
        """
        with self._lock:
            config = self._configs.get("filtering")
            if config is None:
                config = FilteringConfig()
                self._configs["filtering"] = config
            return config

    def update_filtering_config(self, config: FilteringConfig) -> None:
        """
        Update filtering configuration.

        Args:
            config: New filtering configuration

        Raises:
            ValueError: If configuration is invalid
        """
        errors = config.validate()
        if errors:
            raise ValueError(f"Invalid filtering config: {', '.join(errors)}")

        with self._lock:
            self._configs["filtering"] = config
            self._last_updated["filtering"] = datetime.now()
            logger.info("Filtering config updated with new default filtering options")

    # ========== Global Config Management ==========

    def get_config_summary(self) -> dict[str, Any]:
        """
        Get high-level configuration summary.

        Returns:
            Summary dictionary with key configuration status
        """
        with self._lock:
            llm_configs = self._configs["llm"]
            rag_config = self._configs["rag"]
            cache_config = self._configs["cache"]
            safety_config = self._configs["safety"]
            rate_limit_config = self._configs["rate_limit"]
            monitoring_config = self._configs["monitoring"]
            indexing_config = self._configs["indexing"]

            return {
                "llm": {
                    "roles_configured": list(llm_configs.keys()),
                    "main_model": llm_configs.get("main").model if "main" in llm_configs else None,
                    "safety_configured": "safety" in llm_configs,
                    "scoring_configured": "scoring" in llm_configs,
                },
                "rag": {
                    "threshold": rag_config.threshold,
                    "rerank_enabled": rag_config.rerank_enabled,
                },
                "cache": {
                    "backend": cache_config.backend,
                    "ttl": cache_config.ttl,
                },
                "safety": {
                    "mode": safety_config.mode,
                    "stream_guard_mode": safety_config.stream_guard_mode,
                },
                "rate_limit": {
                    "enabled": rate_limit_config.enabled,
                    "query_limit": rate_limit_config.query_limit,
                },
                "monitoring": {
                    "prometheus": monitoring_config.prometheus_enabled,
                    "otel": monitoring_config.otel_enabled,
                    "mlflow": monitoring_config.mlflow_enabled,
                    "wandb": monitoring_config.wandb_enabled,
                },
                "indexing": {
                    "enabled": indexing_config.enabled,
                    "batch_size": indexing_config.batch_size,
                },
                "total_configs": len([k for k in self._configs if self._configs[k]]),
                "last_update": (
                    max(self._last_updated.values()).isoformat() if self._last_updated else None
                ),
            }

    def reset_to_defaults(self, category: str | None = None) -> dict[str, Any]:
        """
        Reset configuration to default values from environment settings.

        Args:
            category: Specific category to reset (llm, rag, cache, safety, rate_limit,
                     monitoring, indexing, filtering) or None to reset all

        Returns:
            Dictionary with reset categories and their new values

        Raises:
            ValueError: If category is invalid
        """
        valid_categories = {
            "llm",
            "rag",
            "cache",
            "safety",
            "rate_limit",
            "monitoring",
            "indexing",
            "filtering",
        }

        if category is not None and category not in valid_categories:
            raise ValueError(
                f"Invalid category: {category}. Must be one of {valid_categories} or None for all."
            )

        with self._lock:
            reset_results = {}

            # Determine which categories to reset
            categories_to_reset = [category] if category else list(valid_categories)

            for cat in categories_to_reset:
                if cat == "llm":
                    # Reset LLM configs from settings
                    self._configs["llm"]["main"] = LLMConfig(
                        model=settings.MAIN_LLM_MODEL or "",
                        api_key=settings.MAIN_LLM_API_KEY or "",
                        api_base=settings.MAIN_LLM_API_BASE or "https://openrouter.ai/api/v1",
                        temperature=settings.MAIN_LLM_TEMPERATURE,
                        max_tokens=settings.MAIN_LLM_MAX_TOKENS,
                    )

                    if settings.SAFETY_LLM_MODEL:
                        self._configs["llm"]["safety"] = LLMConfig(
                            model=settings.SAFETY_LLM_MODEL,
                            api_key=settings.SAFETY_LLM_API_KEY or "",
                            api_base=settings.SAFETY_LLM_API_BASE or "",
                            temperature=settings.SAFETY_LLM_TEMPERATURE,
                            max_tokens=settings.SAFETY_LLM_MAX_TOKENS,
                        )
                    else:
                        self._configs["llm"].pop("safety", None)

                    if settings.SCORING_LLM_MODEL:
                        self._configs["llm"]["scoring"] = LLMConfig(
                            model=settings.SCORING_LLM_MODEL,
                            api_key=settings.SCORING_LLM_API_KEY or "",
                            api_base=settings.SCORING_LLM_API_BASE or "",
                            temperature=settings.SCORING_LLM_TEMPERATURE,
                            max_tokens=settings.SCORING_LLM_MAX_TOKENS,
                        )
                    else:
                        self._configs["llm"].pop("scoring", None)

                    reset_results["llm"] = {
                        role: config.to_dict(include_api_key=False)
                        for role, config in self._configs["llm"].items()
                    }

                elif cat == "rag":
                    self._configs["rag"] = RAGConfig(
                        threshold=settings.RAG_THRESHOLD,
                        rerank_enabled=settings.RERANK_ENABLED,
                        rerank_candidate_count=settings.RERANK_CANDIDATE_COUNT,
                        rerank_model_name=settings.RERANK_MODEL_NAME,
                        rerank_score_threshold=settings.RERANK_SCORE_THRESHOLD,
                        rerank_max_length=settings.RERANK_MAX_LENGTH,
                    )
                    reset_results["rag"] = asdict(self._configs["rag"])

                elif cat == "cache":
                    self._configs["cache"] = CacheConfig(
                        ttl=settings.CACHE_TTL,
                        backend=settings.CACHE_BACKEND,  # type: ignore[arg-type]
                        redis_url=settings.REDIS_URL,
                        redis_host=settings.REDIS_HOST,
                        redis_port=settings.REDIS_PORT,
                        redis_db=settings.REDIS_DB,
                        redis_username=settings.REDIS_USERNAME,
                        redis_password=settings.REDIS_PASSWORD,
                    )
                    reset_results["cache"] = self._configs["cache"].to_dict(include_password=False)

                elif cat == "safety":
                    self._configs["safety"] = SafetyConfig(
                        mode=settings.SAFETY_MODE,  # type: ignore[arg-type]
                        stream_guard_mode=settings.STREAM_GUARD_MODE,  # type: ignore[arg-type]
                    )
                    reset_results["safety"] = asdict(self._configs["safety"])

                elif cat == "rate_limit":
                    self._configs["rate_limit"] = RateLimitConfig(
                        enabled=settings.RATE_LIMIT_ENABLED,
                        default_limit=settings.RATE_LIMIT_DEFAULT,
                        query_limit=settings.RATE_LIMIT_QUERY,
                        upload_limit=settings.RATE_LIMIT_UPLOAD,
                        admin_limit=settings.RATE_LIMIT_ADMIN,
                        redis_url=settings.REDIS_URL,
                    )
                    reset_results["rate_limit"] = asdict(self._configs["rate_limit"])

                elif cat == "monitoring":
                    self._configs["monitoring"] = MonitoringConfig(
                        prometheus_enabled=settings.PROMETHEUS_ENABLED,
                        prometheus_route=settings.PROMETHEUS_ROUTE,
                        otel_enabled=settings.OTEL_ENABLED,
                        otel_service_name=settings.OTEL_SERVICE_NAME,
                        otel_endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
                        mlflow_enabled=settings.ENABLE_MLFLOW,
                        mlflow_tracking_uri=settings.MLFLOW_TRACKING_URI,
                        mlflow_experiment_name=settings.MLFLOW_EXPERIMENT_NAME,
                        wandb_enabled=settings.ENABLE_WANDB,
                        wandb_project=settings.WANDB_PROJECT,
                    )
                    reset_results["monitoring"] = asdict(self._configs["monitoring"])

                elif cat == "indexing":
                    self._configs["indexing"] = IndexingConfig(
                        enabled=True,
                        batch_size=100,
                        auto_reindex_on_startup=False,
                        index_documents=True,
                        index_rules=True,
                    )
                    reset_results["indexing"] = asdict(self._configs["indexing"])

                elif cat == "filtering":
                    self._configs["filtering"] = FilteringConfig()
                    reset_results["filtering"] = {
                        "default_input_filtering": self._configs[
                            "filtering"
                        ].default_input_filtering,
                        "default_output_filtering": self._configs[
                            "filtering"
                        ].default_output_filtering,
                    }

                # Update last_updated timestamp
                self._last_updated[cat] = datetime.now()

            logger.info(
                "Configuration reset to defaults for categories: %s",
                ", ".join(categories_to_reset),
            )

            return {
                "reset_categories": categories_to_reset,
                "configurations": reset_results,
                "timestamp": datetime.now().isoformat(),
            }


# Global singleton instance
_global_config_manager: ConfigurationManager | None = None


def get_config_manager() -> ConfigurationManager:
    """
    Get the global configuration manager instance.

    Returns:
        Global ConfigurationManager instance
    """
    global _global_config_manager
    if _global_config_manager is None:
        _global_config_manager = ConfigurationManager()
    return _global_config_manager


def reset_config_manager() -> None:
    """Reset the global configuration manager (mainly for testing)."""
    global _global_config_manager
    _global_config_manager = None
