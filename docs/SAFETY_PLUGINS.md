# Safety Model Plugins

## Overview

AVI supports custom safety model plugins, allowing you to integrate your own content moderation and safety models. The built-in regex-based safety service is **disabled by default**, giving you full flexibility to choose and implement your preferred safety solution.

## Why Use Custom Safety Plugins?

The default safety service uses simple regex patterns, which are:
- ❌ Limited in accuracy
- ❌ Easy to bypass
- ❌ Language-specific
- ❌ Can't understand context

Custom plugins allow you to use:
- ✅ State-of-the-art ML models (Llama Guard, GPT-4)
- ✅ Commercial APIs (OpenAI Moderation, Perspective API)
- ✅ Your own fine-tuned models
- ✅ Hybrid approaches (ML + rules)
- ✅ Context-aware moderation

## Plugin Architecture

### SafetyModelPlugin Interface

All custom plugins must implement the `SafetyModelPlugin` abstract base class:

```python
from src.services.safety_plugin import SafetyModelPlugin, SafetyResult

class MyCustomPlugin(SafetyModelPlugin):
    async def check_safety(self, text: str, context: str | None = None) -> SafetyResult:
        """
        Check if text is safe.

        Returns:
            SafetyResult with is_safe, confidence, categories, explanation
        """
        # Your safety logic here
        pass

    async def check_health(self) -> bool:
        """Health check for the model."""
        # Return True if operational
        pass

    @property
    def model_name(self) -> str:
        """Return model identifier."""
        return "my-custom-model"
```

### SafetyResult

The `SafetyResult` dataclass contains:

```python
@dataclass
class SafetyResult:
    is_safe: bool                    # True if content is safe
    confidence: float                # 0.0-1.0 confidence score
    categories: list[str]            # Flagged categories
    explanation: str                 # Human-readable explanation
    sanitized_text: str | None      # Optional sanitized version
    metadata: dict[str, Any]         # Additional metadata
```

## Quick Start

### 1. Choose Your Safety Model

Available options:
- **OpenAI Moderation API**: Easy integration, high accuracy, paid API
- **Qwen3Guard**: Alibaba's multilingual safety model (119 languages), Gen + Stream variants, 9 categories
- **NVIDIA Nemotron Guard**: NVIDIA's safety classifier, API or self-hosted, multi-category detection
- **Custom Transformer**: Fine-tune your own model
- **Regex-based**: Simple patterns (included)

### 2. Implement Your Plugin

See `examples/safety_plugins/` for complete examples:

```bash
examples/safety_plugins/
├── __init__.py
├── openai_moderation.py       # OpenAI Moderation API
├── qwen3_guard.py             # Qwen3Guard (Gen + Stream)
├── nvidia_nemotron_guard.py   # NVIDIA Nemotron Guard
└── simple_regex.py            # Simple regex example
```

### 3. Load and Use

```python
from src.services.safety_plugin import SafetyPluginLoader

# Load plugin
plugin = SafetyPluginLoader.load_plugin(
    "examples.safety_plugins.openai_moderation.OpenAIModerationPlugin",
    config={"api_key": "your-openai-key"}
)

# Check safety
result = await plugin.check_safety("Test message")
print(f"Safe: {result.is_safe}")
print(f"Categories: {result.categories}")
```

## Example Plugins

### OpenAI Moderation API

**Pros**: High accuracy, easy setup, 11 categories
**Cons**: Paid API, requires internet, data sent to OpenAI

**Installation**:
```bash
pip install openai
```

**Configuration**:
```python
plugin = SafetyPluginLoader.load_plugin(
    "examples.safety_plugins.openai_moderation.OpenAIModerationPlugin",
    config={
        "api_key": "your-openai-key",
        "threshold": 0.01  # Sensitivity threshold
    }
)
```

**Categories**:
- hate, hate/threatening
- harassment, harassment/threatening
- self-harm, self-harm/intent, self-harm/instructions
- sexual, sexual/minors
- violence, violence/graphic

### Qwen3Guard

**Pros**: Multilingual (119 languages), 9 categories, 3-tier classification, Gen + Stream variants, Apache 2.0
**Cons**: Requires GPU (for larger models), Gen variant slower than Stream

**Installation**:
```bash
pip install transformers torch accelerate bitsandbytes
```

**Configuration (Gen variant - full-context moderation)**:
```python
plugin = SafetyPluginLoader.load_plugin(
    "examples.safety_plugins.qwen3_guard.Qwen3GuardGenPlugin",
    config={
        "model": "Qwen/Qwen3Guard-Gen-4B",  # or 0.6B, 8B
        "device": "cuda",
        "load_in_4bit": True  # Reduce memory usage
    }
)
```

**Configuration (Stream variant - real-time detection)**:
```python
plugin = SafetyPluginLoader.load_plugin(
    "examples.safety_plugins.qwen3_guard.Qwen3GuardStreamPlugin",
    config={
        "model": "Qwen/Qwen3Guard-Stream-4B",  # or 0.6B, 8B
        "device": "cuda",
        "load_in_4bit": True,
        "chunk_size": 512  # Chunk size for streaming
    }
)
```

**Safety Categories** (9):
- Violent: Violence and physical harm
- Non-violent Illegal Acts: Illegal activities without violence
- Sexual Content or Sexual Acts: Adult or sexual content
- PII: Personal Identifiable Information
- Suicide & Self-Harm: Self-harm or suicide content
- Unethical Acts: Unethical behavior or fraud
- Politically Sensitive Topics: Political content (context-dependent)
- Copyright Violation: IP and copyright infringement
- Jailbreak: Attempts to bypass safety measures

**Classification Levels**:
- Safe: Content is safe
- Controversial: Content may be unsafe depending on context
- Unsafe: Content is definitely unsafe

**Model Sizes**:
- 0.6B: ~1.2GB VRAM (fastest, good for real-time)
- 4B: ~8GB VRAM (balanced performance/accuracy)
- 8B: ~16GB VRAM (highest accuracy)

**Features**:
- Support for 119 languages and dialects (including Russian, Chinese, etc.)
- Three-tier classification for flexible policies
- Gen variant for comprehensive full-context assessment
- Stream variant for real-time token-level detection
- Apache 2.0 license (fully open-source)
- API deployment support (SGLang, vLLM)

### NVIDIA Nemotron Guard

**Pros**: High accuracy, NVIDIA optimized, API or self-hosted, multi-category detection
**Cons**: Requires NVIDIA API key (cloud) or GPU infrastructure (local)

**Installation**:
```bash
# For API version
pip install openai  # NVIDIA NIM uses OpenAI-compatible API

# For local Triton version
pip install tritonclient[http]
```

**Configuration (API)**:
```python
plugin = SafetyPluginLoader.load_plugin(
    "examples.safety_plugins.nvidia_nemotron_guard.NvidiaNemotronGuardPlugin",
    config={
        "api_key": "your-nvidia-api-key",  # Get from build.nvidia.com
        "threshold": 0.5  # Safety threshold (0.0-1.0)
    }
)
```

**Configuration (Local Triton)**:
```python
plugin = SafetyPluginLoader.load_plugin(
    "examples.safety_plugins.nvidia_nemotron_guard.NvidiaNemotronGuardLocalPlugin",
    config={
        "triton_url": "localhost:8000",
        "model_name": "nemotron_guard",
        "threshold": 0.5
    }
)
```

**Categories**:
- Violence: Content depicting violence or harm
- Hate: Hate speech or discriminatory content
- Sexual: Sexual or adult content
- Self-Harm: Content promoting self-harm
- Toxicity: Toxic or offensive language
- Harassment: Bullying or harassment content

**Features**:
- Multi-category safety classification
- High accuracy content moderation
- Support for multiple languages
- Low latency inference
- Cloud API or self-hosted options
- NVIDIA GPU optimization

### Simple Regex

**Pros**: Fast, no dependencies, deterministic
**Cons**: Low accuracy, easy to bypass

**Configuration**:
```python
plugin = SafetyPluginLoader.load_plugin(
    "examples.safety_plugins.simple_regex.SimpleRegexPlugin",
    config={
        "patterns": {
            "profanity": [r"\bbad\w*\b", r"\boffensive\w*\b"],
            "violence": [r"\bharm\w*\b", r"\battack\w*\b"]
        },
        "case_sensitive": False,
        "threshold": 1  # Minimum matches to flag
    }
)
```

## Integration with AVI

### Option 1: Configure in Settings

```python
# config/settings.py or .env
SAFETY_MODE=plugin
SAFETY_PLUGIN_PATH=examples.safety_plugins.nvidia_nemotron_guard.NvidiaNemotronGuardPlugin
SAFETY_PLUGIN_CONFIG={"api_key": "your-nvidia-key"}
```

### Option 2: Programmatic Integration

```python
from src.services.safety_plugin import SafetyPluginLoader
from src.core.content_filter import ContentFilterService

# Load plugin
plugin = SafetyPluginLoader.load_plugin(
    "your.plugin.path.YourPlugin",
    config={"your": "config"}
)

# Integrate with content filter
content_filter = ContentFilterService(safety_plugin=plugin)

# Use in your application
result = await content_filter.check_content("User input")
```

### Option 3: Docker Compose

```yaml
# docker-compose.yml
environment:
  SAFETY_MODE: plugin
  SAFETY_PLUGIN_PATH: examples.safety_plugins.nvidia_nemotron_guard.NvidiaNemotronGuardPlugin
  NVIDIA_API_KEY: ${NVIDIA_API_KEY}
```

## Creating Custom Plugins

### Step 1: Create Plugin Class

```python
# plugins/my_safety/my_plugin.py

from src.services.safety_plugin import SafetyModelPlugin, SafetyResult

class MyCustomSafetyPlugin(SafetyModelPlugin):
    def __init__(self, api_key: str, threshold: float = 0.8):
        self.api_key = api_key
        self.threshold = threshold
        # Initialize your model here

    async def check_safety(self, text: str, context: str | None = None) -> SafetyResult:
        # 1. Run your safety check
        score = await your_model.predict(text)
        categories = await your_model.get_categories(text)

        # 2. Determine if safe
        is_safe = score < self.threshold

        # 3. Return result
        return SafetyResult(
            is_safe=is_safe,
            confidence=score,
            categories=categories,
            explanation=f"Safety score: {score:.2f}",
            sanitized_text=None  # Optional
        )

    async def check_health(self) -> bool:
        try:
            await your_model.ping()
            return True
        except:
            return False

    @property
    def model_name(self) -> str:
        return "my-custom-model-v1"
```

### Step 2: Test Your Plugin

```python
# tests/test_my_plugin.py

import pytest
from plugins.my_safety.my_plugin import MyCustomSafetyPlugin

@pytest.mark.asyncio
async def test_safe_content():
    plugin = MyCustomSafetyPlugin(api_key="test-key")
    result = await plugin.check_safety("Hello, how are you?")

    assert result.is_safe is True
    assert result.confidence > 0.8
    assert len(result.categories) == 0

@pytest.mark.asyncio
async def test_unsafe_content():
    plugin = MyCustomSafetyPlugin(api_key="test-key")
    result = await plugin.check_safety("harmful content here")

    assert result.is_safe is False
    assert result.confidence > 0.5
    assert len(result.categories) > 0

@pytest.mark.asyncio
async def test_health_check():
    plugin = MyCustomSafetyPlugin(api_key="test-key")
    is_healthy = await plugin.check_health()

    assert is_healthy is True
```

### Step 3: Deploy

```bash
# Add your plugin to the Python path
export PYTHONPATH=/path/to/your/plugins:$PYTHONPATH

# Configure AVI to use it
export SAFETY_MODE=plugin
export SAFETY_PLUGIN_PATH=plugins.my_safety.my_plugin.MyCustomSafetyPlugin
export SAFETY_PLUGIN_CONFIG='{"api_key": "your-key", "threshold": 0.8}'

# Start AVI
python main.py
```

## Best Practices

### Performance

1. **Cache plugin instances**: Use `SafetyPluginLoader` with `cache=True`
2. **Batch requests**: If your model supports batching
3. **Async implementation**: Always use `async/await`
4. **Timeouts**: Implement request timeouts
5. **Resource management**: Clean up model resources properly

### Error Handling

```python
async def check_safety(self, text: str, context: str | None = None) -> SafetyResult:
    try:
        # Your safety check
        result = await self.model.predict(text)
        return SafetyResult(...)

    except TimeoutError:
        # Return safe on timeout (fail-open) or unsafe (fail-closed)
        return SafetyResult(
            is_safe=True,  # or False for fail-closed
            confidence=0.0,
            categories=["timeout"],
            explanation="Safety check timed out"
        )

    except Exception as e:
        logger.error(f"Safety check failed: {e}")
        return SafetyResult(
            is_safe=False,
            confidence=0.5,
            categories=["error"],
            explanation=f"Error: {str(e)}"
        )
```

### Security

1. **API keys**: Store securely (environment variables, secrets manager)
2. **Input validation**: Sanitize inputs before sending to external APIs
3. **Rate limiting**: Implement rate limits for API calls
4. **Data privacy**: Be aware of data sent to external services
5. **Model security**: Protect model files and weights

### Monitoring

```python
from src.monitoring.observability import observe_safety_check

async def check_safety(self, text: str, context: str | None = None) -> SafetyResult:
    start_time = time.time()

    try:
        result = await self.model.predict(text)

        # Record metrics
        observe_safety_check(
            model_name=self.model_name,
            latency=time.time() - start_time,
            is_safe=result.is_safe,
            confidence=result.confidence
        )

        return result
    except Exception as e:
        # Record error
        observe_safety_check_error(model_name=self.model_name, error=str(e))
        raise
```

## Troubleshooting

### Plugin Not Loading

**Error**: `ModuleNotFoundError: No module named 'your_plugin'`

**Solution**:
- Check plugin path is correct
- Add plugin directory to PYTHONPATH
- Verify `__init__.py` exists in plugin directory

### Model Out of Memory

**Error**: `CUDA out of memory`

**Solution**:
- Use 4-bit quantization: `load_in_4bit=True`
- Reduce batch size
- Use smaller model variant
- Use CPU instead of GPU

### Low Performance

**Issue**: Safety checks taking too long

**Solution**:
- Use caching for repeated checks
- Batch requests if possible
- Consider faster model (API vs local)
- Implement request timeouts

### False Positives/Negatives

**Issue**: Incorrect safety classifications

**Solution**:
- Adjust confidence threshold
- Fine-tune model on your data
- Use hybrid approach (multiple models)
- Add custom rules for edge cases

## Migration Guide

### From Built-in Regex Service

1. Choose your plugin (e.g., OpenAI Moderation)
2. Install dependencies: `pip install openai`
3. Create plugin instance
4. Update configuration:
   ```python
   SAFETY_MODE=plugin
   SAFETY_PLUGIN_PATH=examples.safety_plugins.openai_moderation.OpenAIModerationPlugin
   ```
5. Test thoroughly before production

### From External Service

1. Implement plugin interface for your service
2. Add health checks and error handling
3. Test with your existing safety rules
4. Deploy plugin alongside AVI
5. Monitor performance and accuracy

## FAQ

**Q: Can I use multiple safety models?**
A: Yes, create a plugin that calls multiple models and combines results.

**Q: What if my model requires GPU?**
A: Deploy on GPU-enabled infrastructure or use quantization to reduce memory.

**Q: Can I update plugins without restarting AVI?**
A: Not currently. Restart AVI after plugin updates.

**Q: How do I handle rate limits?**
A: Implement retry logic with exponential backoff in your plugin.

**Q: What about data privacy?**
A: Use local models (Llama Guard) if you can't send data externally.

**Q: Can I sanitize/filter content?**
A: Yes, return sanitized text in `SafetyResult.sanitized_text`.

**Q: How to monitor plugin performance?**
A: Use AVI's built-in Prometheus metrics and add custom metrics in your plugin.

## Resources

- [Qwen3Guard Models](https://huggingface.co/collections/Qwen/qwen3guard-67a78c25c47eee8d7c6f0e4f)
- [Qwen3Guard Blog Post](https://qwenlm.github.io/blog/qwen3guard/)
- [Qwen3Guard Technical Report](https://arxiv.org/abs/2510.14276)
- [OpenAI Moderation](https://platform.openai.com/docs/guides/moderation)
- [NVIDIA Nemotron Guard](https://build.nvidia.com/nvidia/nemotron-guard)
- [NVIDIA NIM API](https://build.nvidia.com/explore/discover)
- [Perspective API](https://perspectiveapi.com/)
- [HuggingFace Safety Models](https://huggingface.co/models?pipeline_tag=text-classification&sort=trending&search=safety)

## Support

For issues and questions:
- GitHub Issues: https://github.com/your-repo/issues
- Documentation: docs/
- Examples: examples/safety_plugins/
