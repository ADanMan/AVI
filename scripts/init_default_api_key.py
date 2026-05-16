#!/usr/bin/env python3
"""
Initialize default API key for Docker deployments.
This script automatically creates a default admin API key if no admin keys exist.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.auth import APIKeyManager, Role
from src.utils.logger import logger

DEFAULT_KEY_NAME = "Docker Default Admin"
DEFAULT_API_KEY = os.getenv("DEFAULT_API_KEY", None)  # Optional: use predefined key


def init_default_api_key() -> str | None:
    """
    Initialize default API key if no admin keys exist.

    Returns:
        The plaintext API key if created, None if admin key already exists
    """
    auth_manager = APIKeyManager()

    # Check if any admin keys already exist
    all_keys = auth_manager.list_keys()
    admin_keys = [key for key in all_keys if key.role == Role.ADMIN and key.is_active]

    if admin_keys:
        logger.info(f"Admin API keys already exist ({len(admin_keys)} active). Skipping default key creation.")

        # Show helpful message about existing keys
        print("\n" + "=" * 80)
        print("ℹ️  EXISTING API KEYS DETECTED")
        print("=" * 80)
        print(f"\nFound {len(admin_keys)} active admin API key(s).")
        print("\nTo view your API keys:")
        print("  • Check saved key: cat /app/data/.default_api_key")
        print("  • List all keys: python scripts/manage_api_keys.py list")
        print("  • Create new key: python scripts/bootstrap_admin_key.py")
        print("\nTo use with API requests:")
        print("  curl -H 'X-API-Key: YOUR_KEY' http://localhost:8000/api/v1/health")
        print("=" * 80 + "\n")

        return None

    logger.info("No admin API keys found. Creating default admin key...")

    # Create default admin key
    try:
        # Generate random key (custom DEFAULT_API_KEY not supported for security)
        plaintext_key, api_key = auth_manager.create_api_key(
            name=DEFAULT_KEY_NAME,
            role=Role.ADMIN,
            metadata={"auto_generated": True, "default_key": True}
        )

        # Log the key prominently
        print("\n" + "=" * 80)
        print("🔑 DEFAULT ADMIN API KEY CREATED")
        print("=" * 80)
        print(f"\nAPI Key Name: {DEFAULT_KEY_NAME}")
        print(f"API Key Role: ADMIN")
        print(f"\nYour API Key (save this, it won't be shown again):")
        print(f"\n    {plaintext_key}\n")
        print("=" * 80)
        print("\nTo use this key, include it in the X-API-Key header:")
        print(f"    curl -H 'X-API-Key: {plaintext_key}' http://localhost:8000/api/v1/health")
        print("\nOr set it as an environment variable:")
        print(f"    export AVI_API_KEY={plaintext_key}")
        print("=" * 80 + "\n")

        logger.info(f"Default admin API key created successfully: {DEFAULT_KEY_NAME}")

        return plaintext_key

    except Exception as e:
        logger.error(f"Failed to create default API key: {e}")
        return None


def main():
    """Main entry point"""
    try:
        api_key = init_default_api_key()

        if api_key:
            # Optionally write to a file for docker-compose to read
            key_file = Path("/app/data/.default_api_key")
            if key_file.parent.exists():
                try:
                    key_file.write_text(api_key)
                    key_file.chmod(0o600)  # Secure permissions
                    logger.info(f"API key saved to {key_file}")
                except Exception as e:
                    logger.warning(f"Could not write API key to file: {e}")

            sys.exit(0)
        else:
            # Admin key already exists, this is fine
            sys.exit(0)

    except Exception as e:
        logger.error(f"Error during API key initialization: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
