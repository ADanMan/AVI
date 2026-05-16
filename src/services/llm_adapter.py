from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

from config.settings import settings
from src.utils.logger import logger


class _AdapterBase:
    """Base interface implemented by all adapter backends."""

    kind: str
    name: str

    async def generate_response(self, query: str, context: str | None = None, **kwargs: Any) -> str:
        raise NotImplementedError

    async def generate_streaming_response(
        self, query: str, context: str | None = None, **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        raise NotImplementedError

    async def check_connection(self) -> bool:
        raise NotImplementedError


@dataclass
class _LLMDefaults:
    api_key: str = ""
    base_url: str | None = None
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 2000
    top_p: float = 1.0
    system_prompt: str | None = None
    context_template: str = "Use this context for answering: {context}"
    mock_prefix: str = "mocked llm"


class _OpenAIProvider(_AdapterBase):
    """Adapter that talks to OpenAI-compatible chat completion endpoints."""

    def __init__(
        self,
        *,
        defaults: _LLMDefaults,
        llm_parameters: dict[str, Any] | None = None,
        client: Any = None,
        role_name: str,
    ) -> None:
        self.kind = role_name
        self.name = role_name
        self._mock_mode = os.environ.get("AVI_TEST_MODE") == "1"
        self._defaults = defaults
        self.temperature = (llm_parameters or {}).get("temperature") or defaults.temperature
        self.max_tokens = (llm_parameters or {}).get("max_tokens") or defaults.max_tokens
        self.top_p = (llm_parameters or {}).get("top_p", defaults.top_p)
        self.model = (llm_parameters or {}).get("model", defaults.model)
        self.system_prompt = (llm_parameters or {}).get("system_prompt", defaults.system_prompt)
        self.context_template = (llm_parameters or {}).get(
            "context_template", defaults.context_template
        )
        self.mock_prefix = (llm_parameters or {}).get("mock_prefix", defaults.mock_prefix)
        self._extra_params = {
            k: v
            for k, v in (llm_parameters or {}).items()
            if k
            not in {
                "temperature",
                "max_tokens",
                "top_p",
                "system_prompt",
                "context_template",
                "mock_prefix",
                "model",
            }
        }

        if client is not None:
            self.client = client
            self._mock_mode = False
            logger.debug("LLMAdapter using injected client for role '%s'", role_name)
            return

        api_key = (defaults.api_key or "").strip()
        base_url = (defaults.base_url or "").strip() or None

        # Production environment must not use mock mode
        if settings.is_production_environment() and self._mock_mode:
            raise RuntimeError(
                f"Mock mode (AVI_TEST_MODE=1) is enabled in production environment for role '{role_name}'. "
                "This is not allowed. Disable AVI_TEST_MODE in production."
            )

        if not api_key:
            # Production environment must have valid API keys
            if settings.is_production_environment():
                field_name_map = {
                    "openrouter": "MAIN_LLM_API_KEY",
                    "external": "MAIN_LLM_API_KEY",
                    "main": "MAIN_LLM_API_KEY",
                    "default": "MAIN_LLM_API_KEY",
                    "safety": "SAFETY_LLM_API_KEY",
                    "scoring": "SCORING_LLM_API_KEY",
                }
                field_name = field_name_map.get(role_name, "MAIN_LLM_API_KEY")
                raise RuntimeError(
                    f"{field_name} is not configured for production environment. "
                    f"API keys are required in production for role '{role_name}'."
                )

            # Development/test environments can use mock mode
            if self._mock_mode or settings.allows_missing_api_keys():
                if not self._mock_mode:
                    logger.info(
                        "LLMAdapter using mock mode for role '%s' in %s environment.",
                        role_name,
                        settings.get_runtime_environment(),
                    )
                    self._mock_mode = True
                self.client = None
                return

            # Non-production with missing keys but not allowing mock mode
            field_name_map = {
                "openrouter": "MAIN_LLM_API_KEY",
                "external": "MAIN_LLM_API_KEY",
                "main": "MAIN_LLM_API_KEY",
                "default": "MAIN_LLM_API_KEY",
                "safety": "SAFETY_LLM_API_KEY",
                "scoring": "SCORING_LLM_API_KEY",
            }
            field_name = field_name_map.get(role_name, "MAIN_LLM_API_KEY")
            raise RuntimeError(
                f"{field_name} is not configured. Set credentials or enable AVI_TEST_MODE."
            )

        try:  # pragma: no cover - import guarded for optional dependency
            from openai import AsyncOpenAI  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "openai package is required to use the configured LLM provider"
            ) from exc

        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        logger.info(
            "LLMAdapter configured OpenAI-compatible client for role '%s' with model '%s'",
            role_name,
            self.model,
        )

    async def generate_response(self, query: str, context: str | None = None, **kwargs: Any) -> str:
        if self._mock_mode:
            return self._mock_response(query, context)

        if not getattr(self, "client", None):
            raise RuntimeError(f"LLM client is not configured for role '{self.kind}'")

        messages = self._build_messages(query, context)
        params = self._prepare_parameters(kwargs)

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=params.pop("temperature"),
            max_tokens=params.pop("max_tokens"),
            **params,
        )

        # Validate response has required fields
        if not response.choices:
            raise ValueError("LLM returned empty response (no choices)")

        message = response.choices[0].message
        if not message or not message.content:
            raise ValueError("LLM returned empty message content")

        return message.content.strip()

    async def generate_streaming_response(
        self, query: str, context: str | None = None, **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        if self._mock_mode:
            yield self._mock_response(query, context)
            return

        if not getattr(self, "client", None):
            raise RuntimeError("LLM client is not configured for streaming use")

        messages = self._build_messages(query, context)
        params = self._prepare_parameters(kwargs)
        params.setdefault("stream", True)

        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=params.pop("temperature"),
            max_tokens=params.pop("max_tokens"),
            **params,
        )

        async for chunk in stream:
            for choice in getattr(chunk, "choices", []):
                delta = getattr(choice, "delta", None)
                content = getattr(delta, "content", None) if delta else None
                if content:
                    yield content

    async def check_connection(self) -> bool:
        if self._mock_mode:
            return True

        if not getattr(self, "client", None):
            return False

        try:
            await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
                temperature=self.temperature,
            )
            return True
        except Exception as exc:  # pragma: no cover - network error path
            logger.error("LLMAdapter health-check failed for role '%s': %s", self.kind, exc)
            return False

    def _build_messages(self, query: str, context: str | None) -> list:
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        if context:
            context_message = self.context_template.format(context=context)
            messages.append({"role": "system", "content": context_message})
        messages.append({"role": "user", "content": query})
        return messages

    def _prepare_parameters(self, overrides: dict[str, Any]) -> dict[str, Any]:
        params: dict[str, Any] = {
            "temperature": overrides.get("temperature", self.temperature),
            "max_tokens": overrides.get("max_tokens", self.max_tokens),
            "top_p": overrides.get("top_p", self.top_p),
        }

        combined = dict(self._extra_params)
        combined.update({k: v for k, v in overrides.items() if k not in params})
        params.update(combined)
        return params

    def _mock_response(self, query: str, context: str | None) -> str:
        prefix = f"[{self.mock_prefix}]"
        if context:
            return f"{prefix} Context: {context} | Query: {query}"
        return f"{prefix} Query: {query}"


class _LocalSafetyProvider(_AdapterBase):
    """Adapter that uses the local safety microservice."""

    def __init__(self, *, client: Any | None = None) -> None:
        from src.services.safety_client import SafetyServiceClient

        service_url = settings.SAFETY_SERVICE_URL or settings.SAFETY_LOCAL_API_URL
        timeout = settings.SAFETY_SERVICE_TIMEOUT or settings.SAFETY_LOCAL_TIMEOUT
        if client is None:
            if not service_url:
                raise ValueError("Local safety microservice endpoint is not configured.")
            client = SafetyServiceClient(service_url, timeout=timeout)

        self.client = client
        self.kind = "local_safety"
        self.name = "local_safety"

    async def generate_response(self, query: str, context: str | None = None, **_: Any) -> str:
        from src.services.safety_client import SafetyServiceError

        try:
            result = await self.client.check_text(query, context=context)
        except SafetyServiceError as exc:
            logger.error("Local safety service failed: %s", exc)
            raise
        return result.sanitized_text or query

    async def generate_streaming_response(
        self, query: str, context: str | None = None, **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        yield await self.generate_response(query, context=context, **kwargs)

    async def check_connection(self) -> bool:
        from src.services.safety_client import SafetyServiceError

        try:
            return await self.client.check_health()
        except SafetyServiceError as exc:  # pragma: no cover - network path
            logger.warning("Local safety service health-check failed: %s", exc)
            return False


class _HybridProvider(_AdapterBase):
    """Adapter that fans out to primary and fallback providers."""

    def __init__(
        self,
        *,
        primary: LLMAdapter,
        fallback: LLMAdapter | None,
        primary_name: str,
        fallback_name: str,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.primary_name = primary_name
        self.fallback_name = fallback_name
        self.last_successful: str | None = None
        self.kind = "hybrid"
        self.name = "hybrid"

    async def generate_response(self, query: str, context: str | None = None, **kwargs: Any) -> str:
        try:
            result = await self.primary.generate_response(query, context=context, **kwargs)
            self.last_successful = self.primary_name
            return result
        except Exception as primary_error:
            logger.warning(
                "Primary safety adapter '%s' failed: %s",
                self.primary_name,
                primary_error,
            )
            if not self.fallback:
                raise
            result = await self.fallback.generate_response(query, context=context, **kwargs)
            self.last_successful = self.fallback_name
            return result

    async def generate_streaming_response(
        self, query: str, context: str | None = None, **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        try:
            async for chunk in self.primary.generate_streaming_response(
                query, context=context, **kwargs
            ):
                yield chunk
            self.last_successful = self.primary_name
            return
        except Exception as primary_error:
            logger.warning(
                "Primary safety adapter '%s' streaming failed: %s",
                self.primary_name,
                primary_error,
            )
            if not self.fallback:
                raise
        async for chunk in self.fallback.generate_streaming_response(
            query, context=context, **kwargs
        ):
            yield chunk
        self.last_successful = self.fallback_name

    async def check_connection(self) -> bool:
        try:
            if await self.primary.check_connection():
                self.last_successful = self.primary_name
                return True
        except Exception as exc:
            logger.warning(
                "Primary safety adapter '%s' health-check failed: %s",
                self.primary_name,
                exc,
            )

        if self.fallback:
            try:
                if await self.fallback.check_connection():
                    self.last_successful = self.fallback_name
                    return True
            except Exception as exc:
                logger.warning(
                    "Fallback safety adapter '%s' health-check failed: %s",
                    self.fallback_name,
                    exc,
                )
        return False


class LLMAdapter:
    """Unified abstraction for interacting with all LLM backends used by AVI."""

    def __init__(
        self,
        *,
        role: str = "external",
        provider: str | None = None,
        config: dict[str, Any] | None = None,
        client: Any = None,
        llm_parameters: dict[str, Any] | None = None,
        model_name_override: str | None = None,
        primary_adapter: LLMAdapter | None = None,
        fallback_adapter: LLMAdapter | None = None,
        primary_name: str = "primary",
        fallback_name: str = "fallback",
    ) -> None:
        config = config or {}
        self.role = (role or "external").strip().lower()
        provider_value = provider or role
        self.provider = provider_value.strip().lower() if provider_value else ""
        self._impl: _AdapterBase

        if self.role == "hybrid":
            if primary_adapter is None:
                raise ValueError("Hybrid adapters require a primary adapter instance")
            self._impl = _HybridProvider(
                primary=primary_adapter,
                fallback=fallback_adapter,
                primary_name=primary_name,
                fallback_name=fallback_name,
            )
        elif self.role == "local_safety":
            self._impl = _LocalSafetyProvider(client=client)
        else:
            defaults = self._build_defaults(
                role=self.role,
                provider=self.provider or None,
                config=config,
                model_name_override=model_name_override,
            )
            self._impl = _OpenAIProvider(
                defaults=defaults,
                llm_parameters=llm_parameters,
                client=client,
                role_name=self.role,
            )

    async def generate_response(self, query: str, context: str | None = None, **kwargs: Any) -> str:
        return await self._impl.generate_response(query, context=context, **kwargs)

    async def generate_streaming_response(
        self, query: str, context: str | None = None, **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        async for chunk in self._impl.generate_streaming_response(query, context=context, **kwargs):
            yield chunk

    async def check_connection(self) -> bool:
        return await self._impl.check_connection()

    @property
    def kind(self) -> str:
        return getattr(self._impl, "kind", self.role)

    @property
    def last_successful(self) -> str | None:
        return getattr(self._impl, "last_successful", None)

    def get_config(self) -> dict:
        if isinstance(self._impl, _OpenAIProvider):
            return {
                "api_key": self._mask_api_key(self._impl._defaults.api_key),
                "base_url": self._impl._defaults.base_url,
                "model": self._impl.model,
                "temperature": self._impl.temperature,
                "max_tokens": self._impl.max_tokens,
            }
        return {"kind": self.kind}

    def _mask_api_key(self, api_key: str) -> str:
        if not api_key:
            return ""
        if len(api_key) <= 8:
            return "****"
        return f"{api_key[:4]}...{api_key[-4:]}"

    def _build_defaults(
        self,
        *,
        role: str,
        provider: str | None,
        config: dict[str, Any],
        model_name_override: str | None,
    ) -> _LLMDefaults:
        role = (role or "main").lower()
        provider = (provider or "").lower()
        if role == "safety":
            system_prompt = config.get(
                "system_prompt",
                (
                    "You are a content safety assistant.\n"
                    "Your task is to check and, if necessary, rephrase the text\n"
                    "to make it safe and ethical, while preserving the main meaning.\n\n"
                    "If the text contains unacceptable content:\n"
                    "1. Identify the problematic areas\n"
                    "2. Suggest a safe alternative\n"
                    "3. Ensure that the main meaning is preserved\n\n"
                    "Return only the rephrased text without additional comments."
                ),
            )
            return _LLMDefaults(
                api_key=config.get("api_key", settings.SAFETY_LLM_API_KEY),
                base_url=config.get("base_url", settings.SAFETY_LLM_API_BASE or None),
                model=config.get("model", settings.SAFETY_LLM_MODEL),
                temperature=config.get("temperature", settings.SAFETY_LLM_TEMPERATURE),
                max_tokens=config.get("max_tokens", settings.SAFETY_LLM_MAX_TOKENS),
                top_p=config.get("top_p", 1.0),
                system_prompt=system_prompt,
                context_template=config.get(
                    "context_template", "Consider the following context:\n{context}"
                ),
                mock_prefix=config.get("mock_prefix", "mocked safety llm"),
            )

        target = provider or role

        if target == "openrouter":
            model_name = model_name_override or config.get("model")
            return _LLMDefaults(
                api_key=config.get("api_key", settings.MAIN_LLM_API_KEY),
                base_url=config.get("base_url", settings.MAIN_LLM_API_BASE or None),
                model=model_name or settings.MAIN_LLM_MODEL,
                temperature=config.get("temperature", settings.MAIN_LLM_TEMPERATURE),
                max_tokens=config.get("max_tokens", settings.MAIN_LLM_MAX_TOKENS),
                top_p=config.get("top_p", 1.0),
                mock_prefix=config.get("mock_prefix", "mocked openrouter llm"),
            )

        if target in {"external", "main", "default", ""}:
            return _LLMDefaults(
                api_key=config.get("api_key", settings.MAIN_LLM_API_KEY),
                base_url=config.get("base_url", settings.MAIN_LLM_API_BASE or None),
                model=model_name_override or config.get("model", settings.MAIN_LLM_MODEL),
                temperature=config.get("temperature", settings.MAIN_LLM_TEMPERATURE),
                max_tokens=config.get("max_tokens", settings.MAIN_LLM_MAX_TOKENS),
                top_p=config.get("top_p", 1.0),
                system_prompt=config.get("system_prompt"),
                context_template=config.get(
                    "context_template", "Use this context for answering: {context}"
                ),
                mock_prefix=config.get("mock_prefix", "mocked external llm"),
            )

        # Fallback to using main LLM defaults for unknown providers
        return _LLMDefaults(
            api_key=config.get("api_key", settings.MAIN_LLM_API_KEY),
            base_url=config.get("base_url", settings.MAIN_LLM_API_BASE or None),
            model=model_name_override or config.get("model", settings.MAIN_LLM_MODEL),
            temperature=config.get("temperature", settings.MAIN_LLM_TEMPERATURE),
            max_tokens=config.get("max_tokens", settings.MAIN_LLM_MAX_TOKENS),
            top_p=config.get("top_p", 1.0),
            system_prompt=config.get("system_prompt"),
            context_template=config.get(
                "context_template", "Use this context for answering: {context}"
            ),
            mock_prefix=config.get("mock_prefix", "mocked external llm"),
        )

    def __getattr__(self, item: str) -> Any:
        if hasattr(self._impl, item):
            return getattr(self._impl, item)
        raise AttributeError(item)


__all__ = ["LLMAdapter"]
