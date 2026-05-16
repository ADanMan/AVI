"""
Pytest configuration and fixtures for E2E tests
"""
import time
from collections.abc import Generator

import pytest
import requests


@pytest.fixture(scope="session")
def api_base_url() -> str:
    """Base URL for the API"""
    return "http://localhost:8000"


@pytest.fixture(scope="session")
def wait_for_api(api_base_url: str) -> Generator:
    """Wait for API to be ready"""
    max_retries = 30
    retry_delay = 2

    for i in range(max_retries):
        try:
            response = requests.get(f"{api_base_url}/health", timeout=5)
            if response.status_code == 200:
                print(f"\n✓ API is ready at {api_base_url}")
                yield
                return
        except requests.exceptions.RequestException:
            if i < max_retries - 1:
                print(f"Waiting for API... ({i+1}/{max_retries})")
                time.sleep(retry_delay)
            else:
                pytest.fail(f"API not available after {max_retries} retries")


@pytest.fixture
def api_client(api_base_url: str, wait_for_api) -> requests.Session:
    """HTTP client for API requests"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    return session
