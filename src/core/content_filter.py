# src/core/content_filter.py
import asyncio
import time
from enum import Enum

from config.settings import settings
from src.models.schemas import FilterResult
from src.monitoring.metrics import content_filter_metrics
from src.monitoring.observability import record_safety_intervention
from src.services.llm_adapter import LLMAdapter
from src.services.vector_db import VectorDBClient, VectorDBService
from src.utils.logger import logger


class SafetyMode(str, Enum):
    """Enumerates available safety filtering backends."""

    EXTERNAL = "external"
    LOCAL = "local"
    HYBRID = "hybrid"
    DISABLED = "disabled"


class ContentFilterService:
    """
    Content filtering service based on vector search for similar rules.
    Allows checking and modifying texts according to specified rules.
    This version focuses on the core AVI architecture: rule-based filtering and modification.
    """

    def __init__(
        self,
        vector_db: VectorDBClient | None = None,
        safety_llm: LLMAdapter | None = None,
        mode: SafetyMode | str | None = None,
        default_threshold: float | None = None,
    ):
        """
        Initializes the content filter service.

        Args:
            vector_db (Optional[VectorDBClient]): Vector DB implementation for rule matching.
            safety_llm (Optional[LLMAdapter]): Adapter used for safety rephrasing when enabled.
            default_threshold (Optional[float]): Default relevance threshold for filter rule activation.
                If None, uses settings.FILTER_DEFAULT_THRESHOLD.
        """
        self.vector_db = vector_db or VectorDBService()
        self.requested_mode = self._resolve_mode(mode)
        self.safety_llm = self._initialize_safety_adapter(safety_llm)
        self._active_mode = self._infer_active_mode()
        # Use settings default if not provided
        if default_threshold is None:
            from config.settings import settings

            default_threshold = settings.FILTER_DEFAULT_THRESHOLD
        self.default_threshold = default_threshold
        logger.info(
            "ContentFilterService initialized with threshold {} and safety mode '{}'",
            default_threshold,
            self._active_mode.value,
        )

    @property
    def safety_llm_enabled(self) -> bool:
        """Return True when the safety LLM is available."""
        return self._active_mode is not SafetyMode.DISABLED

    @property
    def active_mode(self) -> SafetyMode:
        """Return the effective safety mode currently in use."""
        return self._active_mode

    def _resolve_mode(self, mode: SafetyMode | str | None) -> SafetyMode:
        if isinstance(mode, SafetyMode):
            return mode
        if isinstance(mode, str) and mode.strip():
            candidate = mode.strip().lower()
        else:
            candidate = settings.get_safety_mode()
        try:
            return SafetyMode(candidate)
        except ValueError:
            logger.warning(
                "Unknown safety mode '{}'. Falling back to 'disabled'.",
                candidate,
            )
            return SafetyMode.DISABLED

    def _initialize_safety_adapter(self, safety_llm: LLMAdapter | None) -> LLMAdapter | None:
        if safety_llm is not None:
            return safety_llm

        mode = self.requested_mode
        if mode is SafetyMode.DISABLED:
            logger.info(
                "Safety mode disabled. ContentFilterService will operate in vector-only mode."
            )
            return None

        if mode is SafetyMode.EXTERNAL:
            if not settings.is_safety_llm_configured():
                logger.warning("External safety mode requested but credentials are missing.")
                return None
            try:
                return LLMAdapter(role="safety")
            except Exception as init_error:
                logger.error("Failed to initialize safety LLM adapter: {}", init_error)
                return None

        if mode is SafetyMode.LOCAL:
            try:
                return LLMAdapter(role="local_safety")
            except Exception as init_error:
                logger.error("Failed to initialize local safety adapter: {}", init_error)
                return None

        if mode is SafetyMode.HYBRID:
            local_adapter: LLMAdapter | None = None
            external_adapter: LLMAdapter | None = None

            try:
                local_adapter = LLMAdapter(role="local_safety")
            except Exception as local_error:
                logger.warning("Hybrid mode: local safety adapter unavailable: {}", local_error)

            if settings.is_safety_llm_configured():
                try:
                    external_adapter = LLMAdapter(role="safety")
                except Exception as external_error:
                    logger.warning(
                        "Hybrid mode: external safety adapter unavailable: {}",
                        external_error,
                    )
            else:
                logger.warning("Hybrid mode requested but external safety credentials are missing.")

            if local_adapter and external_adapter:
                return LLMAdapter(
                    role="hybrid",
                    primary_adapter=local_adapter,
                    fallback_adapter=external_adapter,
                    primary_name=SafetyMode.LOCAL.value,
                    fallback_name=SafetyMode.EXTERNAL.value,
                )
            if local_adapter:
                logger.warning("Hybrid mode degraded to local safety adapter only.")
                return local_adapter
            if external_adapter:
                logger.warning("Hybrid mode degraded to external safety adapter only.")
                return external_adapter

            logger.error("Hybrid mode requested but no safety adapters are available.")
            return None

        return None

    def _infer_active_mode(self) -> SafetyMode:
        if self.safety_llm is None:
            return SafetyMode.DISABLED
        if self.safety_llm.kind == "hybrid":
            last = self.safety_llm.last_successful
            if last == SafetyMode.LOCAL.value:
                return SafetyMode.LOCAL
            if last == SafetyMode.EXTERNAL.value:
                return SafetyMode.EXTERNAL
            return SafetyMode.HYBRID
        if self.safety_llm.kind == "local_safety":
            return SafetyMode.LOCAL
        return SafetyMode.EXTERNAL

    def _refresh_active_mode(self) -> None:
        self._active_mode = self._infer_active_mode()

    async def check_content(
        self,
        text: str,
        use_llm: bool = False,
        use_linked_docs: bool = True,
        is_input: bool = True,
        context: str | None = None,
        ground_truth: bool | None = None,
        # New granular control flags
        enable_vector_rules: bool = True,
        enable_prompt_modification: bool = True,
        enable_output_cleaning: bool = True,
    ) -> FilterResult:
        """
        Checks the given text for safety risks with configurable filtering components.

        Args:
            text (str): The original text to be filtered.
            use_llm (bool): Flag to indicate if LLM-based rephrasing/modification should be attempted.
            use_linked_docs (bool): Flag to indicate if linked documents were used for context.
            is_input (bool): True if the text is a user input, False if it's an LLM output.
            context (Optional[str]): Context string provided by RAGSystem, used for prompt modification.
            ground_truth (Optional[bool]): Ground truth for evaluation metrics.
            enable_vector_rules (bool): Enable vector-based rule matching. Default: True.
            enable_prompt_modification (bool): Enable prompt modification when matches found. Default: True.
            enable_output_cleaning (bool): Enable output content cleaning (OUTPUT only). Default: True.

        Returns:
            FilterResult: An object containing the original text, modified text (if any),
                          a flag indicating modification, and a list of detected FilterMatch objects.
        """
        start_time = time.perf_counter()
        detection_latency_seconds: float = 0.0
        sanitization_latency_seconds: float | None = None
        stage = "input" if is_input else "output"
        intervention_recorded = False

        # Track which components were applied
        components_applied = {
            "vector_rules": False,
            "safety_llm": False,
            "prompt_modification": False,
            "output_cleaning": False,
        }

        # Track component-level latencies for detailed metrics
        component_latencies = {
            "vector_rules": 0.0,
            "safety_llm": 0.0,
            "prompt_modification": 0.0,
            "output_cleaning": 0.0,
        }

        try:
            result = FilterResult(original_text=text, was_modified=False, matches=[])

            # --- 1. Vector Search for Filter Rules (optional) ---
            if enable_vector_rules:
                vector_rules_start = time.perf_counter()
                from config.settings import settings

                components_applied["vector_rules"] = True
                # This is the core of the filtering mechanism.
                # It finds matches with all types of rules (Toxicity, PII, Prompt Injection, Bias, Hallucination)
                # that were generated from datasets and loaded into ChromaDB.
                matches_from_rules = await self.vector_db.find_matching_rules(
                    text, n_results=settings.VECTOR_SEARCH_TOP_K
                )

                # Filter matches based on their individual relevance thresholds.
                filtered_matches = []
                for match in matches_from_rules:
                    try:
                        rule_threshold = await self.vector_db.get_rule_threshold(match.rule_text)
                        if match.relevance_score >= rule_threshold:
                            filtered_matches.append(match)
                    except Exception as thresh_error:
                        logger.error(
                            f"Error getting threshold for rule {match.rule_text}: {thresh_error!s}. Using fallback threshold ({settings.FILTER_FALLBACK_THRESHOLD})."
                        )
                        if match.relevance_score >= settings.FILTER_FALLBACK_THRESHOLD:
                            filtered_matches.append(match)

                result.matches = filtered_matches
                component_latencies["vector_rules"] = time.perf_counter() - vector_rules_start
            else:
                logger.debug("Vector rule search disabled by configuration")
                result.matches = []

            # Capture the detection latency immediately after rule matching completes.
            detection_latency_seconds = time.perf_counter() - start_time
            result.detection_latency_ms = detection_latency_seconds * 1000
            result.latency_ms = result.detection_latency_ms

            # --- 2. Modification Logic (optional) ---
            # If any rule is matched, apply the generic safe prompt modification.
            if result.matches and enable_prompt_modification:
                prompt_modification_start = time.perf_counter()
                components_applied["prompt_modification"] = True
                result.was_modified = True
                if not intervention_recorded:
                    record_safety_intervention(stage, self.active_mode.value)
                    intervention_recorded = True
                context_info = context or ""
                # Use configurable template from settings
                from config.settings import settings

                safe_prompt = settings.PROMPT_MODIFICATION_TEMPLATE.format(
                    text=text, context=context_info
                )
                result.modified_text = safe_prompt
                component_latencies["prompt_modification"] = (
                    time.perf_counter() - prompt_modification_start
                )
                logger.info(f"Content modified due to detected matches: {result.matches}")
            elif result.matches and not enable_prompt_modification:
                logger.debug("Prompt modification disabled, matches found but not applied")

            # --- 3. Safety LLM Sanitization (optional) ---
            if result.matches and use_llm and self.safety_llm:
                components_applied["safety_llm"] = True
                sanitization_start = time.perf_counter()
                llm_response = await self._try_generate_safe_text(text, context)
                sanitization_latency_seconds = time.perf_counter() - sanitization_start
                result.sanitization_latency_ms = sanitization_latency_seconds * 1000
                if llm_response:
                    result.modified_text = llm_response
                    result.was_modified = True
                    logger.info("Safety service provided a sanitized version of the content.")
            elif use_llm and not self.safety_llm:
                logger.warning("LLM-based filtering requested but safety LLM is not configured.")

            # --- 4. Output Content Cleaning (for LLM responses, optional) ---
            if not is_input and enable_output_cleaning:
                output_cleaning_start = time.perf_counter()
                components_applied["output_cleaning"] = True
                cleaned_text = self._process_output_content(text)
                component_latencies["output_cleaning"] = time.perf_counter() - output_cleaning_start
                if cleaned_text != text:
                    result.was_modified = True
                    if not intervention_recorded:
                        record_safety_intervention(stage, self.active_mode.value)
                        intervention_recorded = True
                    result.modified_text = cleaned_text
                    logger.info("Output modified due to system prompt detection.")
            elif not is_input and not enable_output_cleaning:
                logger.debug("Output content cleaning disabled by configuration")

            result.safety_mode = self.active_mode.value
            result.components_applied = components_applied

            # Convert component latencies from seconds to milliseconds
            result.component_latencies_ms = {
                component: latency * 1000
                for component, latency in component_latencies.items()
                if latency > 0
            }

            content_filter_metrics.record(
                mode=self.active_mode,
                predicted_positive=bool(result.matches),
                detection_latency_seconds=detection_latency_seconds,
                sanitization_latency_seconds=sanitization_latency_seconds,
                actual_positive=ground_truth,
            )
            # Record component-level metrics
            content_filter_metrics.record_component_usage(
                components_applied=components_applied,
                was_modified=result.was_modified,
                is_input=is_input,
            )

            # Record input/output specific metrics
            mode_str = self.active_mode.value
            if is_input:
                # Record input-specific metrics
                content_filter_metrics.record_input_filter_latency(
                    mode=mode_str,
                    component_latencies=component_latencies,
                )
                if result.matches:
                    content_filter_metrics.record_input_filter_rules_matched(
                        mode=mode_str,
                        num_rules=len(result.matches),
                    )
            else:
                # Record output-specific metrics
                content_filter_metrics.record_output_filter_latency(
                    mode=mode_str,
                    component_latencies=component_latencies,
                )
                if result.was_modified:
                    content_filter_metrics.record_output_filter_modification(mode=mode_str)

            return result
        except Exception as e:
            logger.error(f"Error checking content: {e!s}")
            logger.exception(e)
            detection_latency_seconds = time.perf_counter() - start_time
            fallback = FilterResult(original_text=text, was_modified=False, matches=[])
            fallback.safety_mode = self.active_mode.value
            fallback.detection_latency_ms = detection_latency_seconds * 1000
            fallback.latency_ms = fallback.detection_latency_ms
            fallback.components_applied = components_applied  # Include tracking even on failure

            # Convert component latencies from seconds to milliseconds (even on error)
            fallback.component_latencies_ms = {
                component: latency * 1000
                for component, latency in component_latencies.items()
                if latency > 0
            }

            content_filter_metrics.record(
                mode=self.active_mode,
                predicted_positive=False,
                detection_latency_seconds=detection_latency_seconds,
                actual_positive=ground_truth,
            )
            return fallback

    async def _try_generate_safe_text(self, text: str, context: str | None = None) -> str | None:
        try:
            response = await self.safety_llm.generate_response(text, context=context)
            self._refresh_active_mode()
            return response
        except asyncio.TimeoutError as timeout_error:
            logger.error("Safety service timed out: {}", timeout_error)
        except Exception as service_error:
            logger.error("Safety service failed: {}", service_error)
        return None

    def _contains_system_prompt(self, text: str) -> bool:
        """
        Checks if the text contains hardcoded system instructions markers.
        """
        system_markers = [
            "USER QUESTION:",
            "DONT ANSWER",
            "On output provide",
            "SYSTEM:",
            "USER:",
        ]
        return any(marker in text for marker in system_markers)

    def _process_output_content(self, text: str) -> str:
        """
        Processes the outgoing response from the LLM, cleaning it from system prompts and instructions.
        """
        try:
            if not self._contains_system_prompt(text):
                return text

            lines = text.split("\n")
            cleaned_lines = []
            skip_mode = False

            for line in lines:
                if any(
                    marker in line
                    for marker in [
                        "USER QUESTION:",
                        "DONT ANSWER",
                        "On output provide",
                        "SYSTEM:",
                        "USER:",
                    ]
                ):
                    skip_mode = True
                    continue

                if skip_mode and not line.strip():
                    skip_mode = False
                    continue

                if not skip_mode:
                    cleaned_lines.append(line)

            cleaned_text = "\n".join(cleaned_lines).strip()

            if not cleaned_text and "ANSWER:" in text:
                parts = text.split("ANSWER:")
                if len(parts) > 1:
                    return parts[1].strip()

            if not cleaned_text:
                logger.warning(
                    "Failed to extract meaningful answer after cleaning system prompts. Returning original text."
                )
                return text

            return cleaned_text

        except Exception as e:
            logger.error(f"Error processing outgoing response: {e!s}")
            return text


def create_content_filter_service(
    vector_db: VectorDBClient | None = None,
    safety_llm: LLMAdapter | None = None,
    mode: SafetyMode | str | None = None,
    default_threshold: float | None = None,
) -> ContentFilterService:
    """Factory helper to create a ContentFilterService with the configured safety mode.

    Args:
        default_threshold: If None, uses settings.FILTER_DEFAULT_THRESHOLD
    """

    return ContentFilterService(
        vector_db=vector_db,
        safety_llm=safety_llm,
        mode=mode,
        default_threshold=default_threshold,
    )
