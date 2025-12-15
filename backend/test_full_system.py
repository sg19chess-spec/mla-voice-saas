"""
Full System Test
================
This script tests the entire Phase 1 foundation:
1. Creates a sample MLA (tenant)
2. Adds an officer
3. Creates a complaint
4. Assigns the complaint to the officer

Run this AFTER setting up the database tables in Supabase.

Usage: python test_full_system.py
"""

import os
import httpx
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# Headers for Supabase REST API
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

def api_call(method, table, data=None, params=None):
    """Make a REST API call to Supabase."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if params:
        url += f"?{params}"

    try:
        if method == "GET":
            response = httpx.get(url, headers=HEADERS, timeout=10)
        elif method == "POST":
            response = httpx.post(url, headers=HEADERS, json=data, timeout=10)
        elif method == "PATCH":
            response = httpx.patch(url, headers=HEADERS, json=data, timeout=10)

        if response.status_code in [200, 201]:
            return response.json()
        else:
            print(f"  Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"  Error: {e}")
        return None


def main():
    print("=" * 60)
    print("MLA Voice AI - Full System Test")
    print("=" * 60)

    # Check configuration
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: SUPABASE_URL or SUPABASE_SERVICE_KEY not set!")
        return

    print(f"\nSupabase URL: {SUPABASE_URL}")
    print("-" * 60)

    # ========================================
    # STEP 1: Create a Sample MLA (Tenant)
    # ========================================
    print("\n[STEP 1] Creating sample MLA account...")

    tenant_data = {
        "name": "Shri Rajesh Kumar",
        "constituency": "Chennai South",
        "phone_number": "+914423456789",
        "email": "rajesh.kumar@example.com",
        "languages": ["tamil", "english"],
        "greeting_message": "Vanakkam! Welcome to Chennai South constituency. I am an AI assistant. Please tell me your complaint.",
        "is_active": True
    }

    tenant = api_call("POST", "tenants", tenant_data)

    if tenant:
        tenant_id = tenant[0]["id"]
        print(f"  SUCCESS! Created MLA: {tenant[0]['name']}")
        print(f"  Tenant ID: {tenant_id}")
    else:
        print("  Failed to create tenant. It may already exist.")
        # Try to fetch existing tenant
        existing = api_call("GET", "tenants", params="phone_number=eq.%2B914423456789")
        if existing:
            tenant_id = existing[0]["id"]
            print(f"  Using existing tenant: {existing[0]['name']}")
        else:
            print("  Could not find or create tenant. Exiting.")
            return

    # ========================================
    # STEP 2: Add an Officer
    # ========================================
    print("\n[STEP 2] Adding an officer...")

    officer_data = {
        "tenant_id": tenant_id,
        "name": "Arun Kumar",
        "phone": "+919876543210",
        "email": "arun.kumar@pwd.gov.in",
        "department": "PWD",
        "designation": "Junior Engineer",
        "is_active": True
    }

    officer = api_call("POST", "officers", officer_data)

    if officer:
        officer_id = officer[0]["id"]
        print(f"  SUCCESS! Added officer: {officer[0]['name']}")
        print(f"  Department: {officer[0]['department']}")
    else:
        print("  Failed to create officer. It may already exist.")
        existing = api_call("GET", "officers", params=f"tenant_id=eq.{tenant_id}&phone=eq.%2B919876543210")
        if existing:
            officer_id = existing[0]["id"]
            print(f"  Using existing officer: {existing[0]['name']}")
        else:
            print("  Could not find or create officer. Continuing anyway...")
            officer_id = None

    # ========================================
    # STEP 3: Create a Complaint
    # ========================================
    print("\n[STEP 3] Creating a sample complaint...")

    complaint_data = {
        "tenant_id": tenant_id,
        "complaint_number": f"CHN-2024-0001",
        "citizen_name": "Lakshmi Devi",
        "citizen_phone": "+919123456789",
        "issue_type": "water",
        "description": "No water supply in our area for the past 3 days. Please help.",
        "location": "Anna Nagar, 4th Street",
        "landmark": "Near Government School",
        "status": "new"
    }

    complaint = api_call("POST", "complaints", complaint_data)

    if complaint:
        complaint_id = complaint[0]["id"]
        print(f"  SUCCESS! Created complaint: {complaint[0]['complaint_number']}")
        print(f"  Issue: {complaint[0]['issue_type']}")
        print(f"  Citizen: {complaint[0]['citizen_name']}")
    else:
        print("  Failed to create complaint. It may already exist.")
        existing = api_call("GET", "complaints", params=f"tenant_id=eq.{tenant_id}&limit=1")
        if existing:
            complaint_id = existing[0]["id"]
            print(f"  Using existing complaint: {existing[0]['complaint_number']}")
        else:
            print("  No complaints found. Continuing...")
            complaint_id = None

    # ========================================
    # STEP 4: Assign Complaint to Officer
    # ========================================
    if officer_id and complaint_id:
        print("\n[STEP 4] Assigning complaint to officer...")

        deadline = (datetime.now() + timedelta(days=3)).isoformat()

        job_data = {
            "tenant_id": tenant_id,
            "complaint_id": complaint_id,
            "officer_id": officer_id,
            "deadline": deadline,
            "instructions": "Please check the water main and restore supply.",
            "status": "assigned",
            "photo_urls": []
        }

        job = api_call("POST", "job_assignments", job_data)

        if job:
            print(f"  SUCCESS! Job assigned!")
            print(f"  Deadline: {job[0]['deadline'][:10]}")

            # Update complaint status
            api_call("PATCH", "complaints", {"status": "assigned"}, params=f"id=eq.{complaint_id}")
            print("  Complaint status updated to 'assigned'")
        else:
            print("  Failed to create job assignment.")

    # ========================================
    # SUMMARY
    # ========================================
    print("\n" + "=" * 60)
    print("TEST COMPLETE!")
    print("=" * 60)

    print("\nData created in your database:")
    print(f"  - 1 MLA (tenant): Shri Rajesh Kumar")
    print(f"  - 1 Officer: Arun Kumar (PWD)")
    print(f"  - 1 Complaint: Water supply issue")
    print(f"  - 1 Job Assignment: Assigned to officer")

    print("\nNext steps:")
    print("  1. Check Supabase Table Editor to see the data")
    print("  2. Run the FastAPI server: uvicorn app.main:app --reload")
    print("  3. Open http://localhost:8000/docs to test the API")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
