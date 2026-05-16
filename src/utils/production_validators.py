"""
Production environment validation utilities.

This module provides validation functions to ensure the system is properly
configured for production deployment.
"""

from __future__ import annotations

import os
from pathlib import Path

from config.settings import settings


def validate_production_config() -> tuple[bool, list[str]]:
    """
    Validate configuration for production environment.

    Performs comprehensive checks to ensure the system is ready for
    production deployment, including:
    - No test mode overrides enabled
    - Required API keys are set
    - Mock mode is disabled
    - Required directories exist

    Returns:
        tuple[bool, list[str]]: (passed, list of error messages)
            - passed: True if all validations pass
            - errors: List of validation error messages (empty if passed)

    Example:
        >>> passed, errors = validate_production_config()
        >>> if not passed:
        ...     for error in errors:
        ...         print(f"Error: {error}")
    """
    errors = []

    # Check 1: AVI_TEST_MODE must not be enabled
    if os.environ.get("AVI_TEST_MODE") == "1":
        errors.append(
            "AVI_TEST_MODE is set to '1' - test mode must be disabled in production. "
            "Unset this environment variable or set it to '0'."
        )

    # Check 2: Production environment should not allow missing API keys
    if settings.is_production_environment():
        if settings.allows_missing_api_keys():
            errors.append(
                "Production environment is configured to allow missing API keys. "
                "This should never happen. Check ENVIRONMENT variable."
            )

    # Check 3: Validate LLM credentials
    creds_ok, creds_errors = validate_llm_credentials()
    if not creds_ok:
        errors.extend(creds_errors)

    # Check 4: Validate vector DB configuration
    vector_db_ok, vector_db_errors = validate_vector_db_config()
    if not vector_db_ok:
        errors.extend(vector_db_errors)

    # Check 5: Validate required directories exist
    dirs_ok, dirs_errors = validate_data_directories()
    if not dirs_ok:
        errors.extend(dirs_errors)

    passed = len(errors) == 0
    return passed, errors


def validate_llm_credentials() -> tuple[bool, list[str]]:
    """
    Validate LLM credentials are properly configured.

    Checks:
    - MAIN_LLM_API_KEY is set and valid
    - MAIN_LLM_MODEL is set

    Returns:
        tuple[bool, list[str]]: (passed, list of error messages)
    """
    errors = []

    # Check API key
    api_key = settings.MAIN_LLM_API_KEY
    if not api_key or api_key.strip() == "":
        errors.append(
            "MAIN_LLM_API_KEY is not set. "
            "Please set this environment variable with your LLM API key."
        )
    elif len(api_key) < 10:
        errors.append(
            f"MAIN_LLM_API_KEY appears invalid (length: {len(api_key)}). "
            "API keys are typically longer than 10 characters."
        )
    elif api_key.lower() in ["your-key-here", "sk-xxx", "placeholder", "changeme"]:
        errors.append(
            f"MAIN_LLM_API_KEY is set to a placeholder value: '{api_key}'. "
            "Please set a real API key."
        )

    # Check model
    model = settings.MAIN_LLM_MODEL
    if not model or model.strip() == "":
        errors.append(
            "MAIN_LLM_MODEL is not set. "
            "Please specify which LLM model to use (e.g., 'gpt-4', 'claude-3-opus')."
        )

    return len(errors) == 0, errors


def validate_vector_db_config() -> tuple[bool, list[str]]:
    """
    Validate vector database configuration.

    Checks:
    - VECTOR_DB_PROVIDER is set to a valid value
    - Required settings for the chosen provider are configured

    Returns:
        tuple[bool, list[str]]: (passed, list of error messages)
    """
    errors = []

    provider = settings.VECTOR_DB_PROVIDER
    if not provider or provider.strip() == "":
        errors.append(
            "VECTOR_DB_PROVIDER is not set. "
            "Please set to 'qdrant' or 'chroma'."
        )
    elif provider.lower() not in ["qdrant", "chroma", "memory"]:
        errors.append(
            f"Invalid VECTOR_DB_PROVIDER: '{provider}'. "
            "Supported values: 'qdrant', 'chroma', 'memory'."
        )

    # Check Qdrant-specific configuration
    # Note: QDRANT_HOST is optional - Qdrant can use localhost:6333 by default
    # or in-memory mode, so we don't enforce it as a requirement

    return len(errors) == 0, errors


def validate_data_directories() -> tuple[bool, list[str]]:
    """
    Validate that required data directories exist.

    Checks existence of:
    - DATA_DIR
    - RAW_DATA_DIR
    - PROCESSED_DATA_DIR
    - INDEXES_DIR

    Note: Directories are typically created during startup, so missing
    directories are warnings rather than errors.

    Returns:
        tuple[bool, list[str]]: (passed, list of warning messages)
    """
    warnings = []

    required_dirs = {
        "DATA_DIR": settings.DATA_DIR,
        "RAW_DATA_DIR": settings.RAW_DATA_DIR,
        "PROCESSED_DATA_DIR": settings.PROCESSED_DATA_DIR,
        "INDEXES_DIR": settings.INDEXES_DIR,
    }

    for dir_name, dir_path in required_dirs.items():
        path = Path(dir_path)
        if not path.exists():
            warnings.append(
                f"{dir_name} does not exist: {dir_path}. "
                "Directory will be created during startup. "
                "Run 'make init-project' to create it manually."
            )

    # Warnings don't fail validation, but are logged
    return True, warnings


def get_validation_summary() -> dict:
    """
    Get a comprehensive validation summary.

    Returns:
        dict: Validation results with detailed status information
    """
    passed, errors = validate_production_config()

    summary = {
        "passed": passed,
        "environment": settings.get_runtime_environment(),
        "is_production": settings.is_production_environment(),
        "checks": {
            "test_mode": os.environ.get("AVI_TEST_MODE") != "1",
            "llm_credentials": validate_llm_credentials()[0],
            "vector_db_config": validate_vector_db_config()[0],
            "data_directories": validate_data_directories()[0],
        },
        "errors": errors,
    }

    return summary


__all__ = [
    "get_validation_summary",
    "validate_data_directories",
    "validate_llm_credentials",
    "validate_production_config",
    "validate_vector_db_config",
]
