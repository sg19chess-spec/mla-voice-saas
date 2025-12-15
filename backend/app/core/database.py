"""
Database Connection
===================
This file connects your app to Supabase (your database).

WHAT IS SUPABASE?
- A cloud database service (like a spreadsheet in the cloud)
- Stores all your data: complaints, MLAs, officers, etc.
- You can query it (ask questions) and insert data

HOW THIS FILE WORKS:
1. Reads your Supabase URL and keys from settings
2. Creates a connection (called a "client")
3. Other parts of the app use this client to read/write data
"""

from supabase import create_client, Client
from app.core.config import get_settings

# Global variable to store the database connection
# We'll set this up when the app starts
_supabase_client: Client | None = None


def get_supabase() -> Client:
    """
    Get the Supabase client (database connection).

    This uses the SERVICE KEY which has full access to the database.
    Use this for backend operations (creating tenants, saving complaints).

    Usage:
        from app.core.database import get_supabase
        db = get_supabase()
        result = db.table("complaints").select("*").execute()
    """
    global _supabase_client

    if _supabase_client is None:
        settings = get_settings()

        # Check if Supabase is configured
        if not settings.supabase_url or not settings.supabase_service_key:
            raise ValueError(
                "Supabase not configured! "
                "Please set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env"
            )

        # Create the connection
        _supabase_client = create_client(
            settings.supabase_url,
            settings.supabase_service_key  # Service key = full access
        )

    return _supabase_client


def test_connection() -> bool:
    """
    Test if the database connection works.

    Returns True if connected, False otherwise.
    Useful for health checks and debugging.
    """
    try:
        db = get_supabase()
        # Try a simple query
        db.table("tenants").select("count", count="exact").execute()
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False
