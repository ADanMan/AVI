#!/usr/bin/env python3
"""
Bootstrap script for creating the first admin API key.

Usage:
    python scripts/bootstrap_admin_key.py [--name NAME] [--expires-days DAYS]

Example:
    python scripts/bootstrap_admin_key.py --name "Initial Admin" --expires-days 365
"""

import argparse
import sys
from pathlib import Path


# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.auth import APIKeyManager, Role
from src.utils.logger import logger


def main():
    parser = argparse.ArgumentParser(
        description="Bootstrap first admin API key for AVI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create admin key with default name
  python scripts/bootstrap_admin_key.py

  # Create admin key with custom name
  python scripts/bootstrap_admin_key.py --name "Production Admin"

  # Create admin key that expires in 180 days
  python scripts/bootstrap_admin_key.py --name "Temp Admin" --expires-days 180

IMPORTANT: Save the API key shown after creation - it won't be shown again!
        """,
    )

    parser.add_argument(
        "--name",
        type=str,
        default="Bootstrap Admin",
        help="Name for the admin key (default: Bootstrap Admin)",
    )

    parser.add_argument(
        "--expires-days",
        type=int,
        default=None,
        help="Number of days until key expires (default: never expires)",
    )

    parser.add_argument(
        "--storage-path",
        type=str,
        default=None,
        help="Custom path for API key storage (default: data/security/api_keys.json)",
    )

    args = parser.parse_args()

    try:
        # Initialize API key manager
        manager = APIKeyManager(storage_path=args.storage_path)

        # Check if admin keys already exist
        existing_keys = manager.list_keys()
        admin_keys = [k for k in existing_keys if k.role == Role.ADMIN and k.is_active]

        if admin_keys:
            print("⚠️  WARNING: Active admin API keys already exist:")
            for key in admin_keys:
                print(f"  - {key.name} (created: {key.created_at.strftime('%Y-%m-%d %H:%M')})")

            response = input("\nDo you want to create another admin key? [y/N]: ")
            if response.lower() not in ["y", "yes"]:
                print("❌ Cancelled")
                return 1

        # Create admin API key
        print(f"\n🔑 Creating admin API key '{args.name}'...")

        plaintext_key, api_key = manager.create_api_key(
            name=args.name,
            role=Role.ADMIN,
            expires_days=args.expires_days,
            metadata={"created_by": "bootstrap_script"},
        )

        # Display success message
        print("\n" + "=" * 80)
        print("✅ Admin API Key Created Successfully!")
        print("=" * 80)
        print(f"\nName: {api_key.name}")
        print(f"Role: {api_key.role.value}")
        print(f"Created: {api_key.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        if api_key.expires_at:
            print(f"Expires: {api_key.expires_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        else:
            print("Expires: Never")

        print("\n" + "!" * 80)
        print("IMPORTANT: Save this API key securely - it won't be shown again!")
        print("!" * 80)
        print(f"\nAPI Key: {plaintext_key}")
        print("\n" + "=" * 80)

        # Show usage instructions
        print("\n📝 Usage Instructions:")
        print("\n1. Save the API key in your environment:")
        print(f"   export AVI_API_KEY={plaintext_key}")

        print("\n2. Or add to your .env file:")
        print(f"   AVI_API_KEY={plaintext_key}")

        print("\n3. Use in API requests with X-API-Key header:")
        print(f'   curl -H "X-API-Key: {plaintext_key}" http://localhost:8000/admin/keys')

        print("\n4. For production, enable required authentication:")
        print("   export REQUIRE_API_KEY=true")

        print("\n" + "=" * 80)

        logger.info(f"Bootstrap admin key created: {api_key.name}")
        return 0

    except Exception as e:
        print(f"\n❌ Error creating admin key: {e}")
        logger.error(f"Bootstrap admin key creation failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
