"""
Token counting utility for tracking usage metrics.
"""

import tiktoken
from functools import lru_cache


@lru_cache(maxsize=4)
def get_encoding(model: str = "gpt-4") -> tiktoken.Encoding:
    """
    Get tiktoken encoding for a model.
    Cached to avoid repeated loading.

    Args:
        model: Model name (gpt-4, gpt-3.5-turbo, etc.)

    Returns:
        Tiktoken encoding
    """
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        # Fallback to cl100k_base for unknown models
        return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """
    Count tokens in text for a given model.

    Args:
        text: Text to count tokens in
        model: Model name

    Returns:
        Number of tokens
    """
    if not text:
        return 0

    encoding = get_encoding(model)
    return len(encoding.encode(text))


def count_message_tokens(messages: list[dict], model: str = "gpt-4") -> int:
    """
    Count tokens in a list of chat messages.

    Args:
        messages: List of messages with 'role' and 'content'
        model: Model name

    Returns:
        Total number of tokens including formatting overhead
    """
    encoding = get_encoding(model)
    tokens = 0

    # Tokens for message formatting
    # Based on OpenAI's token counting:
    # https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
    tokens_per_message = 3  # Every message follows <|start|>{role/name}\n{content}<|end|>\n
    tokens_per_name = 1  # If there's a name, the role is omitted

    for message in messages:
        tokens += tokens_per_message
        for key, value in message.items():
            if value:
                tokens += len(encoding.encode(str(value)))
            if key == "name":
                tokens += tokens_per_name

    tokens += 3  # Every reply is primed with <|start|>assistant<|message|>

    return tokens


class UsageMetrics:
    """Container for usage metrics."""

    def __init__(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
    ):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens or (prompt_tokens + completion_tokens)

    def to_dict(self) -> dict:
        """Convert to OpenAI-compatible dict format."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }

    @classmethod
    def from_messages(cls, messages: list[dict], response: str, model: str = "gpt-4") -> "UsageMetrics":
        """
        Create UsageMetrics from messages and response.

        Args:
            messages: Input messages
            response: Assistant response
            model: Model name

        Returns:
            UsageMetrics instance
        """
        prompt_tokens = count_message_tokens(messages, model)
        completion_tokens = count_tokens(response, model)
        return cls(prompt_tokens, completion_tokens)
