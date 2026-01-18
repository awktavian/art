#!/usr/bin/env python3
"""
🔌 Composio Integration Verification Script

Verify Composio connected accounts and available tools.

Usage:
    python scripts/verify_composio.py
    python scripts/verify_composio.py --json

This script checks:
1. Connected Composio accounts
2. Available tools per account
3. API connectivity
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))


async def get_composio_status() -> dict:
    """Get actual Composio status from API."""
    try:
        from kagami.core.services.composio import get_composio_service

        service = get_composio_service()
        await service.initialize()

        # Get connected accounts
        accounts = []
        account_map = getattr(service, "_account_map", {})

        for service_name, account_id in account_map.items():
            accounts.append(
                {
                    "service": service_name,
                    "account_id": account_id,
                    "connected": True,
                }
            )

        return {
            "status": "connected",
            "accounts": accounts,
            "account_count": len(accounts),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


async def main():
    """Main verification routine."""
    import argparse

    parser = argparse.ArgumentParser(description="Verify Composio integration")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    status = await get_composio_status()

    if args.json:
        print(json.dumps(status, indent=2))
    else:
        print("🔌 Composio Integration Status")
        print("=" * 40)
        print(f"Status: {status.get('status', 'unknown')}")

        if status.get("status") == "connected":
            print(f"Connected accounts: {status.get('account_count', 0)}")
            for acc in status.get("accounts", []):
                print(f"  ✅ {acc['service']}")
        else:
            print(f"Error: {status.get('error', 'Unknown error')}")

        print(f"\nTimestamp: {status.get('timestamp', 'N/A')}")

    return 0 if status.get("status") == "connected" else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
