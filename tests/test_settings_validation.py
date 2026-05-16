"""Tests for API settings validation logic."""

import sys
from pathlib import Path

import pytest

ROOT_PATH = Path(__file__).resolve().parents[1]
if str(ROOT_PATH) not in sys.path:
    sys.path.insert(0, str(ROOT_PATH))

from config.settings import Settings


def build_settings(**overrides):
    """Helper to create Settings instances with production defaults."""

    base_kwargs = {
        "ENVIRONMENT": "production",
        "MAIN_LLM_API_KEY": "external-key",
        "MAIN_LLM_MODEL": "external-model",
    }
    base_kwargs.update(overrides)
    return Settings(**base_kwargs)


@pytest.mark.parametrize("mode", ["llm", "remote"])
def test_validate_api_settings_requires_llm_credentials_for_llm_modes(mode):
    """LLM-style modes must provide safety LLM credentials."""

    settings = build_settings(SAFETY_MODE=mode)

    with pytest.raises(ValueError) as excinfo:
        settings.validate_api_settings()

    assert "SAFETY_LLM_API_KEY" in str(excinfo.value)


def test_validate_api_settings_accepts_service_mode_without_llm_credentials():
    """Service modes rely on a microservice URL instead of LLM credentials."""

    settings = build_settings(
        SAFETY_MODE="local",
        SAFETY_SERVICE_URL="http://safety:8001",
        SAFETY_LLM_API_KEY="",
        SAFETY_LLM_MODEL="",
    )

    # Should not raise while validating the configuration.
    settings.validate_api_settings()


def test_validate_api_settings_requires_service_url_in_service_mode():
    """Service mode must provide the safety service URL."""

    settings = build_settings(SAFETY_MODE="local")

    with pytest.raises(ValueError) as excinfo:
        settings.validate_api_settings()

    assert "SAFETY_SERVICE_URL" in str(excinfo.value)
