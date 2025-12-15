"""
Agent Tools - Functions the AI Can Call
=======================================
These are "tools" or "functions" that the AI agent can use during a conversation.

WHAT ARE TOOLS?
When the AI decides it needs to perform an action (like saving a complaint),
it calls one of these functions. The function runs, and the result is
sent back to the AI.

AVAILABLE TOOLS:
1. save_complaint - Save a new complaint to database
2. get_tenant_info - Get MLA information from phone number
3. get_issue_types - List valid issue types
"""

import os
import httpx
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# HTTP headers for Supabase
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}


async def get_tenant_by_phone(phone_number: str) -> Optional[dict]:
    """
    Find which MLA (tenant) owns a phone number.

    This is called when a call comes in to identify which MLA's
    configuration to use.

    Args:
        phone_number: The phone number that was called (e.g., "+914423456789")

    Returns:
        Tenant data dict or None if not found
    """
    try:
        async with httpx.AsyncClient() as client:
            # URL encode the phone number
            encoded_phone = phone_number.replace("+", "%2B")
            url = f"{SUPABASE_URL}/rest/v1/tenants?phone_number=eq.{encoded_phone}"

            response = await client.get(url, headers=HEADERS, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data:
                    return data[0]
            return None

    except Exception as e:
        print(f"Error getting tenant: {e}")
        return None


async def save_complaint(
    tenant_id: str,
    citizen_name: str,
    citizen_phone: str,
    issue_type: str,
    description: str,
    location: Optional[str] = None,
    landmark: Optional[str] = None,
    audio_url: Optional[str] = None,
    transcript: Optional[str] = None
) -> dict:
    """
    Save a new complaint to the database.

    This is called by the AI agent after collecting all complaint details
    from the citizen.

    Args:
        tenant_id: Which MLA this complaint belongs to
        citizen_name: Name of the person calling
        citizen_phone: Phone number of the caller
        issue_type: Type of issue (water, road, electricity, etc.)
        description: Detailed description of the problem
        location: Where is the problem?
        landmark: Nearby landmark
        audio_url: URL to call recording (optional)
        transcript: Full conversation transcript (optional)

    Returns:
        Dict with success status and complaint number
    """
    try:
        async with httpx.AsyncClient() as client:
            # First, get tenant info to generate complaint number
            tenant_url = f"{SUPABASE_URL}/rest/v1/tenants?id=eq.{tenant_id}"
            tenant_resp = await client.get(tenant_url, headers=HEADERS, timeout=10)

            if tenant_resp.status_code != 200 or not tenant_resp.json():
                return {"success": False, "error": "Tenant not found"}

            tenant = tenant_resp.json()[0]
            constituency = tenant.get("constituency", "MLA")

            # Generate complaint number (e.g., "CHN-2024-0001")
            year = datetime.now().year
            prefix = constituency[:3].upper()

            # Count existing complaints
            count_url = f"{SUPABASE_URL}/rest/v1/complaints?tenant_id=eq.{tenant_id}&select=id"
            count_resp = await client.get(
                count_url,
                headers={**HEADERS, "Prefer": "count=exact"},
                timeout=10
            )
            count = len(count_resp.json()) + 1 if count_resp.status_code == 200 else 1

            complaint_number = f"{prefix}-{year}-{count:04d}"

            # Validate issue type
            valid_types = ["water", "road", "electricity", "drainage", "garbage", "streetlight", "other"]
            if issue_type.lower() not in valid_types:
                issue_type = "other"

            # Create complaint
            complaint_data = {
                "tenant_id": tenant_id,
                "complaint_number": complaint_number,
                "citizen_name": citizen_name,
                "citizen_phone": citizen_phone,
                "issue_type": issue_type.lower(),
                "description": description,
                "location": location,
                "landmark": landmark,
                "audio_url": audio_url,
                "transcript": transcript,
                "status": "new"
            }

            url = f"{SUPABASE_URL}/rest/v1/complaints"
            response = await client.post(url, headers=HEADERS, json=complaint_data, timeout=10)

            if response.status_code in [200, 201]:
                result = response.json()
                return {
                    "success": True,
                    "complaint_number": complaint_number,
                    "complaint_id": result[0]["id"] if result else None,
                    "message": f"Complaint {complaint_number} registered successfully"
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to save: {response.text}"
                }

    except Exception as e:
        return {"success": False, "error": str(e)}


def get_issue_types() -> list:
    """
    Get list of valid issue types.

    The AI can call this to know what categories are available
    and help classify the citizen's complaint.

    Returns:
        List of issue type strings
    """
    return [
        {"type": "water", "description": "Water supply issues, pipe leaks, no water"},
        {"type": "road", "description": "Potholes, damaged roads, road repairs needed"},
        {"type": "electricity", "description": "Power cuts, electrical faults, transformer issues"},
        {"type": "drainage", "description": "Blocked drains, sewage overflow, flooding"},
        {"type": "garbage", "description": "Garbage not collected, dumping issues"},
        {"type": "streetlight", "description": "Street lights not working"},
        {"type": "other", "description": "Any other issue not listed above"}
    ]


async def log_call(
    tenant_id: Optional[str],
    caller_phone: str,
    called_number: str,
    call_status: str,
    duration_seconds: Optional[int] = None,
    complaint_id: Optional[str] = None,
    livekit_room_id: Optional[str] = None
) -> dict:
    """
    Log a phone call record.

    This is called at the end of every call to record what happened.

    Args:
        tenant_id: Which MLA's number was called
        caller_phone: Citizen's phone number
        called_number: MLA's phone number
        call_status: "completed", "no_answer", "busy", "failed"
        duration_seconds: How long the call lasted
        complaint_id: If a complaint was created, its ID
        livekit_room_id: LiveKit room ID for the call

    Returns:
        Dict with success status
    """
    try:
        async with httpx.AsyncClient() as client:
            call_data = {
                "tenant_id": tenant_id,
                "caller_phone": caller_phone,
                "called_number": called_number,
                "call_status": call_status,
                "duration_seconds": duration_seconds,
                "complaint_id": complaint_id,
                "livekit_room_id": livekit_room_id,
                "started_at": datetime.now().isoformat()
            }

            url = f"{SUPABASE_URL}/rest/v1/call_logs"
            response = await client.post(url, headers=HEADERS, json=call_data, timeout=10)

            return {"success": response.status_code in [200, 201]}

    except Exception as e:
        print(f"Error logging call: {e}")
        return {"success": False, "error": str(e)}


# Tool definitions for the LLM (OpenAI function calling format)
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "save_complaint",
            "description": "Save a new citizen complaint to the database. Call this after collecting all required information from the citizen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "citizen_name": {
                        "type": "string",
                        "description": "Full name of the citizen"
                    },
                    "citizen_phone": {
                        "type": "string",
                        "description": "Phone number of the citizen"
                    },
                    "issue_type": {
                        "type": "string",
                        "enum": ["water", "road", "electricity", "drainage", "garbage", "streetlight", "other"],
                        "description": "Category of the complaint"
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed description of the problem"
                    },
                    "location": {
                        "type": "string",
                        "description": "Location/address where the problem is"
                    },
                    "landmark": {
                        "type": "string",
                        "description": "Nearby landmark for easy identification"
                    }
                },
                "required": ["citizen_name", "citizen_phone", "issue_type", "description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_issue_types",
            "description": "Get the list of valid complaint categories/issue types",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]
