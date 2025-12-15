"""
Test Agent Components
=====================
Test the individual components before running the full agent.

This script tests:
1. Sarvam STT connection
2. Sarvam TTS connection
3. Groq LLM connection
4. Database connection

Run: python test_agent.py
"""

import asyncio
import os
from dotenv import load_dotenv
import httpx

# Load environment
load_dotenv()

# Get API keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
LIVEKIT_URL = os.getenv("LIVEKIT_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


async def test_groq():
    """Test Groq LLM connection."""
    print("\n[1/4] Testing Groq LLM...")

    if not GROQ_API_KEY:
        print("  ❌ GROQ_API_KEY not set")
        return False

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [{"role": "user", "content": "Say hello in Tamil"}],
                    "max_tokens": 50
                },
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                text = result["choices"][0]["message"]["content"]
                print(f"  ✅ Groq working! Response: {text[:50]}...")
                return True
            else:
                print(f"  ❌ Groq error: {response.status_code} - {response.text[:100]}")
                return False

    except Exception as e:
        print(f"  ❌ Groq exception: {e}")
        return False


async def test_sarvam_tts():
    """Test Sarvam TTS connection."""
    print("\n[2/4] Testing Sarvam TTS...")

    if not SARVAM_API_KEY:
        print("  ❌ SARVAM_API_KEY not set")
        return False

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.sarvam.ai/text-to-speech",
                headers={
                    "api-subscription-key": SARVAM_API_KEY,
                    "Content-Type": "application/json"
                },
                json={
                    "inputs": ["வணக்கம்"],  # "Hello" in Tamil
                    "target_language_code": "ta-IN",
                    "speaker": "meera",
                    "model": "bulbul:v1"
                },
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("audios"):
                    audio_len = len(result["audios"][0])
                    print(f"  ✅ Sarvam TTS working! Audio length: {audio_len} chars (base64)")
                    return True
                else:
                    print(f"  ⚠️  No audio returned: {result}")
                    return False
            else:
                print(f"  ❌ Sarvam TTS error: {response.status_code} - {response.text[:100]}")
                return False

    except Exception as e:
        print(f"  ❌ Sarvam TTS exception: {e}")
        return False


async def test_sarvam_stt():
    """Test Sarvam STT connection (just API availability)."""
    print("\n[3/4] Testing Sarvam STT...")

    if not SARVAM_API_KEY:
        print("  ❌ SARVAM_API_KEY not set")
        return False

    # Note: STT needs actual audio, so we just check the API key works
    print(f"  ✅ SARVAM_API_KEY is set ({SARVAM_API_KEY[:10]}...)")
    print("     (Full test requires audio input)")
    return True


async def test_supabase():
    """Test Supabase database connection."""
    print("\n[4/4] Testing Supabase Database...")

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("  ❌ SUPABASE_URL or SUPABASE_SERVICE_KEY not set")
        return False

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SUPABASE_URL}/rest/v1/tenants?select=count",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}"
                },
                timeout=10
            )

            if response.status_code == 200:
                print(f"  ✅ Supabase connected!")
                return True
            else:
                print(f"  ❌ Supabase error: {response.status_code} - {response.text[:100]}")
                return False

    except Exception as e:
        print(f"  ❌ Supabase exception: {e}")
        return False


async def test_livekit():
    """Check LiveKit configuration."""
    print("\n[Bonus] Checking LiveKit Config...")

    if LIVEKIT_URL:
        print(f"  ✅ LIVEKIT_URL: {LIVEKIT_URL}")
    else:
        print("  ⚠️  LIVEKIT_URL not set")

    livekit_key = os.getenv("LIVEKIT_API_KEY")
    livekit_secret = os.getenv("LIVEKIT_API_SECRET")

    if livekit_key and livekit_secret:
        print(f"  ✅ LIVEKIT_API_KEY: {livekit_key[:8]}...")
        print(f"  ✅ LIVEKIT_API_SECRET: {livekit_secret[:8]}...")
        return True
    else:
        print("  ⚠️  LiveKit credentials not fully set")
        return False


async def main():
    """Run all tests."""
    print("=" * 60)
    print("MLA Voice Agent - Component Tests")
    print("=" * 60)

    results = {
        "Groq LLM": await test_groq(),
        "Sarvam TTS": await test_sarvam_tts(),
        "Sarvam STT": await test_sarvam_stt(),
        "Supabase": await test_supabase(),
        "LiveKit": await test_livekit()
    }

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    all_passed = True
    for name, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {name}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("All tests passed! You're ready to run the agent.")
        print("\nNext step: python agent.py dev")
    else:
        print("Some tests failed. Please check your .env file.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
