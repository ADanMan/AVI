"""
Plugin interface for custom safety models.

This module provides an abstraction layer for integrating custom safety models
into the AVI system. Users can implement their own safety models by extending
the SafetyModelPlugin base class.

Supported model types:
- OpenAI Moderation API
- Meta Llama Guard 2/3
- NVIDIA Nemotron Guard
- Custom transformer models (HuggingFace)
- External API services
- Local ML models (CPU/GPU)

Example usage:
    >>> from src.services.safety_plugin import SafetyPluginLoader
    >>> plugin = SafetyPluginLoader.load_plugin(
    ...     "plugins.llama_guard.LlamaGuardPlugin",
    ...     config={"model": "meta-llama/LlamaGuard-7b", "device": "cuda"}
    ... )
    >>> result = await plugin.check_safety("Test message")
    >>> print(f"Safe: {result.is_safe}, Categories: {result.categories}")
"""

from __future__ import annotations

import importlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from src.utils.logger import logger


@dataclass
class SafetyResult:
    """
    Result from safety model check.

    Attributes:
        is_safe: Whether the text is considered safe
        confidence: Confidence score from 0.0 to 1.0
        categories: List of flagged categories (e.g., ["violence", "hate"])
        explanation: Human-readable explanation of the decision
        sanitized_text: Optional sanitized/filtered version of the text
        metadata: Additional metadata from the safety check
    """

    is_safe: bool
    confidence: float  # 0.0-1.0
    categories: list[str] = field(default_factory=list)
    explanation: str = ""
    sanitized_text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate confidence score."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")


class SafetyModelPlugin(ABC):
    """
    Abstract base class for custom safety model plugins.

    Implement this interface to integrate your own safety model into AVI.
    The plugin will be called for every content filtering operation.

    Example:
        ```python
        class MySafetyPlugin(SafetyModelPlugin):
            def __init__(self, api_key: str, threshold: float = 0.8):
                self.api_key = api_key
                self.threshold = threshold

            async def check_safety(self, text: str, context: str | None = None) -> SafetyResult:
                # Your safety check logic here
                result = await my_api.check(text)
                return SafetyResult(
                    is_safe=result.score < self.threshold,
                    confidence=result.score,
                    categories=result.categories,
                    explanation=result.reason
                )

            async def check_health(self) -> bool:
                try:
                    await my_api.ping()
                    return True
                except:
                    return False

            @property
            def model_name(self) -> str:
                return "my-custom-model-v1"
        ```
    """

    @abstractmethod
    async def check_safety(self, text: str, context: str | None = None) -> SafetyResult:
        """
        Check if text is safe according to the model's criteria.

        This is the main method that will be called for every content check.
        Implement your safety logic here.

        Args:
            text: Text to check for safety
            context: Optional context for the check (e.g., conversation history)

        Returns:
            SafetyResult with is_safe flag, confidence score, categories, etc.

        Raises:
            Exception: If the safety check fails (will be caught by the system)

        Example:
            >>> result = await plugin.check_safety("Hello, how are you?")
            >>> if not result.is_safe:
            ...     print(f"Unsafe content: {result.categories}")
        """

    @abstractmethod
    async def check_health(self) -> bool:
        """
        Health check for the model.

        Called periodically to ensure the model is operational.
        Should return quickly (< 1 second).

        Returns:
            True if the model is healthy and operational, False otherwise

        Example:
            >>> is_healthy = await plugin.check_health()
            >>> if not is_healthy:
            ...     logger.error("Safety model is down!")
        """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """
        Return name/identifier of the safety model.

        Used for logging and monitoring.

        Returns:
            String identifier for the model (e.g., "llama-guard-2", "openai-moderation")

        Example:
            >>> print(plugin.model_name)
            "llama-guard-2"
        """


class SafetyPluginLoader:
    """
    Load and manage safety model plugins.

    This class handles dynamic loading of custom safety plugins from Python modules.
    Plugins are loaded once and cached for reuse.
    """

    _plugin_cache: dict[str, SafetyModelPlugin] = {}

    @classmethod
    def load_plugin(
        cls, plugin_path: str, config: dict[str, Any] | None = None, cache: bool = True
    ) -> SafetyModelPlugin:
        """
        Load custom safety plugin from module path.

        The plugin_path should be a Python import path in the format:
        "module.submodule.ClassName"

        Args:
            plugin_path: Python import path (e.g., "plugins.my_safety.MySafetyModel")
            config: Optional configuration dict passed to plugin constructor
            cache: Whether to cache the plugin instance (default: True)

        Returns:
            Instantiated SafetyModelPlugin

        Raises:
            ImportError: If the module cannot be imported
            AttributeError: If the class doesn't exist in the module
            TypeError: If the class doesn't inherit from SafetyModelPlugin
            Exception: If plugin initialization fails

        Example:
            >>> plugin = SafetyPluginLoader.load_plugin(
            ...     "plugins.llama_guard.LlamaGuardPlugin",
            ...     config={"model": "llama-guard-2", "device": "cuda"}
            ... )
            >>> result = await plugin.check_safety("test")
        """
        # Check cache first
        if cache and plugin_path in cls._plugin_cache:
            logger.debug(f"Using cached safety plugin: {plugin_path}")
            return cls._plugin_cache[plugin_path]

        logger.info(f"Loading safety plugin from: {plugin_path}")

        try:
            # Parse module and class name
            if "." not in plugin_path:
                raise ValueError(
                    f"Invalid plugin path: {plugin_path}. "
                    "Expected format: 'module.submodule.ClassName'"
                )

            module_path, class_name = plugin_path.rsplit(".", 1)

            # Import module
            try:
                module = importlib.import_module(module_path)
            except ImportError as e:
                raise ImportError(
                    f"Could not import module '{module_path}'. "
                    f"Make sure the plugin is installed and accessible. Error: {e}"
                ) from e

            # Get class from module
            if not hasattr(module, class_name):
                raise AttributeError(
                    f"Module '{module_path}' has no class '{class_name}'. "
                    f"Available: {dir(module)}"
                )

            plugin_class = getattr(module, class_name)

            # Verify it's a SafetyModelPlugin subclass
            if not issubclass(plugin_class, SafetyModelPlugin):
                raise TypeError(
                    f"Class '{class_name}' must inherit from SafetyModelPlugin. "
                    f"Got: {plugin_class.__bases__}"
                )

            # Instantiate plugin
            config = config or {}
            try:
                plugin = plugin_class(**config)
            except Exception as e:
                raise Exception(
                    f"Failed to initialize plugin '{class_name}' with config {config}. "
                    f"Error: {e}"
                ) from e

            # Cache if requested
            if cache:
                cls._plugin_cache[plugin_path] = plugin

            logger.info(f"Successfully loaded safety plugin: {plugin.model_name}")
            return plugin

        except Exception as e:
            logger.error(f"Failed to load safety plugin '{plugin_path}': {e}")
            raise

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the plugin cache."""
        cls._plugin_cache.clear()
        logger.debug("Safety plugin cache cleared")

    @classmethod
    def list_cached_plugins(cls) -> list[str]:
        """
        Get list of cached plugin paths.

        Returns:
            List of plugin paths currently in cache
        """
        return list(cls._plugin_cache.keys())


__all__ = [
    "SafetyModelPlugin",
    "SafetyPluginLoader",
    "SafetyResult",
]
