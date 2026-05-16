"""
LLM Client Wrapper

Unified interface for different LLM providers (OpenAI, Cotype, etc.)
"""

import os
from typing import Optional, List, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class LLMClient:
    """Unified LLM client for multiple providers"""

    def __init__(
        self,
        provider: str = "openai",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ):
        """
        Initialize LLM client

        Args:
            provider: "openai" or "cotype"
            model: Model name (e.g., "gpt-4o-mini", "cotype-2.5-pro")
            api_key: API key (or from env)
            api_base: API base URL (or from env)
            temperature: Sampling temperature
            max_tokens: Max tokens in response
        """
        self.provider = provider
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Setup based on provider
        if provider == "openai":
            self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

        elif provider == "cotype":
            self.model = model or os.getenv("COTYPE_MODEL", "cotype-2.5-pro")
            self.client = OpenAI(
                api_key=api_key or os.getenv("COTYPE_API_KEY"),
                base_url=api_base or os.getenv("COTYPE_API_BASE", "https://api.mws.ai/v1")
            )

        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> str:
        """
        Generate text completion

        Args:
            prompt: User prompt
            system_prompt: System prompt (optional)
            temperature: Override default temperature
            max_tokens: Override default max_tokens
            json_mode: Enable JSON response format

        Returns:
            Generated text
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        # Call API
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
        }

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = self.client.chat.completions.create(**kwargs)

        return response.choices[0].message.content.strip()

    def generate_batch(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None,
        show_progress: bool = True,
    ) -> List[str]:
        """
        Generate completions for multiple prompts

        Args:
            prompts: List of prompts
            system_prompt: System prompt for all
            show_progress: Show tqdm progress bar

        Returns:
            List of generated texts
        """
        results = []

        iterator = prompts
        if show_progress:
            from tqdm import tqdm
            iterator = tqdm(prompts, desc="Generating")

        for prompt in iterator:
            result = self.generate(prompt, system_prompt=system_prompt)
            results.append(result)

        return results


class PromptTemplate:
    """Helper for managing prompt templates"""

    @staticmethod
    def load_from_yaml(path: str) -> Dict[str, str]:
        """Load prompts from YAML config"""
        import yaml

        with open(path, 'r') as f:
            return yaml.safe_load(f)

    @staticmethod
    def format(template: str, **kwargs) -> str:
        """Format template with variables"""
        return template.format(**kwargs)
