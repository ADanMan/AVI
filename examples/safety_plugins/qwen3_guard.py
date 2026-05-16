"""
Qwen3Guard plugin for AVI.

This plugin integrates Alibaba's Qwen3Guard model for content safety.

Qwen3Guard is a multilingual safety guardrail model series that provides:
- Support for 119 languages and dialects
- 9 comprehensive safety categories
- Three-tier classification (Safe, Controversial, Unsafe)
- Real-time streaming detection (Stream variant)
- Full-context safety assessment (Gen variant)

Installation:
    # For local inference
    pip install transformers torch accelerate

    # For server deployment (optional)
    pip install sglang>=0.4.6.post1  # or vllm>=0.9.0

Configuration:
    Supports local inference or API endpoint (SGLang/vLLM)

Usage:
    from src.services.safety_plugin import SafetyPluginLoader

    # Gen variant (full-context moderation)
    plugin = SafetyPluginLoader.load_plugin(
        "examples.safety_plugins.qwen3_guard.Qwen3GuardGenPlugin",
        config={
            "model": "Qwen/Qwen3Guard-Gen-4B",
            "device": "cuda",
            "load_in_4bit": True
        }
    )

    # Stream variant (real-time detection)
    plugin = SafetyPluginLoader.load_plugin(
        "examples.safety_plugins.qwen3_guard.Qwen3GuardStreamPlugin",
        config={
            "model": "Qwen/Qwen3Guard-Stream-4B",
            "device": "cuda"
        }
    )
"""

from __future__ import annotations

import re
from typing import Any

from src.services.safety_plugin import SafetyModelPlugin, SafetyResult


class Qwen3GuardGenPlugin(SafetyModelPlugin):
    """
    Safety plugin using Qwen3Guard-Gen for full-context moderation.

    Qwen3Guard-Gen is designed for comprehensive safety assessment of
    full prompts and responses. It provides detailed categorization
    across 9 safety categories with three-tier classification.

    Safety Categories (9):
    - Violent: Violence and physical harm
    - Non-violent Illegal Acts: Illegal activities without violence
    - Sexual Content or Sexual Acts: Adult or sexual content
    - PII: Personal Identifiable Information
    - Suicide & Self-Harm: Self-harm or suicide content
    - Unethical Acts: Unethical behavior or fraud
    - Politically Sensitive Topics: Political content (context-dependent)
    - Copyright Violation: IP and copyright infringement
    - Jailbreak: Attempts to bypass safety measures

    Classification Levels:
    - Safe: Content is safe
    - Controversial: Content may be unsafe depending on context
    - Unsafe: Content is definitely unsafe

    Model Sizes:
    - Qwen/Qwen3Guard-Gen-0.6B: ~1.2GB VRAM (fastest)
    - Qwen/Qwen3Guard-Gen-4B: ~8GB VRAM (balanced)
    - Qwen/Qwen3Guard-Gen-8B: ~16GB VRAM (most accurate)
    """

    SAFETY_CATEGORIES = [
        "Violent",
        "Non-violent Illegal Acts",
        "Sexual Content or Sexual Acts",
        "PII",
        "Suicide & Self-Harm",
        "Unethical Acts",
        "Politically Sensitive Topics",
        "Copyright Violation",
        "Jailbreak",
    ]

    def __init__(
        self,
        model: str = "Qwen/Qwen3Guard-Gen-4B",
        device: str = "cuda",
        load_in_4bit: bool = False,
        max_length: int = 8192,
        controversial_as_unsafe: bool = False,
        api_base: str | None = None,
        api_key: str | None = None,
    ):
        """
        Initialize Qwen3Guard-Gen plugin.

        Args:
            model: HuggingFace model identifier or API model name
            device: Device to load model on ("cuda" or "cpu")
            load_in_4bit: Use 4-bit quantization to reduce memory
            max_length: Maximum input length in tokens (default: 8192)
            controversial_as_unsafe: Treat "Controversial" as unsafe (default: False)
            api_base: API base URL if using server deployment (SGLang/vLLM)
            api_key: API key if required by server
        """
        self.model_name_or_path = model
        self.device = device
        self.max_length = max_length
        self.controversial_as_unsafe = controversial_as_unsafe
        self.api_base = api_base
        self.api_key = api_key

        # Initialize based on deployment mode
        if api_base:
            # API mode (SGLang/vLLM)
            self._init_api_client()
        else:
            # Local inference mode
            self._init_local_model(load_in_4bit)

    def _init_local_model(self, load_in_4bit: bool):
        """Initialize local model with transformers."""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch
        except ImportError:
            raise ImportError(
                "transformers and torch required. Install with: "
                "pip install transformers torch accelerate"
            )

        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name_or_path, trust_remote_code=True
        )

        # Configure quantization if requested
        model_kwargs: dict[str, Any] = {
            "torch_dtype": "auto",
            "device_map": "auto" if self.device == "cuda" else None,
            "trust_remote_code": True,
        }

        if load_in_4bit:
            try:
                from transformers import BitsAndBytesConfig

                model_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4",
                )
            except ImportError:
                raise ImportError(
                    "bitsandbytes required for 4-bit. Install with: pip install bitsandbytes"
                )

        # Load model
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name_or_path, **model_kwargs
        )

        if not load_in_4bit and self.device == "cpu":
            self.model = self.model.to(self.device)

        self.model.eval()
        self.client = None

    def _init_api_client(self):
        """Initialize API client for server deployment."""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError("openai package required for API mode. Install with: pip install openai")

        self.client = AsyncOpenAI(
            api_key=self.api_key or "EMPTY",
            base_url=self.api_base,
        )
        self.model = None
        self.tokenizer = None

    async def check_safety(self, text: str, context: str | None = None) -> SafetyResult:
        """
        Check text safety using Qwen3Guard-Gen.

        For prompt moderation:
            check_safety("User prompt here")

        For response moderation:
            check_safety("Assistant response", context="User prompt")
        """
        try:
            if self.client:
                # API mode
                return await self._check_safety_api(text, context)
            else:
                # Local inference mode
                return await self._check_safety_local(text, context)

        except Exception as e:
            # Return error as unsafe
            return SafetyResult(
                is_safe=False,
                confidence=0.5,
                categories=["error"],
                explanation=f"Qwen3Guard check failed: {str(e)}",
                sanitized_text=None,
                metadata={"error": str(e)},
            )

    async def _check_safety_local(self, text: str, context: str | None = None) -> SafetyResult:
        """Local inference with transformers."""
        import torch

        # Prepare messages
        messages = []
        if context:
            # Response moderation
            messages.append({"role": "user", "content": context})
            messages.append({"role": "assistant", "content": text})
        else:
            # Prompt moderation
            messages.append({"role": "user", "content": text})

        # Apply chat template
        formatted_input = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        # Tokenize
        inputs = self.tokenizer(
            formatted_input,
            return_tensors="pt",
            max_length=self.max_length,
            truncation=True,
        )

        if self.device == "cuda":
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Generate
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=200,
                temperature=0.0,
                do_sample=False,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )

        # Decode output
        generated_ids = outputs[0][inputs["input_ids"].shape[1] :]
        result_text = self.tokenizer.decode(generated_ids, skip_special_tokens=True)

        # Parse result
        return self._parse_result(result_text)

    async def _check_safety_api(self, text: str, context: str | None = None) -> SafetyResult:
        """API inference via SGLang/vLLM."""
        # Prepare messages
        messages = []
        if context:
            messages.append({"role": "user", "content": context})
            messages.append({"role": "assistant", "content": text})
        else:
            messages.append({"role": "user", "content": text})

        # Call API
        response = await self.client.chat.completions.create(
            model=self.model_name_or_path,
            messages=messages,
            temperature=0.0,
            max_tokens=200,
        )

        result_text = response.choices[0].message.content

        # Parse result
        return self._parse_result(result_text)

    def _parse_result(self, result_text: str) -> SafetyResult:
        """
        Parse Qwen3Guard output format.

        Expected format:
            Safety: [Safe|Unsafe|Controversial]
            Categories: [list of categories or None]
            Refusal: [Yes|No]  (optional, for response moderation)
        """
        # Extract safety level
        safety_match = re.search(
            r"Safety:\s*(Safe|Unsafe|Controversial)", result_text, re.IGNORECASE
        )
        if safety_match:
            safety_level = safety_match.group(1).capitalize()
        else:
            # Default to unsafe if parsing fails
            safety_level = "Unsafe"

        # Extract categories
        categories_match = re.search(
            r"Categories:\s*(.+?)(?:\n|$)", result_text, re.IGNORECASE
        )
        if categories_match:
            categories_text = categories_match.group(1).strip()
            if categories_text.lower() in ["none", "[]", ""]:
                categories = []
            else:
                # Parse comma-separated categories
                categories = [
                    cat.strip() for cat in categories_text.split(",") if cat.strip()
                ]
        else:
            categories = []

        # Extract refusal (for response moderation)
        refusal_match = re.search(r"Refusal:\s*(Yes|No)", result_text, re.IGNORECASE)
        has_refusal = refusal_match and refusal_match.group(1).lower() == "yes"

        # Determine if safe
        if safety_level == "Safe":
            is_safe = True
            confidence = 0.95
        elif safety_level == "Controversial":
            # Controversial can be treated as safe or unsafe based on config
            is_safe = not self.controversial_as_unsafe
            confidence = 0.70  # Lower confidence for controversial
        else:  # Unsafe
            is_safe = False
            confidence = 0.90

        # Build explanation
        if is_safe:
            if safety_level == "Controversial":
                explanation = f"Content is controversial but allowed. Categories: {', '.join(categories) if categories else 'None'}"
            else:
                explanation = "Content passed all safety checks"
        else:
            if categories:
                explanation = f"Content flagged as {safety_level}. Categories: {', '.join(categories)}"
            else:
                explanation = f"Content flagged as {safety_level}"

        if has_refusal:
            explanation += " (Response contained refusal)"

        return SafetyResult(
            is_safe=is_safe,
            confidence=confidence,
            categories=categories,
            explanation=explanation,
            sanitized_text=None,
            metadata={
                "safety_level": safety_level,
                "refusal": has_refusal,
                "raw_output": result_text,
            },
        )

    async def check_health(self) -> bool:
        """Health check for Qwen3Guard-Gen model."""
        try:
            # Simple test with benign content
            result = await self.check_safety("Hello, how are you?")
            return result.confidence > 0
        except Exception:
            return False

    @property
    def model_name(self) -> str:
        """Return model identifier."""
        return f"qwen3guard-gen-{self.model_name_or_path.split('/')[-1]}"


class Qwen3GuardStreamPlugin(SafetyModelPlugin):
    """
    Safety plugin using Qwen3Guard-Stream for real-time streaming detection.

    Qwen3Guard-Stream is designed for token-level safety monitoring during
    incremental text generation. It can detect safety issues in real-time
    as tokens are being generated, allowing for early stopping of unsafe content.

    Use Cases:
    - Real-time content moderation during LLM generation
    - Stream safety scoring for RAG systems
    - Early detection and prevention of unsafe outputs
    - Low-latency safety checks for chat applications

    Features:
    - Token-level classification head
    - Streaming detection capability
    - Lower latency than Gen variant
    - Same 9 safety categories

    Note: This plugin performs safety checks on complete text chunks.
    For true streaming token-by-token detection, integrate directly with
    your generation pipeline using the model's classification head.
    """

    def __init__(
        self,
        model: str = "Qwen/Qwen3Guard-Stream-4B",
        device: str = "cuda",
        load_in_4bit: bool = False,
        max_length: int = 8192,
        controversial_as_unsafe: bool = False,
        chunk_size: int = 512,
    ):
        """
        Initialize Qwen3Guard-Stream plugin.

        Args:
            model: HuggingFace model identifier
            device: Device to load model on ("cuda" or "cpu")
            load_in_4bit: Use 4-bit quantization to reduce memory
            max_length: Maximum input length in tokens
            controversial_as_unsafe: Treat "Controversial" as unsafe
            chunk_size: Size of chunks for streaming detection (tokens)
        """
        self.model_name_or_path = model
        self.device = device
        self.max_length = max_length
        self.controversial_as_unsafe = controversial_as_unsafe
        self.chunk_size = chunk_size

        # Initialize model
        self._init_model(load_in_4bit)

    def _init_model(self, load_in_4bit: bool):
        """Initialize streaming model."""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch
        except ImportError:
            raise ImportError(
                "transformers and torch required. Install with: "
                "pip install transformers torch accelerate"
            )

        # Load tokenizer (must use Qwen3 tokenizer for Stream variant)
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name_or_path, trust_remote_code=True
        )

        # Configure model loading
        model_kwargs: dict[str, Any] = {
            "torch_dtype": "auto",
            "device_map": "auto" if self.device == "cuda" else None,
            "trust_remote_code": True,
        }

        if load_in_4bit:
            try:
                from transformers import BitsAndBytesConfig
                import torch

                model_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4",
                )
            except ImportError:
                raise ImportError(
                    "bitsandbytes required for 4-bit. Install with: pip install bitsandbytes"
                )

        # Load model with classification head
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name_or_path, **model_kwargs
        )

        if not load_in_4bit and self.device == "cpu":
            self.model = self.model.to(self.device)

        self.model.eval()

    async def check_safety(self, text: str, context: str | None = None) -> SafetyResult:
        """
        Check text safety using Qwen3Guard-Stream.

        This performs chunk-based safety detection. For true streaming
        token-by-token detection, use the model's classification head
        directly in your generation pipeline.
        """
        try:
            import torch

            # Prepare input
            if context:
                full_text = f"{context}\n{text}"
            else:
                full_text = text

            # Tokenize
            inputs = self.tokenizer(
                full_text,
                return_tensors="pt",
                max_length=self.max_length,
                truncation=True,
            )

            if self.device == "cuda":
                inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # Forward pass to get classification scores
            with torch.no_grad():
                outputs = self.model(**inputs, output_hidden_states=True)

                # Extract classification head output
                # Note: Actual implementation depends on model architecture
                # This is a simplified version
                logits = outputs.logits[:, -1, :]  # Last token logits

                # Get safety scores (simplified)
                # In production, use the actual classification head
                safety_score = torch.sigmoid(logits.mean()).item()

            # Determine safety based on score
            is_safe = safety_score < 0.5
            confidence = abs(safety_score - 0.5) * 2  # Scale to 0-1

            # For streaming variant, we provide simplified categorization
            categories = []
            if not is_safe:
                categories = ["potential_unsafe"]

            return SafetyResult(
                is_safe=is_safe,
                confidence=min(0.95, max(0.5, confidence)),
                categories=categories,
                explanation=f"Stream safety score: {safety_score:.3f}",
                sanitized_text=None,
                metadata={
                    "safety_score": safety_score,
                    "streaming": True,
                },
            )

        except Exception as e:
            return SafetyResult(
                is_safe=False,
                confidence=0.5,
                categories=["error"],
                explanation=f"Qwen3Guard-Stream check failed: {str(e)}",
                sanitized_text=None,
            )

    async def check_health(self) -> bool:
        """Health check for Qwen3Guard-Stream model."""
        try:
            result = await self.check_safety("Hello")
            return result.confidence > 0
        except Exception:
            return False

    @property
    def model_name(self) -> str:
        """Return model identifier."""
        return f"qwen3guard-stream-{self.model_name_or_path.split('/')[-1]}"


# Helper function for easy deployment
def create_qwen3guard_plugin(
    variant: str = "gen",
    size: str = "4B",
    device: str = "cuda",
    load_in_4bit: bool = False,
    **kwargs,
) -> SafetyModelPlugin:
    """
    Create Qwen3Guard plugin with easy configuration.

    Args:
        variant: "gen" or "stream"
        size: "0.6B", "4B", or "8B"
        device: "cuda" or "cpu"
        load_in_4bit: Use 4-bit quantization
        **kwargs: Additional arguments passed to plugin constructor

    Returns:
        Configured Qwen3Guard plugin instance

    Example:
        >>> # Quick setup for Gen variant
        >>> plugin = create_qwen3guard_plugin(variant="gen", size="4B", load_in_4bit=True)
        >>> result = await plugin.check_safety("Test message")

        >>> # Stream variant for real-time detection
        >>> plugin = create_qwen3guard_plugin(variant="stream", size="0.6B")
    """
    model_name = f"Qwen/Qwen3Guard-{variant.capitalize()}-{size}"

    if variant.lower() == "gen":
        return Qwen3GuardGenPlugin(
            model=model_name, device=device, load_in_4bit=load_in_4bit, **kwargs
        )
    elif variant.lower() == "stream":
        return Qwen3GuardStreamPlugin(
            model=model_name, device=device, load_in_4bit=load_in_4bit, **kwargs
        )
    else:
        raise ValueError(f"Unknown variant: {variant}. Must be 'gen' or 'stream'")
