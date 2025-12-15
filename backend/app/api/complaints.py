"""
Complaints API
==============
These endpoints manage citizen complaints.

THE COMPLAINT LIFECYCLE:
1. Citizen calls → AI creates complaint (status: "new")
2. MLA staff sees complaint → assigns to officer (status: "assigned")
3. Officer works on it (status: "in_progress")
4. Officer uploads photos → completes (status: "completed")
5. MLA verifies → closes (status: "verified" → "closed")

ENDPOINTS:
- POST   /api/complaints/              Create new complaint
- GET    /api/complaints/              List complaints (with filters)
- GET    /api/complaints/{id}          Get complaint details
- PUT    /api/complaints/{id}/status   Update complaint status
"""

from fastapi import APIRouter, HTTPException, Query
from app.core.database import get_supabase
from app.models.schemas import (
    ComplaintCreate,
    ComplaintResponse,
    ComplaintStatus,
    IssueType,
    SuccessResponse
)
from typing import List, Optional
from datetime import datetime

router = APIRouter()


# ============================================
# CREATE NEW COMPLAINT
# ============================================
@router.post("/", response_model=SuccessResponse)
async def create_complaint(
    tenant_id: str,
    complaint: ComplaintCreate,
    audio_url: Optional[str] = None,
    transcript: Optional[str] = None
):
    """
    Create a new complaint.

    This is called by the AI agent after collecting information from a citizen.

    Required:
    - tenant_id: Which MLA this complaint belongs to
    - complaint: Citizen's information and complaint details

    Optional:
    - audio_url: Link to call recording
    - transcript: Full conversation text
    """
    try:
        db = get_supabase()

        # Verify tenant exists
        tenant = db.table("tenants").select(
            "id", "constituency"
        ).eq("id", tenant_id).execute()

        if not tenant.data:
            raise HTTPException(
                status_code=404,
                detail=f"Tenant {tenant_id} not found"
            )

        # Generate complaint number (e.g., "CHN-2024-0001")
        # Get count of existing complaints for this tenant this year
        year = datetime.now().year
        existing = db.table("complaints").select(
            "id", count="exact"
        ).eq("tenant_id", tenant_id).gte(
            "created_at", f"{year}-01-01"
        ).execute()

        count = (existing.count or 0) + 1
        constituency_prefix = tenant.data[0]["constituency"][:3].upper()
        complaint_number = f"{constituency_prefix}-{year}-{count:04d}"

        # Insert complaint
        result = db.table("complaints").insert({
            "tenant_id": tenant_id,
            "complaint_number": complaint_number,
            "citizen_name": complaint.citizen_name,
            "citizen_phone": complaint.citizen_phone,
            "issue_type": complaint.issue_type.value,
            "description": complaint.description,
            "location": complaint.location,
            "landmark": complaint.landmark,
            "audio_url": audio_url,
            "transcript": transcript,
            "status": "new"
        }).execute()

        if result.data:
            return SuccessResponse(
                success=True,
                message=f"Complaint {complaint_number} created successfully!",
                data={
                    "complaint_id": result.data[0]["id"],
                    "complaint_number": complaint_number
                }
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to create complaint")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# LIST COMPLAINTS
# ============================================
@router.get("/", response_model=List[ComplaintResponse])
async def list_complaints(
    tenant_id: str,
    status: Optional[ComplaintStatus] = None,
    issue_type: Optional[IssueType] = None,
    search: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    skip: int = 0,
    limit: int = 50
):
    """
    Get list of complaints for an MLA.

    This is what the MLA dashboard uses to show complaints.

    FILTERS:
    - status: Filter by status (new, assigned, completed, etc.)
    - issue_type: Filter by issue type (water, road, electricity, etc.)
    - search: Search in citizen name, location, or description
    - start_date: Complaints after this date (YYYY-MM-DD)
    - end_date: Complaints before this date (YYYY-MM-DD)

    SORTING:
    - sort_by: Field to sort by (created_at, status, issue_type)
    - sort_order: "asc" or "desc"

    PAGINATION:
    - skip: Number of records to skip
    - limit: Max records to return
    """
    try:
        db = get_supabase()

        query = db.table("complaints").select("*").eq("tenant_id", tenant_id)

        # Apply filters
        if status:
            query = query.eq("status", status.value)

        if issue_type:
            query = query.eq("issue_type", issue_type.value)

        if start_date:
            query = query.gte("created_at", start_date)

        if end_date:
            query = query.lte("created_at", end_date)

        if search:
            # Search in name, location, or description
            # Note: Supabase uses 'or' for multiple conditions
            query = query.or_(
                f"citizen_name.ilike.%{search}%,"
                f"location.ilike.%{search}%,"
                f"description.ilike.%{search}%"
            )

        # Apply sorting
        is_desc = sort_order.lower() == "desc"
        query = query.order(sort_by, desc=is_desc)

        # Apply pagination
        result = query.range(skip, skip + limit - 1).execute()

        return result.data

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# GET SINGLE COMPLAINT
# ============================================
@router.get("/{complaint_id}", response_model=ComplaintResponse)
async def get_complaint(complaint_id: str):
    """
    Get details of a specific complaint.

    This shows all information including:
    - Citizen details
    - Full description
    - Audio recording link
    - Transcript
    - Current status
    """
    try:
        db = get_supabase()

        result = db.table("complaints").select("*").eq(
            "id", complaint_id
        ).execute()

        if not result.data:
            raise HTTPException(
                status_code=404,
                detail=f"Complaint {complaint_id} not found"
            )

        return result.data[0]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# UPDATE COMPLAINT STATUS
# ============================================
@router.put("/{complaint_id}/status", response_model=SuccessResponse)
async def update_complaint_status(
    complaint_id: str,
    status: ComplaintStatus
):
    """
    Update a complaint's status.

    Valid status transitions:
    - new → assigned (when forwarded to officer)
    - assigned → in_progress (officer started work)
    - in_progress → completed (officer finished)
    - completed → verified (MLA verified)
    - verified → closed (archived)
    """
    try:
        db = get_supabase()

        # Verify complaint exists
        existing = db.table("complaints").select("id", "status").eq(
            "id", complaint_id
        ).execute()

        if not existing.data:
            raise HTTPException(
                status_code=404,
                detail=f"Complaint {complaint_id} not found"
            )

        # Update status
        result = db.table("complaints").update({
            "status": status.value
        }).eq("id", complaint_id).execute()

        return SuccessResponse(
            success=True,
            message=f"Complaint status updated to '{status.value}'"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# GET COMPLAINT STATISTICS
# ============================================
@router.get("/stats/summary")
async def get_complaint_stats(tenant_id: str):
    """
    Get summary statistics for an MLA's complaints.

    Returns:
    - Total complaints
    - Breakdown by status
    - Breakdown by issue type
    - Complaints this week/month
    """
    try:
        db = get_supabase()

        # Get all complaints for this tenant
        result = db.table("complaints").select(
            "status", "issue_type", "created_at"
        ).eq("tenant_id", tenant_id).execute()

        complaints = result.data

        # Calculate statistics
        total = len(complaints)
        by_status = {}
        by_issue = {}

        for c in complaints:
            # Count by status
            status = c["status"]
            by_status[status] = by_status.get(status, 0) + 1

            # Count by issue type
            issue = c["issue_type"]
            by_issue[issue] = by_issue.get(issue, 0) + 1

        return {
            "total_complaints": total,
            "by_status": by_status,
            "by_issue_type": by_issue
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
