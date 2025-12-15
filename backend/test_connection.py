"""
Test Script - Verify Supabase Connection
=========================================
Run this to check if your database connection is working.

Usage: python test_connection.py
"""

import os
from dotenv import load_dotenv
import httpx

# Load environment variables from .env file
load_dotenv()

def test_connection():
    """Test if we can connect to Supabase using REST API."""
    print("=" * 50)
    print("Testing Supabase Connection...")
    print("=" * 50)

    # Check if environment variables are set
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not supabase_url:
        print("ERROR: SUPABASE_URL not set in .env")
        return False

    if not supabase_key:
        print("ERROR: SUPABASE_SERVICE_KEY not set in .env")
        return False

    print(f"SUPABASE_URL: {supabase_url}")
    print(f"SUPABASE_SERVICE_KEY: {supabase_key[:30]}...")

    # Try to connect using REST API directly
    try:
        print("\nConnecting to Supabase REST API...")

        # Supabase REST API endpoint
        rest_url = f"{supabase_url}/rest/v1/tenants?select=count"

        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "count=exact"
        }

        response = httpx.get(rest_url, headers=headers, timeout=10)

        if response.status_code == 200:
            print("Connection successful!")
            print(f"Response: {response.text}")
            return True
        elif response.status_code == 404 or "does not exist" in response.text:
            print("Connection works, but 'tenants' table doesn't exist yet!")
            print("\nNext step: Run the SQL schema in Supabase")
            return True
        else:
            print(f"Unexpected response: {response.status_code}")
            print(f"Body: {response.text}")
            return False

    except Exception as e:
        print(f"Connection failed: {e}")
        return False


if __name__ == "__main__":
    success = test_connection()
    print("\n" + "=" * 50)
    if success:
        print("Test completed! Your Supabase is configured.")
    else:
        print("Test failed. Please check your .env file.")
    print("=" * 50)
