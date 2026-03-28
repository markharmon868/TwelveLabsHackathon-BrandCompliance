#!/usr/bin/env python3
"""
One-time setup script: registers the Frame.io webhook and saves the
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

from api.frameio import get_me, get_teams, register_webhook

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/setup_frameio_webhook.py <ngrok-url>")
        sys.exit(1)

    ngrok_url = sys.argv[1].rstrip("/")
    webhook_url = f"{ngrok_url}/webhooks/frameio"

    print(f"Connecting to Frame.io...")
    try:
        me = get_me()
        print(f"Authenticated as: {me.get('name')} ({me.get('email')})")
    except Exception as e:
        print(f"Error: Could not authenticate with Frame.io: {e}")
        sys.exit(1)

    print(f"\nFetching teams...")
    try:
        teams = get_teams()
    except Exception as e:
        print(f"Error: Could not fetch teams: {e}")
        sys.exit(1)

    if not teams:
        print("No teams found for this account.")
        sys.exit(1)

    # Use first team (or let user pick if multiple)
    if len(teams) == 1:
        team = teams[0]
    else:
        print("\nMultiple teams found:")
        for i, t in enumerate(teams):
            print(f"  [{i}] {t.get('name')} ({t.get('id')})")
        idx = int(input("Select team number: "))
        team = teams[idx]

    team_id = team["id"]
    team_name = team.get("name", team_id)
    print(f"\nRegistering webhook for team: {team_name}")
    print(f"Webhook URL: {webhook_url}")

    try:
        webhook = register_webhook(team_id, webhook_url)
    except Exception as e:
        print(f"Error registering webhook: {e}")
        sys.exit(1)

    secret = webhook.get("secret") or webhook.get("signing_secret", "")
    webhook_id = webhook.get("id", "")

    print(f"\n✓ Webhook registered! ID: {webhook_id}")

    if secret:
        # Append secret to .env
        env_path = Path(__file__).parent.parent / ".env"
        with env_path.open("a") as f:
            f.write(f"\nFRAMEIO_WEBHOOK_SECRET = {secret}\n")
            f.write(f"FRAMEIO_TEAM_ID = {team_id}\n")
        print(f"✓ Signing secret saved to .env")
        print(f"✓ Team ID saved to .env")
    else:
        print(f"⚠ No signing secret returned — signature verification will be skipped.")
        print(f"  Team ID: {team_id} — add FRAMEIO_TEAM_ID={team_id} to your .env manually.")

    print(f"\nAll set! Upload any video to Frame.io and the audit will trigger automatically.")
    print(f"Watch your backend terminal for '[Frame.io]' log lines.")

if __name__ == "__main__":
    main()
