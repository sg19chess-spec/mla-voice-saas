"""
Tenants API (MLA Management)
============================
These endpoints manage MLA accounts (tenants).

WHAT IS A TENANT?
- Each MLA is a "tenant" in our system
- They have their own complaints, officers, and data
- Tenants cannot see each other's data (isolation)

ENDPOINTS:
- POST   /api/tenants/        Create new MLA account
- GET    /api/tenants/        List all MLAs (admin only)
- GET    /api/tenants/{id}    Get one MLA's details
- PUT    /api/tenants/{id}    Update MLA settings
- DELETE /api/tenants/{id}    Deactivate MLA account
"""

from fastapi import APIRouter, HTTPException
from app.core.database import get_supabase
from app.models.schemas import (
    TenantCreate,
    TenantResponse,
    SuccessResponse,
    ErrorResponse
)
from typing import List
import uuid

router = APIRouter()


# ============================================
# CREATE NEW TENANT (MLA)
# ============================================
@router.post("/", response_model=SuccessResponse)
async def create_tenant(tenant: TenantCreate):
    """
    Create a new MLA account.

    This is the "provisioning" step mentioned in AGENTS.md.
    When you create a tenant:
    1. A unique ID is generated
    2. Their data is stored in the tenants table
    3. They can now receive calls and manage complaints

    Example request body:
    ```json
    {
        "name": "Shri Rajesh Kumar",
        "constituency": "Chennai South",
        "phone_number": "+914423456789",
        "email": "rajesh@example.com",
        "languages": ["tamil", "english"]
    }
    ```
    """
    try:
        db = get_supabase()

        # Check if phone number already exists
        existing = db.table("tenants").select("id").eq(
            "phone_number", tenant.phone_number
        ).execute()

        if existing.data:
            raise HTTPException(
                status_code=400,
                detail=f"Phone number {tenant.phone_number} is already registered"
            )

        # Create default greeting if not provided
        greeting = tenant.greeting_message
        if not greeting:
            greeting = (
                f"Vanakkam! Welcome to {tenant.constituency} constituency office. "
                f"I am an AI assistant helping {tenant.name}. "
                "Please tell me your name and describe your complaint."
            )

        # Insert into database
        result = db.table("tenants").insert({
            "name": tenant.name,
            "constituency": tenant.constituency,
            "phone_number": tenant.phone_number,
            "email": tenant.email,
            "languages": tenant.languages,
            "greeting_message": greeting,
            "is_active": True
        }).execute()

        if result.data:
            return SuccessResponse(
                success=True,
                message=f"Tenant '{tenant.name}' created successfully!",
                data=result.data[0]
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to create tenant")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# LIST ALL TENANTS
# ============================================
@router.get("/", response_model=List[TenantResponse])
async def list_tenants(
    is_active: bool = None,
    skip: int = 0,
    limit: int = 50
):
    """
    Get list of all MLA accounts.

    This is for the super admin panel to see all MLAs.

    Query parameters:
    - is_active: Filter by active status (true/false)
    - skip: Number of records to skip (for pagination)
    - limit: Maximum records to return (default 50)
    """
    try:
        db = get_supabase()

        query = db.table("tenants").select("*")

        # Filter by active status if provided
        if is_active is not None:
            query = query.eq("is_active", is_active)

        # Order by creation date (newest first) and paginate
        result = query.order(
            "created_at", desc=True
        ).range(skip, skip + limit - 1).execute()

        return result.data

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# GET SINGLE TENANT
# ============================================
@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(tenant_id: str):
    """
    Get details of a specific MLA.

    Use this to view an MLA's configuration, contact info, etc.
    """
    try:
        db = get_supabase()

        result = db.table("tenants").select("*").eq(
            "id", tenant_id
        ).execute()

        if not result.data:
            raise HTTPException(
                status_code=404,
                detail=f"Tenant with ID {tenant_id} not found"
            )

        return result.data[0]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# GET TENANT BY PHONE NUMBER
# ============================================
@router.get("/by-phone/{phone_number}", response_model=TenantResponse)
async def get_tenant_by_phone(phone_number: str):
    """
    Find a tenant by their phone number.

    This is used when a call comes in:
    1. Call arrives at phone number X
    2. System looks up: "Which MLA owns phone X?"
    3. Returns that MLA's configuration
    4. AI agent uses the config (language, greeting, etc.)
    """
    try:
        db = get_supabase()

        result = db.table("tenants").select("*").eq(
            "phone_number", phone_number
        ).execute()

        if not result.data:
            raise HTTPException(
                status_code=404,
                detail=f"No tenant found with phone number {phone_number}"
            )

        return result.data[0]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# UPDATE TENANT
# ============================================
@router.put("/{tenant_id}", response_model=SuccessResponse)
async def update_tenant(tenant_id: str, updates: dict):
    """
    Update an MLA's settings.

    You can update:
    - name, constituency, email
    - languages (what AI speaks)
    - greeting_message (AI's welcome message)
    - is_active (enable/disable account)

    Example:
    ```json
    {
        "languages": ["tamil", "hindi", "english"],
        "greeting_message": "New custom greeting..."
    }
    ```
    """
    try:
        db = get_supabase()

        # Verify tenant exists
        existing = db.table("tenants").select("id").eq(
            "id", tenant_id
        ).execute()

        if not existing.data:
            raise HTTPException(
                status_code=404,
                detail=f"Tenant with ID {tenant_id} not found"
            )

        # Don't allow updating ID or phone_number (these are fixed)
        updates.pop("id", None)
        updates.pop("phone_number", None)
        updates.pop("created_at", None)

        # Update
        result = db.table("tenants").update(updates).eq(
            "id", tenant_id
        ).execute()

        return SuccessResponse(
            success=True,
            message="Tenant updated successfully",
            data=result.data[0] if result.data else None
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# DEACTIVATE TENANT
# ============================================
@router.delete("/{tenant_id}", response_model=SuccessResponse)
async def deactivate_tenant(tenant_id: str):
    """
    Deactivate an MLA account.

    Note: This doesn't DELETE the data, just marks it as inactive.
    The account can be reactivated later if needed.
    """
    try:
        db = get_supabase()

        # Verify tenant exists
        existing = db.table("tenants").select("id").eq(
            "id", tenant_id
        ).execute()

        if not existing.data:
            raise HTTPException(
                status_code=404,
                detail=f"Tenant with ID {tenant_id} not found"
            )

        # Set is_active to False
        result = db.table("tenants").update({
            "is_active": False
        }).eq("id", tenant_id).execute()

        return SuccessResponse(
            success=True,
            message="Tenant deactivated successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
