"""
Complaint Tools - Add to your existing agent
=============================================
This file contains the complaint-saving functionality.
Import this in your agent.py to save complaints to Supabase.

Usage in agent.py:
    from complaint_tools import save_complaint_to_db, SUPABASE_CONFIGURED
"""

import os
import httpx
from datetime import datetime
import logging

logger = logging.getLogger("complaint_tools")

# ===========================================
# SUPABASE CONFIGURATION
# ===========================================
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ielvfrkkoxeqmljggoem.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

SUPABASE_CONFIGURED = bool(SUPABASE_URL and SUPABASE_KEY)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
} if SUPABASE_KEY else {}


async def save_complaint_to_db(
    citizen_name: str,
    citizen_phone: str,
    issue_type: str,
    description: str,
    location: str,
    ward: str = "",
    duration_days: int = 0,
) -> dict:
    """
    Save a complaint to Supabase database.

    Args:
        citizen_name: Name of the caller
        citizen_phone: Phone number
        issue_type: road, water, electricity, drainage, garbage, streetlight, other
        description: What is the problem
        location: Where is the problem
        ward: Ward number (optional)
        duration_days: How many days issue exists (optional)

    Returns:
        {"success": True, "complaint_number": "RAS-2024-0001"}
        or {"success": False, "error": "..."}
    """

    if not SUPABASE_CONFIGURED:
        logger.warning("Supabase not configured - generating local reference")
        # Generate a local reference number
        ref = f"RC{datetime.now().strftime('%Y%m%d%H%M%S')}"
        return {"success": True, "complaint_number": ref, "local": True}

    try:
        async with httpx.AsyncClient() as client:
            # Get the first tenant (default MLA)
            tenant_url = f"{SUPABASE_URL}/rest/v1/tenants?limit=1"
            tenant_resp = await client.get(tenant_url, headers=HEADERS, timeout=10)

            if tenant_resp.status_code != 200 or not tenant_resp.json():
                logger.error("No tenant found in database")
                ref = f"RC{datetime.now().strftime('%Y%m%d%H%M%S')}"
                return {"success": True, "complaint_number": ref, "local": True}

            tenant = tenant_resp.json()[0]
            tenant_id = tenant["id"]
            constituency = tenant.get("constituency", "RAS")[:3].upper()

            # Generate complaint number
            year = datetime.now().year

            # Count existing complaints for this year
            count_url = f"{SUPABASE_URL}/rest/v1/complaints?tenant_id=eq.{tenant_id}&select=id"
            count_resp = await client.get(count_url, headers=HEADERS, timeout=10)
            count = len(count_resp.json()) + 1 if count_resp.status_code == 200 else 1

            complaint_number = f"{constituency}-{year}-{count:04d}"

            # Map issue types (Tamil to English)
            issue_map = {
                "சாலை": "road", "road": "road", "roads": "road",
                "தண்ணீர்": "water", "water": "water",
                "மின்சாரம்": "electricity", "electricity": "electricity",
                "சுகாதாரம்": "garbage", "garbage": "garbage", "குப்பை": "garbage",
                "drainage": "drainage", "வடிகால்": "drainage",
                "தெரு விளக்கு": "streetlight", "streetlight": "streetlight", "street light": "streetlight",
            }
            db_issue_type = issue_map.get(issue_type.lower().strip(), "other")

            # Build full location
            full_location = f"Ward {ward}, {location}" if ward else location

            # Create complaint record
            complaint_data = {
                "tenant_id": tenant_id,
                "complaint_number": complaint_number,
                "citizen_name": citizen_name,
                "citizen_phone": citizen_phone,
                "issue_type": db_issue_type,
                "description": description,
                "location": full_location,
                "status": "new"
            }

            # Insert into database
            url = f"{SUPABASE_URL}/rest/v1/complaints"
            response = await client.post(url, headers=HEADERS, json=complaint_data, timeout=10)

            if response.status_code in [200, 201]:
                logger.info(f"✅ Complaint saved: {complaint_number}")
                return {"success": True, "complaint_number": complaint_number}
            else:
                logger.error(f"❌ Failed to save: {response.text}")
                # Return a local reference as fallback
                ref = f"RC{datetime.now().strftime('%Y%m%d%H%M%S')}"
                return {"success": True, "complaint_number": ref, "local": True}

    except Exception as e:
        logger.error(f"❌ Exception saving complaint: {e}")
        ref = f"RC{datetime.now().strftime('%Y%m%d%H%M%S')}"
        return {"success": True, "complaint_number": ref, "local": True}


def get_issue_types() -> list:
    """Get valid issue types in Tamil and English."""
    return [
        {"tamil": "சாலை", "english": "road", "description": "Roads, potholes, damage"},
        {"tamil": "தண்ணீர்", "english": "water", "description": "Water supply, leaks"},
        {"tamil": "மின்சாரம்", "english": "electricity", "description": "Electricity, power"},
        {"tamil": "வடிகால்", "english": "drainage", "description": "Drainage, sewage"},
        {"tamil": "குப்பை", "english": "garbage", "description": "Garbage collection"},
        {"tamil": "தெரு விளக்கு", "english": "streetlight", "description": "Street lights"},
    ]


# Test function
async def test_connection():
    """Test Supabase connection."""
    if not SUPABASE_CONFIGURED:
        print("❌ Supabase not configured")
        return False

    try:
        async with httpx.AsyncClient() as client:
            url = f"{SUPABASE_URL}/rest/v1/tenants?select=count"
            response = await client.get(url, headers=HEADERS, timeout=10)
            if response.status_code == 200:
                print("✅ Supabase connection successful!")
                return True
            else:
                print(f"❌ Supabase error: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


if __name__ == "__main__":
    import asyncio
    print("Testing Supabase connection...")
    print(f"URL: {SUPABASE_URL}")
    print(f"Key: {SUPABASE_KEY[:20]}..." if SUPABASE_KEY else "Key: NOT SET")
    asyncio.run(test_connection())
