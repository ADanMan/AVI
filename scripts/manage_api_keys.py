#!/usr/bin/env python3
"""
CLI tool for managing API keys.

Usage:
    python scripts/manage_api_keys.py list
    python scripts/manage_api_keys.py create --name "My Key" --role user
    python scripts/manage_api_keys.py revoke <key_hash>
    python scripts/manage_api_keys.py delete <key_hash>
"""

import argparse
import sys
from pathlib import Path


# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.auth import APIKeyManager, Role


def format_timestamp(dt):
    """Format datetime for display."""
    if dt is None:
        return "Never"
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def cmd_list(args):
    """List all API keys."""
    manager = APIKeyManager(storage_path=args.storage_path)
    keys = manager.list_keys()

    if not keys:
        print("No API keys found.")
        return 0

    print(
        f"\n{'Status':<10} {'Name':<25} {'Role':<10} {'Created':<20} {'Expires':<20} {'Last Used':<20}"
    )
    print("=" * 115)

    for key in keys:
        status = "✅ Active" if key.is_active else "❌ Revoked"
        if key.is_expired():
            status = "⏰ Expired"

        print(
            f"{status:<10} {key.name:<25} {key.role.value:<10} "
            f"{format_timestamp(key.created_at):<20} "
            f"{format_timestamp(key.expires_at):<20} "
            f"{format_timestamp(key.last_used):<20}"
        )

        if args.verbose:
            print(f"  Hash: {key.key_hash[:16]}...")
            if key.metadata:
                print(f"  Metadata: {key.metadata}")

    print(f"\nTotal: {len(keys)} keys")
    active_count = sum(1 for k in keys if k.is_active and not k.is_expired())
    print(f"Active: {active_count}")

    return 0


def cmd_create(args):
    """Create a new API key."""
    manager = APIKeyManager(storage_path=args.storage_path)

    try:
        role = Role(args.role)
    except ValueError:
        print(f"❌ Invalid role: {args.role}")
        print(f"Valid roles: {', '.join(r.value for r in Role)}")
        return 1

    try:
        plaintext_key, api_key = manager.create_api_key(
            name=args.name,
            role=role,
            expires_days=args.expires_days,
            metadata={"created_by": "manage_api_keys_script"},
        )

        print("\n" + "=" * 80)
        print("✅ API Key Created Successfully!")
        print("=" * 80)
        print(f"\nName: {api_key.name}")
        print(f"Role: {api_key.role.value}")
        print(f"Created: {format_timestamp(api_key.created_at)}")
        print(f"Expires: {format_timestamp(api_key.expires_at)}")

        print("\n" + "!" * 80)
        print("IMPORTANT: Save this API key securely - it won't be shown again!")
        print("!" * 80)
        print(f"\nAPI Key: {plaintext_key}")
        print("\n" + "=" * 80)

        return 0

    except Exception as e:
        print(f"\n❌ Error creating API key: {e}")
        return 1


def cmd_revoke(args):
    """Revoke an API key."""
    manager = APIKeyManager(storage_path=args.storage_path)

    # Find key by partial hash
    keys = manager.list_keys()
    matching_keys = [k for k in keys if k.key_hash.startswith(args.key_hash)]

    if not matching_keys:
        print(f"❌ No key found with hash starting with: {args.key_hash}")
        return 1

    if len(matching_keys) > 1:
        print(f"❌ Multiple keys found with hash starting with: {args.key_hash}")
        print("Please provide a longer hash prefix:")
        for key in matching_keys:
            print(f"  - {key.name}: {key.key_hash[:16]}...")
        return 1

    key = matching_keys[0]

    if not key.is_active:
        print(f"⚠️  Key '{key.name}' is already revoked")
        return 0

    # Confirm revocation
    if not args.yes:
        print("\n⚠️  About to revoke key:")
        print(f"  Name: {key.name}")
        print(f"  Role: {key.role.value}")
        print(f"  Hash: {key.key_hash[:16]}...")

        response = input("\nAre you sure? [y/N]: ")
        if response.lower() not in ["y", "yes"]:
            print("❌ Cancelled")
            return 1

    success = manager.revoke_key(key.key_hash)

    if success:
        print(f"✅ API key '{key.name}' has been revoked")
        return 0
    else:
        print("❌ Failed to revoke key")
        return 1


def cmd_delete(args):
    """Permanently delete an API key."""
    manager = APIKeyManager(storage_path=args.storage_path)

    # Find key by partial hash
    keys = manager.list_keys()
    matching_keys = [k for k in keys if k.key_hash.startswith(args.key_hash)]

    if not matching_keys:
        print(f"❌ No key found with hash starting with: {args.key_hash}")
        return 1

    if len(matching_keys) > 1:
        print(f"❌ Multiple keys found with hash starting with: {args.key_hash}")
        print("Please provide a longer hash prefix:")
        for key in matching_keys:
            print(f"  - {key.name}: {key.key_hash[:16]}...")
        return 1

    key = matching_keys[0]

    # Confirm deletion
    if not args.yes:
        print("\n⚠️  About to PERMANENTLY DELETE key:")
        print(f"  Name: {key.name}")
        print(f"  Role: {key.role.value}")
        print(f"  Hash: {key.key_hash[:16]}...")
        print("\n⚠️  This action CANNOT be undone!")

        response = input("\nAre you sure? [y/N]: ")
        if response.lower() not in ["y", "yes"]:
            print("❌ Cancelled")
            return 1

    success = manager.delete_key(key.key_hash)

    if success:
        print(f"✅ API key '{key.name}' has been permanently deleted")
        return 0
    else:
        print("❌ Failed to delete key")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Manage AVI API keys",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--storage-path",
        type=str,
        default=None,
        help="Custom path for API key storage",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # List command
    list_parser = subparsers.add_parser("list", help="List all API keys")
    list_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show detailed information"
    )

    # Create command
    create_parser = subparsers.add_parser("create", help="Create a new API key")
    create_parser.add_argument("--name", type=str, required=True, help="Name for the API key")
    create_parser.add_argument(
        "--role",
        type=str,
        default="user",
        choices=["admin", "user", "readonly"],
        help="Role for the API key (default: user)",
    )
    create_parser.add_argument(
        "--expires-days",
        type=int,
        default=None,
        help="Number of days until expiration (default: never)",
    )

    # Revoke command
    revoke_parser = subparsers.add_parser("revoke", help="Revoke an API key")
    revoke_parser.add_argument("key_hash", type=str, help="Key hash (or prefix) to revoke")
    revoke_parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Permanently delete an API key")
    delete_parser.add_argument("key_hash", type=str, help="Key hash (or prefix) to delete")
    delete_parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "list": cmd_list,
        "create": cmd_create,
        "revoke": cmd_revoke,
        "delete": cmd_delete,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
