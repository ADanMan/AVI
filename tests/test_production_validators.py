"""
Tests for production configuration validators.
"""

from config.settings import settings
from src.utils.production_validators import (
    validate_data_directories,
    validate_llm_credentials,
    validate_production_config,
    validate_vector_db_config,
)


class TestProductionValidation:
    """Test suite for production configuration validation."""

    def test_validation_passes_with_valid_config(self, monkeypatch):
        """Test that validation passes with a valid production configuration."""
        # Patch settings object directly
        monkeypatch.setattr(settings, "MAIN_LLM_API_KEY", "sk-validapikey1234567890")
        monkeypatch.setattr(settings, "MAIN_LLM_MODEL", "gpt-4")
        monkeypatch.setattr(settings, "VECTOR_DB_PROVIDER", "qdrant")

        # Ensure test mode is not set
        monkeypatch.setenv("AVI_TEST_MODE", "0")

        passed, errors = validate_production_config()

        assert passed is True
        assert len(errors) == 0

    def test_validation_fails_with_test_mode_enabled(self, monkeypatch):
        """Test that validation fails when AVI_TEST_MODE is enabled."""
        monkeypatch.setenv("AVI_TEST_MODE", "1")
        monkeypatch.setattr(settings, "MAIN_LLM_API_KEY", "sk-validkey")
        monkeypatch.setattr(settings, "MAIN_LLM_MODEL", "gpt-4")

        passed, errors = validate_production_config()

        assert passed is False
        assert any("AVI_TEST_MODE" in error for error in errors)
        assert any("test mode must be disabled" in error.lower() for error in errors)

    def test_validation_fails_without_api_key(self, monkeypatch):
        """Test that validation fails when API key is missing."""
        monkeypatch.setenv("AVI_TEST_MODE", "0")

        # Set empty API key
        monkeypatch.setattr(settings, "MAIN_LLM_API_KEY", "")
        monkeypatch.setattr(settings, "MAIN_LLM_MODEL", "gpt-4")

        passed, errors = validate_production_config()

        assert passed is False
        assert any("MAIN_LLM_API_KEY" in error for error in errors)

    def test_validation_fails_with_placeholder_api_key(self, monkeypatch):
        """Test that validation fails with placeholder API keys."""
        monkeypatch.setenv("AVI_TEST_MODE", "0")

        # Test various placeholder values
        # Note: Some are too short and trigger length check instead of placeholder check
        placeholders = {
            "your-key-here": "placeholder value",  # 13 chars, triggers placeholder check
            "sk-xxx": "appears invalid",  # 6 chars, triggers length check
            "placeholder": "placeholder value",  # 11 chars, triggers placeholder check
            "changeme": "appears invalid",  # 8 chars, triggers length check
        }

        for placeholder, expected_error_substring in placeholders.items():
            monkeypatch.setattr(settings, "MAIN_LLM_API_KEY", placeholder)
            monkeypatch.setattr(settings, "MAIN_LLM_MODEL", "gpt-4")
            monkeypatch.setattr(settings, "VECTOR_DB_PROVIDER", "qdrant")

            passed, errors = validate_production_config()

            assert passed is False, f"Should fail with placeholder: {placeholder}"
            assert any(
                expected_error_substring in error.lower() for error in errors
            ), f"Expected '{expected_error_substring}' in errors for '{placeholder}', got: {errors}"

    def test_validation_fails_without_model(self, monkeypatch):
        """Test that validation fails when model is not specified."""
        monkeypatch.setenv("AVI_TEST_MODE", "0")

        monkeypatch.setattr(settings, "MAIN_LLM_API_KEY", "sk-validkey1234567890")
        monkeypatch.setattr(settings, "MAIN_LLM_MODEL", "")

        passed, errors = validate_production_config()

        assert passed is False
        assert any("MAIN_LLM_MODEL" in error for error in errors)


class TestLLMCredentialsValidation:
    """Test suite for LLM credentials validation."""

    def test_valid_credentials(self, monkeypatch):
        """Test validation passes with valid credentials."""
        monkeypatch.setattr(settings, "MAIN_LLM_API_KEY", "sk-validapikey1234567890")
        monkeypatch.setattr(settings, "MAIN_LLM_MODEL", "gpt-4")

        passed, errors = validate_llm_credentials()

        assert passed is True
        assert len(errors) == 0

    def test_missing_api_key(self, monkeypatch):
        """Test validation fails with missing API key."""
        monkeypatch.setattr(settings, "MAIN_LLM_API_KEY", "")
        monkeypatch.setattr(settings, "MAIN_LLM_MODEL", "gpt-4")

        passed, errors = validate_llm_credentials()

        assert passed is False
        assert len(errors) > 0
        assert any("MAIN_LLM_API_KEY is not set" in error for error in errors)

    def test_short_api_key(self, monkeypatch):
        """Test validation fails with API key that's too short."""
        monkeypatch.setattr(settings, "MAIN_LLM_API_KEY", "short")
        monkeypatch.setattr(settings, "MAIN_LLM_MODEL", "gpt-4")

        passed, errors = validate_llm_credentials()

        assert passed is False
        assert any("appears invalid" in error for error in errors)

    def test_missing_model(self, monkeypatch):
        """Test validation fails with missing model."""
        monkeypatch.setattr(settings, "MAIN_LLM_API_KEY", "sk-validkey1234567890")
        monkeypatch.setattr(settings, "MAIN_LLM_MODEL", "")

        passed, errors = validate_llm_credentials()

        assert passed is False
        assert any("MAIN_LLM_MODEL is not set" in error for error in errors)


class TestVectorDBValidation:
    """Test suite for vector database configuration validation."""

    def test_valid_qdrant_config(self, monkeypatch):
        """Test validation passes with valid Qdrant configuration."""
        monkeypatch.setattr(settings, "VECTOR_DB_PROVIDER", "qdrant")

        passed, errors = validate_vector_db_config()

        assert passed is True
        assert len(errors) == 0

    def test_valid_chroma_config(self, monkeypatch):
        """Test validation passes with valid ChromaDB configuration."""
        monkeypatch.setattr(settings, "VECTOR_DB_PROVIDER", "chroma")

        passed, _errors = validate_vector_db_config()

        assert passed is True

    def test_missing_provider(self, monkeypatch):
        """Test validation fails with missing provider."""
        monkeypatch.setattr(settings, "VECTOR_DB_PROVIDER", "")

        passed, errors = validate_vector_db_config()

        assert passed is False
        assert any("VECTOR_DB_PROVIDER is not set" in error for error in errors)

    def test_invalid_provider(self, monkeypatch):
        """Test validation fails with invalid provider."""
        monkeypatch.setattr(settings, "VECTOR_DB_PROVIDER", "invalid_provider")

        passed, errors = validate_vector_db_config()

        assert passed is False
        assert any("Invalid VECTOR_DB_PROVIDER" in error for error in errors)


class TestDataDirectoriesValidation:
    """Test suite for data directories validation."""

    def test_validation_always_passes(self):
        """
        Test that directory validation always passes.

        Missing directories are warnings, not errors, since they
        are created during startup.
        """
        passed, _warnings = validate_data_directories()

        # Should always pass (warnings don't fail validation)
        assert passed is True

        # May have warnings about missing directories
        # This is OK - directories are created during init

    def test_provides_helpful_warnings(self):
        """Test that validation provides helpful warning messages."""
        _passed, warnings = validate_data_directories()

        # Check that warnings include directory creation instructions
        if warnings:
            assert any("make init-project" in warning for warning in warnings)


class TestEnvironmentBehavior:
    """Test suite for environment-specific behavior."""

    def test_dev_environment_allows_missing_keys(self, monkeypatch):
        """Test that dev environment allows missing API keys."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("MAIN_LLM_API_KEY", "")
        monkeypatch.setenv("MAIN_LLM_MODEL", "")

        # Validation should still fail (returns errors)
        # but application won't abort in dev mode
        passed, errors = validate_production_config()

        assert passed is False
        assert len(errors) > 0

    def test_production_environment_requires_keys(self, monkeypatch):
        """Test that production environment requires API keys."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("MAIN_LLM_API_KEY", "")

        passed, errors = validate_production_config()

        assert passed is False
        assert len(errors) > 0


class TestMultipleErrors:
    """Test handling of multiple validation errors."""

    def test_reports_all_errors_together(self, monkeypatch):
        """Test that all validation errors are reported together."""
        # Set up multiple invalid conditions
        monkeypatch.setenv("AVI_TEST_MODE", "1")
        monkeypatch.setenv("MAIN_LLM_API_KEY", "")
        monkeypatch.setenv("MAIN_LLM_MODEL", "")
        monkeypatch.setenv("VECTOR_DB_PROVIDER", "")

        passed, errors = validate_production_config()

        assert passed is False

        # Should report multiple errors
        assert len(errors) >= 3

        # Check specific errors are present
        assert any("AVI_TEST_MODE" in error for error in errors)
        assert any("MAIN_LLM_API_KEY" in error for error in errors)
        assert any("MAIN_LLM_MODEL" in error for error in errors)
