"""
Setup LiveKit SIP Trunk
=======================
This script creates the SIP trunk and dispatch rules in LiveKit.

Prerequisites:
1. Install LiveKit CLI: pip install livekit-cli
2. Set your LiveKit credentials in .env

Usage: python setup_sip.py
"""

import os
import subprocess
import json
from dotenv import load_dotenv

load_dotenv()

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "").replace("wss://", "https://")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")


def run_lk_command(args: list) -> tuple:
    """Run a LiveKit CLI command."""
    env = os.environ.copy()
    env["LIVEKIT_URL"] = LIVEKIT_URL
    env["LIVEKIT_API_KEY"] = LIVEKIT_API_KEY
    env["LIVEKIT_API_SECRET"] = LIVEKIT_API_SECRET

    try:
        result = subprocess.run(
            ["lk"] + args,
            capture_output=True,
            text=True,
            env=env
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return -1, "", "LiveKit CLI 'lk' not found. Install with: pip install livekit-cli"


def create_sip_trunk():
    """Create the SIP trunk for Twilio."""
    print("\n[1/2] Creating SIP Trunk...")

    trunk_config = {
        "sip_trunk_id": "twilio-mla-trunk",
        "name": "Twilio MLA Trunk",
        "inbound": {
            "allowed_addresses": [
                # Twilio's SIP IPs - add more as needed
                "0.0.0.0/0"  # Allow all for testing (restrict in production!)
            ],
            "allowed_numbers": [],  # Empty = allow all numbers
        }
    }

    # Save config to temp file
    config_file = "/tmp/sip_trunk.json"
    with open(config_file, "w") as f:
        json.dump(trunk_config, f)

    code, out, err = run_lk_command(["sip", "trunk", "create", config_file])

    if code == 0:
        print(f"  ✅ SIP Trunk created!")
        print(f"     {out}")
    else:
        print(f"  ❌ Failed: {err or out}")


def create_dispatch_rule():
    """Create the dispatch rule for routing calls."""
    print("\n[2/2] Creating Dispatch Rule...")

    rule_config = {
        "rule_id": "mla-complaint-dispatch",
        "trunk_ids": ["twilio-mla-trunk"],
        "dispatch_rule": {
            "dispatch_rule_direct": {
                "room_name": "mla-call-room",
                "pin": ""  # No PIN required
            }
        },
        "hide_phone_number": False
    }

    # Save config to temp file
    config_file = "/tmp/dispatch_rule.json"
    with open(config_file, "w") as f:
        json.dump(rule_config, f)

    code, out, err = run_lk_command(["sip", "dispatch-rule", "create", config_file])

    if code == 0:
        print(f"  ✅ Dispatch Rule created!")
        print(f"     {out}")
    else:
        print(f"  ❌ Failed: {err or out}")


def list_sip_config():
    """List current SIP configuration."""
    print("\nCurrent SIP Configuration:")
    print("-" * 40)

    print("\nTrunks:")
    code, out, err = run_lk_command(["sip", "trunk", "list"])
    print(out if code == 0 else f"Error: {err}")

    print("\nDispatch Rules:")
    code, out, err = run_lk_command(["sip", "dispatch-rule", "list"])
    print(out if code == 0 else f"Error: {err}")


def main():
    print("=" * 60)
    print("LiveKit SIP Setup")
    print("=" * 60)

    # Check configuration
    if not LIVEKIT_URL or not LIVEKIT_API_KEY:
        print("❌ Error: LIVEKIT_URL and LIVEKIT_API_KEY must be set in .env")
        return

    print(f"\nLiveKit Server: {LIVEKIT_URL}")

    # Check if lk CLI is installed
    code, _, err = run_lk_command(["--version"])
    if code != 0:
        print(f"\n❌ {err}")
        print("\nInstall LiveKit CLI:")
        print("  pip install livekit-cli")
        print("\nOr download from: https://github.com/livekit/livekit-cli")
        return

    print("\nWhat would you like to do?")
    print("1. Create SIP Trunk and Dispatch Rule")
    print("2. List current SIP configuration")
    print("3. Exit")

    choice = input("\nEnter choice (1/2/3): ").strip()

    if choice == "1":
        create_sip_trunk()
        create_dispatch_rule()
        print("\n" + "=" * 60)
        print("Setup complete! Now configure Twilio.")
        print("=" * 60)
    elif choice == "2":
        list_sip_config()
    else:
        print("Exiting.")


if __name__ == "__main__":
    main()
