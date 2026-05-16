"""
Tests for production mode restrictions on mock/dummy components.

These tests verify that LLMAdapter and Reranker properly reject
mock/test modes when running in production environment.
"""


from config.settings import settings
from src.utils.production_validators import validate_production_config


class TestProductionValidationIntegration:
    """Integration tests for production validation catching mock mode."""

    def test_production_validators_detect_test_mode(self, monkeypatch):
        """Test that production validators detect AVI_TEST_MODE enabled."""
        monkeypatch.setenv("AVI_TEST_MODE", "1")
        monkeypatch.setattr(settings, "MAIN_LLM_API_KEY", "sk-validkey1234567890")
        monkeypatch.setattr(settings, "MAIN_LLM_MODEL", "gpt-4")

        passed, errors = validate_production_config()

        assert passed is False
        assert any("AVI_TEST_MODE" in error for error in errors)
        assert any("test mode must be disabled" in error.lower() for error in errors)

    def test_production_validators_pass_without_test_mode(self, monkeypatch):
        """Test that production validators pass with proper configuration."""
        monkeypatch.setenv("AVI_TEST_MODE", "0")
        monkeypatch.setattr(settings, "MAIN_LLM_API_KEY", "sk-validkey1234567890")
        monkeypatch.setattr(settings, "MAIN_LLM_MODEL", "gpt-4")
        monkeypatch.setattr(settings, "VECTOR_DB_PROVIDER", "qdrant")

        passed, errors = validate_production_config()

        # Should pass when test mode is disabled and credentials are valid
        assert passed is True
        assert len(errors) == 0
