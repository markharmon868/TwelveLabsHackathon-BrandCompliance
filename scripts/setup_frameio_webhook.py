#!/usr/bin/env python3
"""
One-time setup script: registers the Frame.io v4 webhook and saves the
signing secret to your .env file.

Usage:
    python scripts/setup_frameio_webhook.py <ngrok-url>

Example:
    python scripts/setup_frameio_webhook.py https://abc123.ngrok-free.app
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from api.frameio import get_me, get_workspaces, register_webhook


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/setup_frameio_webhook.py <ngrok-url>")
        sys.exit(1)

    ngrok_url = sys.argv[1].rstrip("/")
    webhook_url = f"{ngrok_url}/webhooks/frameio"

    print("Connecting to Frame.io...")
    try:
        me_resp = get_me()
        me = me_resp.get("data", me_resp)
        print(f"Authenticated as: {me.get('name')} ({me.get('email')})")
    except Exception as e:
        print(f"Error: Could not authenticate with Frame.io: {e}")
        print()
        print("Frame.io v4 requires an OAuth 2.0 token from Adobe Developer Console.")
        print("See: https://next.developer.frame.io/platform/docs/getting-started.mdx")
        sys.exit(1)

    account_id = me.get("account_id") or os.getenv("FRAMEIO_ACCOUNT_ID", "").strip()
    if not account_id:
        print("Error: Could not determine account_id.")
        sys.exit(1)

    print(f"\nFetching workspaces for account {account_id}...")
    workspaces = []
    try:
        workspaces = get_workspaces(account_id)
    except Exception as e:
        print(f"Warning: Could not fetch workspaces: {e}")

    # Fall back to FRAMEIO_WORKSPACE_ID from env
    env_workspace_id = os.getenv("FRAMEIO_WORKSPACE_ID", "").strip()
    if not workspaces and env_workspace_id:
        print(f"Using FRAMEIO_WORKSPACE_ID from environment: {env_workspace_id}")
        workspaces = [{"id": env_workspace_id, "name": env_workspace_id}]

    if not workspaces:
        print("Could not auto-discover workspace ID.")
        print()
        print("Find your workspace ID:")
        print("  1. Open app.frame.io and log in")
        print("  2. Open DevTools → Network tab, filter by 'api.frame.io'")
        print("  3. Look for workspace_id in any v4 API response")
        print()
        print("Then add it to .env and re-run:")
        print("  FRAMEIO_WORKSPACE_ID=<uuid>")
        sys.exit(1)

    if len(workspaces) == 1:
        workspace = workspaces[0]
    else:
        print("\nMultiple workspaces found:")
        for i, w in enumerate(workspaces):
            print(f"  [{i}] {w.get('name')} ({w.get('id')})")
        idx = int(input("Select workspace number: "))
        workspace = workspaces[idx]

    workspace_id = workspace["id"]
    workspace_name = workspace.get("name", workspace_id)
    print(f"\nRegistering webhook for workspace: {workspace_name}")
    print(f"Webhook URL: {webhook_url}")

    try:
        webhook_resp = register_webhook(workspace_id, webhook_url, account_id)
    except Exception as e:
        print(f"Error registering webhook: {e}")
        sys.exit(1)

    webhook = webhook_resp.get("data", webhook_resp)
    secret = webhook.get("secret", "")
    webhook_id = webhook.get("id", "")

    print(f"\n✓ Webhook registered! ID: {webhook_id}")

    env_path = Path(__file__).parent.parent / ".env"
    with env_path.open("a") as f:
        if secret:
            f.write(f"\nFRAMEIO_WEBHOOK_SECRET = {secret}\n")
        f.write(f"FRAMEIO_WORKSPACE_ID = {workspace_id}\n")

    if secret:
        print("✓ Signing secret saved to .env")
    else:
        print("⚠ No signing secret returned — signature verification will be skipped.")

    print(f"✓ Workspace ID saved to .env")
    print(f"\nAll set! Upload any video to Frame.io and the audit will trigger automatically.")
    print(f"Watch your backend terminal for '[Frame.io]' log lines.")


if __name__ == "__main__":
    main()
