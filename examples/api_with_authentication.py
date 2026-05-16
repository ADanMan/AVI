#!/usr/bin/env python3
"""
Example: Using AVI API with Authentication

This example demonstrates how to:
1. Create API keys for different roles
2. Make authenticated requests to AVI endpoints
3. Handle authentication errors
"""

import requests
import sys
from pathlib import Path

# Add project root to path to import from scripts
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.api.auth import APIKeyManager, Role


# API Configuration
API_BASE_URL = "http://localhost:8000/api/v1"


def create_api_keys():
    """Create API keys for testing."""
    print("=" * 60)
    print("Creating API Keys")
    print("=" * 60)

    manager = APIKeyManager()

    # Create different role keys
    admin_key, admin_obj = manager.create_api_key(
        name="Admin Key - Full Access",
        role=Role.ADMIN,
        expires_days=90
    )

    user_key, user_obj = manager.create_api_key(
        name="User Key - Standard Access",
        role=Role.USER,
        expires_days=30
    )

    readonly_key, readonly_obj = manager.create_api_key(
        name="Readonly Key - Read Only",
        role=Role.READONLY,
        expires_days=7
    )

    print(f"\n✅ ADMIN Key: {admin_key}")
    print(f"   - Full access to all endpoints")
    print(f"   - Can manage API keys")
    print(f"   - Expires in 90 days")

    print(f"\n✅ USER Key: {user_key}")
    print(f"   - Can query, upload, configure")
    print(f"   - Cannot manage API keys")
    print(f"   - Expires in 30 days")

    print(f"\n✅ READONLY Key: {readonly_key}")
    print(f"   - Can only read data (health, stats, monitoring)")
    print(f"   - Cannot modify anything")
    print(f"   - Expires in 7 days")

    print("\n⚠️  Save these keys securely - they won't be shown again!")

    return {
        "admin": admin_key,
        "user": user_key,
        "readonly": readonly_key
    }


def example_query_with_auth(api_key: str, query_text: str):
    """Example: Process a query with authentication."""
    print("\n" + "=" * 60)
    print("Example: Authenticated Query Request")
    print("=" * 60)

    url = f"{API_BASE_URL}/query"
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }
    data = {
        "query": query_text,
        "use_cache": True
    }

    print(f"\nSending query: '{query_text}'")
    print(f"Using API key: {api_key[:25]}...")

    try:
        response = requests.post(url, json=data, headers=headers)

        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ Success! Response:")
            print(f"   - Response: {result.get('response', '')[:100]}...")
            print(f"   - Processing time: {result.get('processing_time', 0):.2f}s")
        elif response.status_code == 401:
            print(f"\n❌ Authentication failed: {response.json().get('detail')}")
        elif response.status_code == 403:
            print(f"\n❌ Insufficient permissions: {response.json().get('detail')}")
        else:
            print(f"\n❌ Error {response.status_code}: {response.text}")

    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to API server. Make sure it's running on localhost:8000")


def example_chat_with_auth(api_key: str, message: str):
    """Example: Chat request with authentication."""
    print("\n" + "=" * 60)
    print("Example: Authenticated Chat Request")
    print("=" * 60)

    url = f"{API_BASE_URL}/chat/complete"
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }
    data = {
        "message": message,
        "enable_avi": True,
        "model": "gpt-4o-mini"
    }

    print(f"\nSending message: '{message}'")
    print(f"Using API key: {api_key[:25]}...")

    try:
        response = requests.post(url, json=data, headers=headers)

        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ Success!")
            print(f"   - Message: {result.get('message', '')[:150]}...")
            print(f"   - Filtered: {result.get('filtered', False)}")
            print(f"   - Safety score: {result.get('safety_scores', {}).get('overall', 0):.2f}")
        elif response.status_code == 401:
            print(f"\n❌ Authentication failed: {response.json().get('detail')}")
        else:
            print(f"\n❌ Error {response.status_code}: {response.text}")

    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to API server")


def example_readonly_access(api_key: str):
    """Example: Readonly access to monitoring data."""
    print("\n" + "=" * 60)
    print("Example: Readonly Access - Health Check")
    print("=" * 60)

    url = f"{API_BASE_URL}/health"
    headers = {
        "X-API-Key": api_key
    }

    print(f"\nChecking system health...")
    print(f"Using READONLY key: {api_key[:25]}...")

    try:
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ System Status: {result.get('status')}")
            print(f"   Components:")
            for component, status in result.get('components', {}).items():
                print(f"      - {component}: {status}")
        else:
            print(f"\n❌ Error {response.status_code}: {response.text}")

    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to API server")


def example_permission_denied(readonly_key: str):
    """Example: Attempting write operation with readonly key."""
    print("\n" + "=" * 60)
    print("Example: Permission Denied (Readonly trying to upload)")
    print("=" * 60)

    url = f"{API_BASE_URL}/cache/clear"
    headers = {
        "X-API-Key": readonly_key
    }

    print(f"\nAttempting to clear cache with READONLY key...")
    print(f"This should fail with 403 Forbidden")

    try:
        response = requests.post(url, headers=headers)

        if response.status_code == 403:
            print(f"\n✅ Expected behavior: {response.json().get('detail')}")
            print("   Readonly keys cannot perform write operations")
        elif response.status_code == 200:
            print("\n⚠️  Unexpected: Operation succeeded (should have been denied)")
        else:
            print(f"\n❌ Error {response.status_code}: {response.text}")

    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to API server")


def example_without_auth():
    """Example: Request without authentication (dev mode)."""
    print("\n" + "=" * 60)
    print("Example: Request Without Authentication")
    print("=" * 60)
    print("\nNote: This works when REQUIRE_API_KEY=false (development mode)")
    print("      In production, set REQUIRE_API_KEY=true to enforce auth")

    url = f"{API_BASE_URL}/health"

    print(f"\nChecking health without API key...")

    try:
        response = requests.get(url)  # No X-API-Key header

        if response.status_code == 200:
            print("\n✅ Success! Authentication is optional in dev mode")
            print("   Set REQUIRE_API_KEY=true to enforce authentication")
        elif response.status_code == 401:
            print("\n✅ Authentication required (production mode)")
        else:
            print(f"\n❌ Error {response.status_code}: {response.text}")

    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to API server")


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("AVI API Authentication Examples")
    print("=" * 60)
    print("\nThis script demonstrates how to use AVI API with authentication")
    print("Make sure the AVI server is running: python main.py")

    # Create API keys
    keys = create_api_keys()

    # Example 1: Query with USER key
    example_query_with_auth(
        keys["user"],
        "What is AVI and how does it work?"
    )

    # Example 2: Chat with USER key
    example_chat_with_auth(
        keys["user"],
        "Hello! Can you explain content filtering?"
    )

    # Example 3: Health check with READONLY key
    example_readonly_access(keys["readonly"])

    # Example 4: Permission denied
    example_permission_denied(keys["readonly"])

    # Example 5: No authentication (dev mode)
    example_without_auth()

    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Test with REQUIRE_API_KEY=true in production")
    print("2. Use 'python scripts/manage_api_keys.py' to manage keys")
    print("3. See docs/AUTHENTICATION.md for more details")
    print()


if __name__ == "__main__":
    main()
