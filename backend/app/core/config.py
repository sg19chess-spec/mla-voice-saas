"""
Configuration Management
========================
This file loads all your secret keys and settings from the .env file.

WHY WE DO THIS:
- Keeps secrets out of your code (security!)
- Makes it easy to change settings without editing code
- Different settings for development vs production

HOW IT WORKS:
1. You create a .env file with your secrets
2. This file reads those secrets
3. Other parts of the app use this file to get settings
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    All application settings in one place.

    These values come from your .env file.
    If a value isn't in .env, it uses the default shown here.
    """

    # ----- Application -----
    app_name: str = "MLA Voice AI"
    app_env: str = "development"  # "development" or "production"
    app_secret_key: str = "change-me-in-production"

    # ----- Supabase (Database) -----
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""

    # ----- AI Services -----
    groq_api_key: str = ""
    sarvam_api_key: str = ""

    # ----- LiveKit (Voice) -----
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""

    # ----- SMS -----
    sms_api_key: str = ""
    sms_sender_id: str = "MLABOT"

    class Config:
        # Tell Pydantic where to find the .env file
        env_file = ".env"
        # Make variable names case-insensitive
        # So SUPABASE_URL and supabase_url both work
        case_sensitive = False


@lru_cache()  # This caches the settings so we don't reload .env every time
def get_settings() -> Settings:
    """
    Get application settings.

    Usage in other files:
        from app.core.config import get_settings
        settings = get_settings()
        print(settings.supabase_url)
    """
    return Settings()
