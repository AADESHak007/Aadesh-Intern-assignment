import argparse
import asyncio
import secrets
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from db import connect_db, disconnect_db, execute, fetch, fetchrow
DEFAULT_QUOTA = 125

async def create_key(label: str, quota: int):
    api_key = f"ak_{secrets.token_urlsafe(32)}"
    query = """
        INSERT INTO api_keys (api_key, label, quota)
        VALUES ($1, $2, $3)
        RETURNING id, api_key, label, quota
    """
    row = await fetchrow(query, api_key, label, quota)
    print(f"[OK] Created API Key successfully!")
    print(f"ID: {row['id']}")
    print(f"Label: {row['label']}")
    print(f"Quota: {row['quota']}")
    print(f"Key: {row['api_key']}")
    print("\n[!] SAVE THIS KEY. YOU WILL NOT BE ABLE TO SEE IT AGAIN.")

async def list_keys():
    query = "SELECT id, label, revoked, usage_count, quota, tokens, last_used_at FROM api_keys ORDER BY created_at DESC"
    rows = await fetch(query)
    print(f"Found {len(rows)} API Keys:\n")
    for row in rows:
        status = "[REVOKED]" if row['revoked'] else "[ACTIVE]"
        print(f"ID: {row['id']} | Label: {row['label']} | Status: {status}")
        print(f"Usage: {row['usage_count']}/{row['quota'] if row['quota'] else 'Unlimited'} | Tokens: {row['tokens']:.2f}")
        print(f"Last Used: {row['last_used_at']}\n")

async def revoke_key(key_id: str):
    query = "UPDATE api_keys SET revoked = TRUE WHERE id = $1 RETURNING id"
    row = await fetchrow(query, key_id)
    if row:
        print(f"[OK] Key {key_id} has been revoked.")
    else:
        print(f"[FAIL] Key {key_id} not found.")

async def main():
    parser = argparse.ArgumentParser(description="API Key Management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create a new API key")
    create_parser.add_argument("--label", type=str, help="Label for the key (e.g., 'Agent A')")
    create_parser.add_argument(
        "--quota",
        type=int,
        default=DEFAULT_QUOTA,
        help=f"Maximum number of requests allowed (default: {DEFAULT_QUOTA})",
    )

    subparsers.add_parser("list", help="List all API keys")

    revoke_parser = subparsers.add_parser("revoke", help="Revoke an API key")
    revoke_parser.add_argument("id", type=str, help="ID of the API key to revoke")

    args = parser.parse_args()

    await connect_db()
    try:
        if args.command == "create":
            await create_key(args.label, args.quota)
        elif args.command == "list":
            await list_keys()
        elif args.command == "revoke":
            await revoke_key(args.id)
    finally:
        await disconnect_db()

if __name__ == "__main__":
    asyncio.run(main())
