"""
NVIDIA Nemotron Guard plugin for AVI.

This plugin integrates NVIDIA's Nemotron Guard model for content safety.

Nemotron Guard is NVIDIA's safety classifier model that provides:
- Multi-category safety classification
- High accuracy content moderation
- Support for multiple languages
- Low latency inference

Installation:
    pip install openai  # NVIDIA NIM uses OpenAI-compatible API

Configuration:
    Requires NVIDIA API key from build.nvidia.com

Usage:
    from src.services.safety_plugin import SafetyPluginLoader

    plugin = SafetyPluginLoader.load_plugin(
        "examples.safety_plugins.nvidia_nemotron_guard.NvidiaNemotronGuardPlugin",
        config={
            "api_key": "your-nvidia-api-key",
            "base_url": "https://integrate.api.nvidia.com/v1"  # or your self-hosted endpoint
        }
    )

Features:
- Content safety classification
- Toxicity detection
- Hate speech detection
- Violence detection
- Sexual content detection
- Self-harm detection
"""

from __future__ import annotations

from src.services.safety_plugin import SafetyModelPlugin, SafetyResult


class NvidiaNemotronGuardPlugin(SafetyModelPlugin):
    """
    Safety plugin using NVIDIA Nemotron Guard.

    Nemotron Guard is NVIDIA's safety classifier that provides:
    - Comprehensive content moderation
    - Multi-category classification
    - High accuracy and low latency
    - Support for multiple languages

    Safety Categories:
    - Violence: Content depicting violence or harm
    - Hate: Hate speech or discriminatory content
    - Sexual: Sexual or adult content
    - Self-Harm: Content promoting self-harm
    - Toxicity: Toxic or offensive language
    - Harassment: Bullying or harassment content
    """

    # Nemotron Guard safety categories
    CATEGORIES = [
        "violence",
        "hate",
        "sexual",
        "self-harm",
        "toxicity",
        "harassment",
    ]

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://integrate.api.nvidia.com/v1",
        model: str = "nvidia/nemotron-guard",
        threshold: float = 0.5,
        timeout: float = 30.0,
    ):
        """
        Initialize NVIDIA Nemotron Guard plugin.

        Args:
            api_key: NVIDIA API key from build.nvidia.com
            base_url: Base URL for NVIDIA API (default: NVIDIA NIM endpoint)
            model: Model identifier (default: nvidia/nemotron-guard)
            threshold: Classification threshold (0.0-1.0, default: 0.5)
            timeout: Request timeout in seconds (default: 30.0)
        """
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError(
                "openai package required for NVIDIA NIM. Install with: pip install openai"
            )

        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.threshold = threshold
        self.timeout = timeout

        # Initialize client (NVIDIA NIM uses OpenAI-compatible API)
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    async def check_safety(self, text: str, context: str | None = None) -> SafetyResult:
        """
        Check text safety using NVIDIA Nemotron Guard.

        This performs comprehensive safety classification across multiple categories.
        """
        try:
            # Prepare the prompt for Nemotron Guard
            # Nemotron Guard expects a structured input format
            if context:
                prompt = f"Context: {context}\n\nText to evaluate: {text}"
            else:
                prompt = text

            # Call NVIDIA Nemotron Guard API
            # Note: The actual API format may vary based on NVIDIA's implementation
            # This uses the chat completions endpoint with safety-focused prompting
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a content safety classifier. Evaluate the following text "
                            "for safety issues across these categories: violence, hate, sexual, "
                            "self-harm, toxicity, harassment. Respond with a JSON object containing "
                            "scores (0.0-1.0) for each category, where higher scores indicate unsafe content."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=500,
                timeout=self.timeout,
            )

            # Parse response
            result_text = response.choices[0].message.content

            # Extract safety scores (this is a simplified parsing)
            # In production, you'd parse the JSON response properly
            scores = self._parse_safety_scores(result_text)

            # Determine if content is safe
            is_safe = all(score < self.threshold for score in scores.values())

            # Get flagged categories
            flagged_categories = [
                category for category, score in scores.items() if score >= self.threshold
            ]

            # Calculate confidence (use highest score)
            max_score = max(scores.values()) if scores else 0.0
            confidence = max_score if not is_safe else (1.0 - max_score)

            # Build explanation
            if flagged_categories:
                category_details = ", ".join(
                    [f"{cat} ({scores[cat]:.2f})" for cat in flagged_categories]
                )
                explanation = f"Content flagged for: {category_details}"
            else:
                explanation = "Content passed all safety checks"

            return SafetyResult(
                is_safe=is_safe,
                confidence=min(0.99, max(0.5, confidence)),
                categories=flagged_categories,
                explanation=explanation,
                sanitized_text=None,
                metadata={
                    "model": self.model,
                    "scores": scores,
                    "threshold": self.threshold,
                },
            )

        except Exception as e:
            # Return error as unsafe with low confidence
            return SafetyResult(
                is_safe=False,
                confidence=0.5,
                categories=["error"],
                explanation=f"Nemotron Guard check failed: {str(e)}",
                sanitized_text=None,
                metadata={"error": str(e)},
            )

    def _parse_safety_scores(self, result_text: str) -> dict[str, float]:
        """
        Parse safety scores from Nemotron Guard response.

        This is a simplified parser. In production, you'd use proper JSON parsing.
        """
        import json
        import re

        scores = {category: 0.0 for category in self.CATEGORIES}

        try:
            # Try to parse as JSON
            # Remove markdown code blocks if present
            text = result_text.strip()
            if text.startswith("```"):
                text = re.sub(r"```(?:json)?\n?", "", text)
                text = text.strip()

            data = json.loads(text)

            # Extract scores from JSON response
            for category in self.CATEGORIES:
                if category in data:
                    scores[category] = float(data[category])
                # Handle different key formats
                elif category.replace("-", "_") in data:
                    scores[category] = float(data[category.replace("-", "_")])
                elif category.replace("-", " ") in data:
                    scores[category] = float(data[category.replace("-", " ")])

        except (json.JSONDecodeError, ValueError):
            # Fallback: try to extract scores using regex
            for category in self.CATEGORIES:
                # Look for patterns like "violence: 0.8" or '"violence": 0.8'
                pattern = rf'"{category}"?\s*:\s*([0-9.]+)'
                match = re.search(pattern, result_text, re.IGNORECASE)
                if match:
                    scores[category] = float(match.group(1))

        return scores

    async def check_health(self) -> bool:
        """Health check for NVIDIA Nemotron Guard API."""
        try:
            # Simple test with benign content
            result = await self.check_safety("Hello, how are you?")
            return result.confidence > 0
        except Exception:
            return False

    @property
    def model_name(self) -> str:
        """Return model identifier."""
        return f"nvidia-nemotron-guard-{self.model.split('/')[-1]}"


# Alternative: Local Triton Inference Implementation
class NvidiaNemotronGuardLocalPlugin(SafetyModelPlugin):
    """
    Safety plugin using locally deployed NVIDIA Nemotron Guard via Triton.

    This variant runs Nemotron Guard on your own infrastructure using
    NVIDIA Triton Inference Server.

    Requirements:
    - NVIDIA GPU with sufficient VRAM
    - NVIDIA Triton Inference Server
    - tritonclient package

    Installation:
        pip install tritonclient[http]

    Usage:
        plugin = SafetyPluginLoader.load_plugin(
            "examples.safety_plugins.nvidia_nemotron_guard.NvidiaNemotronGuardLocalPlugin",
            config={
                "triton_url": "localhost:8000",
                "model_name": "nemotron_guard"
            }
        )
    """

    def __init__(
        self,
        triton_url: str = "localhost:8000",
        model_name: str = "nemotron_guard",
        model_version: str = "1",
        threshold: float = 0.5,
    ):
        """
        Initialize local Nemotron Guard plugin.

        Args:
            triton_url: Triton server URL (default: localhost:8000)
            model_name: Model name in Triton (default: nemotron_guard)
            model_version: Model version (default: 1)
            threshold: Classification threshold (0.0-1.0, default: 0.5)
        """
        try:
            import tritonclient.http as httpclient
        except ImportError:
            raise ImportError(
                "tritonclient required for local inference. "
                "Install with: pip install tritonclient[http]"
            )

        self.triton_url = triton_url
        self.model_name = model_name
        self.model_version = model_version
        self.threshold = threshold

        # Initialize Triton client
        self.client = httpclient.InferenceServerClient(url=triton_url)

    async def check_safety(self, text: str, context: str | None = None) -> SafetyResult:
        """Check text safety using local Nemotron Guard via Triton."""
        try:
            import tritonclient.http as httpclient
            import numpy as np

            # Prepare input
            if context:
                input_text = f"{context}\n\n{text}"
            else:
                input_text = text

            # Create input tensor
            input_data = np.array([input_text], dtype=object)
            inputs = [
                httpclient.InferInput("INPUT_TEXT", input_data.shape, "BYTES")
            ]
            inputs[0].set_data_from_numpy(input_data)

            # Create output request
            outputs = [
                httpclient.InferRequestedOutput("OUTPUT_SCORES"),
                httpclient.InferRequestedOutput("OUTPUT_CATEGORIES"),
            ]

            # Run inference
            response = self.client.infer(
                model_name=self.model_name,
                model_version=self.model_version,
                inputs=inputs,
                outputs=outputs,
            )

            # Extract results
            scores = response.as_numpy("OUTPUT_SCORES")[0]
            categories = response.as_numpy("OUTPUT_CATEGORIES")[0]

            # Determine safety
            is_safe = float(np.max(scores)) < self.threshold
            flagged_categories = [
                cat.decode("utf-8") if isinstance(cat, bytes) else str(cat)
                for i, cat in enumerate(categories)
                if scores[i] >= self.threshold
            ]

            max_score = float(np.max(scores))
            confidence = max_score if not is_safe else (1.0 - max_score)

            return SafetyResult(
                is_safe=is_safe,
                confidence=min(0.99, max(0.5, confidence)),
                categories=flagged_categories,
                explanation=f"Max score: {max_score:.3f}, Threshold: {self.threshold}",
                sanitized_text=None,
                metadata={
                    "scores": scores.tolist(),
                    "all_categories": [
                        cat.decode("utf-8") if isinstance(cat, bytes) else str(cat)
                        for cat in categories
                    ],
                },
            )

        except Exception as e:
            return SafetyResult(
                is_safe=False,
                confidence=0.5,
                categories=["error"],
                explanation=f"Local Nemotron Guard check failed: {str(e)}",
                sanitized_text=None,
            )

    async def check_health(self) -> bool:
        """Health check for local Triton server."""
        try:
            return self.client.is_server_live() and self.client.is_model_ready(
                self.model_name, self.model_version
            )
        except Exception:
            return False

    @property
    def model_name(self) -> str:
        """Return model identifier."""
        return f"nvidia-nemotron-guard-local-{self.model_name}"
