"""
Sarvam AI Speech-to-Text (STT) Plugin
=====================================
Converts spoken Tamil/Hindi/English to text using Sarvam's 'saarika' model.

HOW IT WORKS:
1. Receives audio chunks from the phone call
2. Sends audio to Sarvam API
3. Returns transcribed text

SUPPORTED LANGUAGES:
- Tamil (ta-IN)
- Hindi (hi-IN)
- English (en-IN)
- Telugu (te-IN)
- Kannada (kn-IN)
- Malayalam (ml-IN)
- And more Indian languages!
"""

import httpx
import base64
import io
import wave
import numpy as np
from typing import Optional
import os


class SarvamSTT:
    """
    Sarvam AI Speech-to-Text client.

    Usage:
        stt = SarvamSTT(api_key="your-key")
        text = await stt.transcribe(audio_bytes, language="ta-IN")
    """

    API_URL = "https://api.sarvam.ai/speech-to-text"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Sarvam STT client.

        Args:
            api_key: Sarvam API key. If not provided, reads from SARVAM_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("SARVAM_API_KEY")
        if not self.api_key:
            raise ValueError("SARVAM_API_KEY not provided")

        self.client = httpx.AsyncClient(timeout=30.0)

    async def transcribe(
        self,
        audio_data: bytes,
        language: str = "ta-IN",
        sample_rate: int = 16000
    ) -> str:
        """
        Transcribe audio to text.

        Args:
            audio_data: Raw audio bytes (PCM 16-bit)
            language: Language code (ta-IN, hi-IN, en-IN, etc.)
            sample_rate: Audio sample rate (default 16000)

        Returns:
            Transcribed text string
        """
        try:
            # Convert raw PCM to WAV format (Sarvam expects WAV)
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_data)

            wav_bytes = wav_buffer.getvalue()

            # Prepare multipart form data
            files = {
                "file": ("audio.wav", wav_bytes, "audio/wav")
            }

            data = {
                "language_code": language,
                "model": "saarika:v1",  # Sarvam's STT model
                "with_timestamps": "false"
            }

            headers = {
                "api-subscription-key": self.api_key
            }

            # Make API request
            response = await self.client.post(
                self.API_URL,
                files=files,
                data=data,
                headers=headers
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("transcript", "")
            else:
                print(f"Sarvam STT error: {response.status_code} - {response.text}")
                return ""

        except Exception as e:
            print(f"Sarvam STT exception: {e}")
            return ""

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Language code mappings for convenience
LANGUAGE_CODES = {
    "tamil": "ta-IN",
    "hindi": "hi-IN",
    "english": "en-IN",
    "telugu": "te-IN",
    "kannada": "kn-IN",
    "malayalam": "ml-IN",
    "bengali": "bn-IN",
    "marathi": "mr-IN",
    "gujarati": "gu-IN",
    "punjabi": "pa-IN"
}


def get_language_code(language: str) -> str:
    """
    Convert language name to Sarvam language code.

    Args:
        language: Language name (e.g., "tamil") or code (e.g., "ta-IN")

    Returns:
        Sarvam language code (e.g., "ta-IN")
    """
    language_lower = language.lower()
    return LANGUAGE_CODES.get(language_lower, language)
