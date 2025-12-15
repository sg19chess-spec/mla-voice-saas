"""
Sarvam AI Text-to-Speech (TTS) Plugin
=====================================
Converts text to spoken audio using Sarvam's 'bulbul' model.

HOW IT WORKS:
1. Receives text from the AI agent
2. Sends to Sarvam API
3. Returns audio bytes to play to the caller

SUPPORTED LANGUAGES:
- Tamil, Hindi, English, Telugu, Kannada, Malayalam, and more!

VOICE OPTIONS:
- Multiple voices per language
- Natural sounding Indian accents
"""

import httpx
import base64
import io
from typing import Optional, AsyncGenerator
import os


class SarvamTTS:
    """
    Sarvam AI Text-to-Speech client.

    Usage:
        tts = SarvamTTS(api_key="your-key")
        audio_bytes = await tts.synthesize("வணக்கம்!", language="ta-IN")
    """

    API_URL = "https://api.sarvam.ai/text-to-speech"

    # Available voices for each language
    VOICES = {
        "ta-IN": ["meera"],      # Tamil
        "hi-IN": ["arvind"],     # Hindi
        "en-IN": ["arvind"],     # English (Indian)
        "te-IN": ["meera"],      # Telugu
        "kn-IN": ["meera"],      # Kannada
        "ml-IN": ["meera"],      # Malayalam
    }

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Sarvam TTS client.

        Args:
            api_key: Sarvam API key. If not provided, reads from SARVAM_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("SARVAM_API_KEY")
        if not self.api_key:
            raise ValueError("SARVAM_API_KEY not provided")

        self.client = httpx.AsyncClient(timeout=30.0)

    async def synthesize(
        self,
        text: str,
        language: str = "ta-IN",
        speaker: Optional[str] = None,
        sample_rate: int = 16000
    ) -> bytes:
        """
        Convert text to speech.

        Args:
            text: Text to convert to speech
            language: Language code (ta-IN, hi-IN, en-IN, etc.)
            speaker: Voice to use (optional, uses default for language)
            sample_rate: Output sample rate (8000, 16000, 22050, 24000)

        Returns:
            Audio bytes (WAV format)
        """
        try:
            # Select default speaker if not provided
            if not speaker:
                speaker = self.VOICES.get(language, ["meera"])[0]

            payload = {
                "inputs": [text],
                "target_language_code": language,
                "speaker": speaker,
                "model": "bulbul:v1",  # Sarvam's TTS model
                "pitch": 0,
                "pace": 1.0,
                "loudness": 1.0,
                "enable_preprocessing": True,
                "speech_sample_rate": sample_rate
            }

            headers = {
                "api-subscription-key": self.api_key,
                "Content-Type": "application/json"
            }

            response = await self.client.post(
                self.API_URL,
                json=payload,
                headers=headers
            )

            if response.status_code == 200:
                result = response.json()
                # Sarvam returns base64 encoded audio
                audio_base64 = result.get("audios", [None])[0]
                if audio_base64:
                    return base64.b64decode(audio_base64)
                return b""
            else:
                print(f"Sarvam TTS error: {response.status_code} - {response.text}")
                return b""

        except Exception as e:
            print(f"Sarvam TTS exception: {e}")
            return b""

    async def synthesize_stream(
        self,
        text: str,
        language: str = "ta-IN",
        speaker: Optional[str] = None
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream audio synthesis (for lower latency).

        Currently Sarvam doesn't support streaming, so this
        synthesizes the full audio and yields it in chunks.

        Args:
            text: Text to convert
            language: Language code
            speaker: Voice to use

        Yields:
            Audio chunks
        """
        audio = await self.synthesize(text, language, speaker)
        if audio:
            # Yield in 4KB chunks
            chunk_size = 4096
            for i in range(0, len(audio), chunk_size):
                yield audio[i:i + chunk_size]

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Convenience function for quick synthesis
async def speak(text: str, language: str = "ta-IN") -> bytes:
    """
    Quick text-to-speech conversion.

    Args:
        text: Text to speak
        language: Language code

    Returns:
        Audio bytes
    """
    tts = SarvamTTS()
    try:
        return await tts.synthesize(text, language)
    finally:
        await tts.close()
