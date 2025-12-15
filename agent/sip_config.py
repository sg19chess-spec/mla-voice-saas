"""
LiveKit SIP Configuration
=========================
This file contains the SIP trunk and dispatch rule configurations
for connecting Twilio to LiveKit.

You'll need to register these with LiveKit using the CLI or API.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Your LiveKit server info
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "wss://livekit.qnow.in")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")

# ===========================================
# SIP TRUNK CONFIGURATION
# ===========================================
# This tells LiveKit how to receive calls from Twilio

SIP_TRUNK_CONFIG = {
    # Unique ID for this trunk
    "sip_trunk_id": "twilio-mla-trunk",

    # Twilio's SIP addresses (allow calls from these IPs)
    # These are Twilio's signaling IPs - check Twilio docs for latest
    "inbound_addresses": [
        # Twilio's SIP signaling IPs (add your region's IPs)
        "54.172.60.0/30",      # US East
        "54.244.51.0/30",      # US West
        "54.171.127.192/30",   # Ireland
        "35.156.191.128/30",   # Frankfurt
        "54.65.63.192/30",     # Tokyo
        "54.252.254.64/30",    # Sydney
        "54.169.127.128/30",   # Singapore
        "18.228.249.0/30",     # Sao Paulo
    ],

    # Authentication (optional but recommended)
    "inbound_username": "twilio-user",
    "inbound_password": "your-secure-password-here",  # Change this!

    # Outbound calling (if you want to make calls)
    "outbound_address": "your-twilio-sip-uri.sip.twilio.com",
    "outbound_username": "",  # Your Twilio SIP credentials
    "outbound_password": "",
}


# ===========================================
# DISPATCH RULE CONFIGURATION
# ===========================================
# This tells LiveKit which agent to start when a call comes in

DISPATCH_RULE_CONFIG = {
    "rule_id": "mla-complaint-dispatch",

    # Match any incoming call
    "trunk_ids": ["twilio-mla-trunk"],

    # Room name pattern for calls
    # ${caller} and ${called} are variables
    "room_name": "mla-call-${caller}",

    # Room settings
    "room_preset": "default",

    # Metadata to pass to the agent
    "metadata_template": '{"caller_phone": "${caller}", "called_number": "${called}"}'
}


# ===========================================
# PRINT CONFIGURATION
# ===========================================
if __name__ == "__main__":
    print("=" * 60)
    print("LiveKit SIP Configuration")
    print("=" * 60)

    print(f"\nLiveKit Server: {LIVEKIT_URL}")
    print(f"API Key: {LIVEKIT_API_KEY[:10]}..." if LIVEKIT_API_KEY else "API Key: Not set")

    print("\n--- SIP Trunk ---")
    print(f"Trunk ID: {SIP_TRUNK_CONFIG['sip_trunk_id']}")

    print("\n--- Dispatch Rule ---")
    print(f"Rule ID: {DISPATCH_RULE_CONFIG['rule_id']}")
    print(f"Room Pattern: {DISPATCH_RULE_CONFIG['room_name']}")

    print("\n" + "=" * 60)
    print("Next: Use 'lk' CLI to create these configurations")
    print("=" * 60)
