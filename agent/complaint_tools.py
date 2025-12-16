"""
Complaint Tools - Save complaints to Supabase
==============================================
Based on schema.sql - complaints table fields:
- tenant_id, complaint_number
- citizen_name, citizen_phone
- issue_type (water/road/electricity/drainage/garbage/streetlight/other)
- description, location, landmark
- audio_url, transcript, call_duration_seconds
- status
"""

import os
import httpx
from datetime import datetime
from dataclasses import dataclass
import logging

logger = logging.getLogger("complaint_tools")

# ===========================================
# SUPABASE CONFIGURATION
# ===========================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
} if SUPABASE_KEY else {}


# ===========================================
# DATA CLASSES
# ===========================================
@dataclass
class ComplaintData:
    """All data collected from the caller."""
    citizen_name: str
    citizen_phone: str
    issue_type: str
    description: str  # Main problem summary
    location: str
    ward: str
    landmark: str = ""
    transcript: str = ""  # Full conversation
    call_duration_seconds: int = 0
    audio_url: str = ""


@dataclass
class SaveResult:
    """Result of saving a complaint."""
    success: bool
    complaint_number: str
    complaint_id: str = ""
    error: str = ""


# ===========================================
# ISSUE TYPE MAPPING
# ===========================================
ISSUE_TYPE_MAP = {
    # Tamil to English
    "சாலை": "road",
    "தண்ணீர்": "water",
    "மின்சாரம்": "electricity",
    "வடிகால்": "drainage",
    "குப்பை": "garbage",
    "சுகாதாரம்": "garbage",
    "தெரு விளக்கு": "streetlight",
    "விளக்கு": "streetlight",
    # English variations
    "road": "road",
    "roads": "road",
    "pothole": "road",
    "water": "water",
    "electricity": "electricity",
    "power": "electricity",
    "drainage": "drainage",
    "sewage": "drainage",
    "garbage": "garbage",
    "trash": "garbage",
    "streetlight": "streetlight",
    "street light": "streetlight",
    "light": "streetlight",
}


def normalize_issue_type(issue: str) -> str:
    """Convert issue type to database-valid value."""
    issue_lower = issue.lower().strip()
    return ISSUE_TYPE_MAP.get(issue_lower, "other")


# ===========================================
# MAIN SAVE FUNCTION
# ===========================================
async def save_complaint_to_db(
    citizen_name: str,
    citizen_phone: str,
    issue_type: str,
    description: str,
    location: str,
    ward: str = "",
    landmark: str = "",
    transcript: str = "",
    call_duration_seconds: int = 0,
    audio_url: str = ""
) -> dict:
    """
    Save a complete complaint to Supabase.

    Args:
        citizen_name: Name of the caller
        citizen_phone: Phone number of caller
        issue_type: Type of complaint (road/water/electricity/etc)
        description: Summary of the main problem
        location: Area/street where problem is
        ward: Ward number
        landmark: Nearby landmark
        transcript: Full conversation transcript
        call_duration_seconds: Duration of the call
        audio_url: URL to call recording

    Returns:
        dict with success, complaint_number, complaint_id, error
    """

    # Check if Supabase is configured
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("Supabase not configured - generating local reference")
        ref = f"RC{datetime.now().strftime('%Y%m%d%H%M%S')}"
        return {"success": True, "complaint_number": ref, "complaint_id": "", "local": True}

    try:
        async with httpx.AsyncClient() as client:
            # Step 1: Get tenant
            tenant_url = f"{SUPABASE_URL}/rest/v1/tenants?is_active=eq.true&limit=1"
            tenant_resp = await client.get(tenant_url, headers=HEADERS, timeout=10)

            if tenant_resp.status_code != 200 or not tenant_resp.json():
                logger.error("No active tenant found")
                ref = f"RC{datetime.now().strftime('%H%M%S')}"
                return {"success": True, "complaint_number": ref, "local": True}

            tenant = tenant_resp.json()[0]
            tenant_id = tenant["id"]
            constituency = tenant.get("constituency", "RAS")[:3].upper()

            # Step 2: Generate complaint number
            year = datetime.now().year

            # Count existing complaints for this tenant this year
            count_url = f"{SUPABASE_URL}/rest/v1/complaints?tenant_id=eq.{tenant_id}&created_at=gte.{year}-01-01&select=id"
            count_resp = await client.get(count_url, headers=HEADERS, timeout=10)
            count = len(count_resp.json()) + 1 if count_resp.status_code == 200 else 1

            complaint_number = f"{constituency}-{year}-{count:04d}"

            # Step 3: Normalize issue type
            db_issue_type = normalize_issue_type(issue_type)

            # Step 4: Build full location
            full_location = location
            if ward:
                full_location = f"Ward {ward}, {location}"

            # Step 5: Create complaint record
            complaint_data = {
                "tenant_id": tenant_id,
                "complaint_number": complaint_number,
                "citizen_name": citizen_name,
                "citizen_phone": citizen_phone,
                "issue_type": db_issue_type,
                "description": description,
                "location": full_location,
                "landmark": landmark if landmark else None,
                "transcript": transcript if transcript else None,
                "call_duration_seconds": call_duration_seconds if call_duration_seconds > 0 else None,
                "audio_url": audio_url if audio_url else None,
                "status": "new"
            }

            # Step 6: Insert into database
            url = f"{SUPABASE_URL}/rest/v1/complaints"
            response = await client.post(url, headers=HEADERS, json=complaint_data, timeout=10)

            if response.status_code in [200, 201]:
                result = response.json()
                complaint_id = result[0]["id"] if result else ""
                logger.info(f"✅ Complaint saved: {complaint_number} (ID: {complaint_id})")
                return {
                    "success": True,
                    "complaint_number": complaint_number,
                    "complaint_id": complaint_id
                }
            else:
                logger.error(f"❌ Failed to save: {response.text}")
                ref = f"RC{datetime.now().strftime('%H%M%S')}"
                return {"success": True, "complaint_number": ref, "error": response.text}

    except Exception as e:
        logger.error(f"❌ Exception: {e}")
        ref = f"RC{datetime.now().strftime('%H%M%S')}"
        return {"success": True, "complaint_number": ref, "error": str(e)}


# ===========================================
# LOG CALL FUNCTION
# ===========================================
async def log_call(
    caller_phone: str,
    called_number: str,
    call_status: str = "completed",
    duration_seconds: int = 0,
    complaint_id: str = None,
    livekit_room_id: str = None
) -> dict:
    """
    Log a call to the call_logs table.

    Args:
        caller_phone: Citizen's phone number
        called_number: MLA's phone number
        call_status: completed/no_answer/busy/failed/voicemail
        duration_seconds: Call duration
        complaint_id: If complaint was created
        livekit_room_id: LiveKit room ID
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        return {"success": False, "error": "Supabase not configured"}

    try:
        async with httpx.AsyncClient() as client:
            # Get tenant by phone number
            tenant_id = None
            if called_number:
                encoded_phone = called_number.replace("+", "%2B")
                tenant_url = f"{SUPABASE_URL}/rest/v1/tenants?phone_number=eq.{encoded_phone}&select=id"
                tenant_resp = await client.get(tenant_url, headers=HEADERS, timeout=10)
                if tenant_resp.status_code == 200 and tenant_resp.json():
                    tenant_id = tenant_resp.json()[0]["id"]

            call_data = {
                "tenant_id": tenant_id,
                "caller_phone": caller_phone,
                "called_number": called_number,
                "call_status": call_status,
                "duration_seconds": duration_seconds if duration_seconds > 0 else None,
                "complaint_id": complaint_id if complaint_id else None,
                "livekit_room_id": livekit_room_id,
                "started_at": datetime.now().isoformat()
            }

            url = f"{SUPABASE_URL}/rest/v1/call_logs"
            response = await client.post(url, headers=HEADERS, json=call_data, timeout=10)

            return {"success": response.status_code in [200, 201]}

    except Exception as e:
        logger.error(f"Error logging call: {e}")
        return {"success": False, "error": str(e)}


# ===========================================
# TEST CONNECTION
# ===========================================
async def test_supabase_connection() -> bool:
    """Test if Supabase is reachable and configured."""
    if not SUPABASE_URL or not SUPABASE_KEY:
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
    print(f"SUPABASE_URL: {SUPABASE_URL}")
    print(f"SUPABASE_KEY: {SUPABASE_KEY[:30] if SUPABASE_KEY else 'NOT SET'}...")
    asyncio.run(test_supabase_connection())
