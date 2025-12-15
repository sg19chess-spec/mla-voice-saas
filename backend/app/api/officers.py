"""
Officers API
============
These endpoints manage officers and job assignments.

WHAT ARE OFFICERS?
- Officers are government employees who resolve complaints
- Examples: PWD Engineer, Water Board Inspector, etc.
- Each officer belongs to ONE MLA (tenant)

JOB ASSIGNMENTS:
- When MLA staff "forwards" a complaint, a job is created
- The job links: complaint → officer → deadline
- Officer must upload photos to complete the job

ENDPOINTS:
Officers:
- POST   /api/officers/              Add new officer
- GET    /api/officers/              List officers
- GET    /api/officers/{id}          Get officer details
- PUT    /api/officers/{id}          Update officer

Jobs:
- POST   /api/officers/jobs/         Create job assignment
- GET    /api/officers/jobs/         List jobs (with filters)
- PUT    /api/officers/jobs/{id}     Update job (status, photos)
"""

from fastapi import APIRouter, HTTPException
from app.core.database import get_supabase
from app.models.schemas import (
    OfficerCreate,
    OfficerResponse,
    JobCreate,
    JobResponse,
    JobStatus,
    SuccessResponse
)
from typing import List, Optional
from datetime import datetime

router = APIRouter()


# ============================================
# OFFICER ENDPOINTS
# ============================================

@router.post("/", response_model=SuccessResponse)
async def create_officer(tenant_id: str, officer: OfficerCreate):
    """
    Add a new officer to an MLA's team.

    Officers can then be assigned jobs (complaints to resolve).

    Example:
    ```json
    {
        "name": "Arun Kumar",
        "phone": "+919876543210",
        "department": "PWD",
        "designation": "Junior Engineer"
    }
    ```
    """
    try:
        db = get_supabase()

        # Verify tenant exists
        tenant = db.table("tenants").select("id").eq(
            "id", tenant_id
        ).execute()

        if not tenant.data:
            raise HTTPException(
                status_code=404,
                detail=f"Tenant {tenant_id} not found"
            )

        # Check if officer phone already exists for this tenant
        existing = db.table("officers").select("id").eq(
            "tenant_id", tenant_id
        ).eq("phone", officer.phone).execute()

        if existing.data:
            raise HTTPException(
                status_code=400,
                detail=f"Officer with phone {officer.phone} already exists"
            )

        # Insert officer
        result = db.table("officers").insert({
            "tenant_id": tenant_id,
            "name": officer.name,
            "phone": officer.phone,
            "email": officer.email,
            "department": officer.department,
            "designation": officer.designation,
            "is_active": True
        }).execute()

        if result.data:
            return SuccessResponse(
                success=True,
                message=f"Officer '{officer.name}' added successfully!",
                data=result.data[0]
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to create officer")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[OfficerResponse])
async def list_officers(
    tenant_id: str,
    department: Optional[str] = None,
    is_active: bool = True
):
    """
    Get list of officers for an MLA.

    This is used in the "Forward" dropdown when assigning jobs.

    Filters:
    - department: Filter by department (PWD, Water Board, etc.)
    - is_active: Only show active officers (default: true)
    """
    try:
        db = get_supabase()

        query = db.table("officers").select("*").eq("tenant_id", tenant_id)

        if department:
            query = query.eq("department", department)

        if is_active is not None:
            query = query.eq("is_active", is_active)

        result = query.order("name").execute()

        return result.data

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{officer_id}", response_model=OfficerResponse)
async def get_officer(officer_id: str):
    """Get details of a specific officer."""
    try:
        db = get_supabase()

        result = db.table("officers").select("*").eq(
            "id", officer_id
        ).execute()

        if not result.data:
            raise HTTPException(
                status_code=404,
                detail=f"Officer {officer_id} not found"
            )

        return result.data[0]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{officer_id}", response_model=SuccessResponse)
async def update_officer(officer_id: str, updates: dict):
    """
    Update an officer's information.

    Can update: name, email, department, designation, is_active
    Cannot update: phone (contact admin to change)
    """
    try:
        db = get_supabase()

        # Verify officer exists
        existing = db.table("officers").select("id").eq(
            "id", officer_id
        ).execute()

        if not existing.data:
            raise HTTPException(
                status_code=404,
                detail=f"Officer {officer_id} not found"
            )

        # Remove protected fields
        updates.pop("id", None)
        updates.pop("tenant_id", None)
        updates.pop("phone", None)
        updates.pop("created_at", None)

        # Update
        result = db.table("officers").update(updates).eq(
            "id", officer_id
        ).execute()

        return SuccessResponse(
            success=True,
            message="Officer updated successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# JOB ASSIGNMENT ENDPOINTS
# ============================================

@router.post("/jobs/", response_model=SuccessResponse)
async def create_job(job: JobCreate):
    """
    Assign a complaint to an officer.

    This is the "Forward" action from the dashboard.

    Steps:
    1. MLA staff clicks "Forward" on a complaint
    2. Selects officer from dropdown
    3. Sets deadline date
    4. Optionally adds instructions
    5. This endpoint creates the job

    After creating:
    - SMS is sent to officer (handled by notification service)
    - Complaint status changes to "assigned"
    """
    try:
        db = get_supabase()

        # Verify complaint exists and get tenant_id
        complaint = db.table("complaints").select(
            "id", "tenant_id", "status"
        ).eq("id", job.complaint_id).execute()

        if not complaint.data:
            raise HTTPException(
                status_code=404,
                detail=f"Complaint {job.complaint_id} not found"
            )

        tenant_id = complaint.data[0]["tenant_id"]

        # Verify officer exists and belongs to same tenant
        officer = db.table("officers").select(
            "id", "tenant_id", "name"
        ).eq("id", job.officer_id).execute()

        if not officer.data:
            raise HTTPException(
                status_code=404,
                detail=f"Officer {job.officer_id} not found"
            )

        if officer.data[0]["tenant_id"] != tenant_id:
            raise HTTPException(
                status_code=400,
                detail="Officer does not belong to this MLA"
            )

        # Create job assignment
        result = db.table("job_assignments").insert({
            "tenant_id": tenant_id,
            "complaint_id": job.complaint_id,
            "officer_id": job.officer_id,
            "deadline": job.deadline.isoformat(),
            "instructions": job.instructions,
            "status": "assigned",
            "photo_urls": []
        }).execute()

        if result.data:
            # Update complaint status to "assigned"
            db.table("complaints").update({
                "status": "assigned"
            }).eq("id", job.complaint_id).execute()

            return SuccessResponse(
                success=True,
                message=f"Job assigned to {officer.data[0]['name']}!",
                data={
                    "job_id": result.data[0]["id"],
                    "officer_name": officer.data[0]["name"]
                }
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to create job")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/", response_model=List[JobResponse])
async def list_jobs(
    tenant_id: Optional[str] = None,
    officer_id: Optional[str] = None,
    status: Optional[JobStatus] = None,
    overdue_only: bool = False
):
    """
    List job assignments.

    Filters:
    - tenant_id: Jobs for a specific MLA
    - officer_id: Jobs for a specific officer
    - status: Filter by status
    - overdue_only: Only show jobs past deadline
    """
    try:
        db = get_supabase()

        query = db.table("job_assignments").select("*")

        if tenant_id:
            query = query.eq("tenant_id", tenant_id)

        if officer_id:
            query = query.eq("officer_id", officer_id)

        if status:
            query = query.eq("status", status.value)

        if overdue_only:
            now = datetime.now().isoformat()
            query = query.lt("deadline", now).neq("status", "completed")

        result = query.order("deadline").execute()

        return result.data

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    """Get details of a specific job assignment."""
    try:
        db = get_supabase()

        result = db.table("job_assignments").select("*").eq(
            "id", job_id
        ).execute()

        if not result.data:
            raise HTTPException(
                status_code=404,
                detail=f"Job {job_id} not found"
            )

        return result.data[0]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/jobs/{job_id}", response_model=SuccessResponse)
async def update_job(job_id: str, updates: dict):
    """
    Update a job assignment.

    Officers use this to:
    - Update status (in_progress, completed)
    - Upload photo URLs
    - Add completion notes

    Example for completing a job:
    ```json
    {
        "status": "completed",
        "photo_urls": ["https://...", "https://..."],
        "completion_notes": "Fixed the water pipe leak"
    }
    ```
    """
    try:
        db = get_supabase()

        # Verify job exists
        existing = db.table("job_assignments").select(
            "id", "complaint_id", "status"
        ).eq("id", job_id).execute()

        if not existing.data:
            raise HTTPException(
                status_code=404,
                detail=f"Job {job_id} not found"
            )

        # If marking as completed, require photos
        if updates.get("status") == "completed":
            photo_urls = updates.get("photo_urls", [])
            if not photo_urls:
                raise HTTPException(
                    status_code=400,
                    detail="At least 1 photo is required to mark job as completed"
                )
            updates["completed_at"] = datetime.now().isoformat()

        # Remove protected fields
        updates.pop("id", None)
        updates.pop("tenant_id", None)
        updates.pop("complaint_id", None)
        updates.pop("officer_id", None)
        updates.pop("created_at", None)

        # Update job
        result = db.table("job_assignments").update(updates).eq(
            "id", job_id
        ).execute()

        # If completed, also update complaint status
        if updates.get("status") == "completed":
            complaint_id = existing.data[0]["complaint_id"]
            db.table("complaints").update({
                "status": "completed"
            }).eq("id", complaint_id).execute()

        return SuccessResponse(
            success=True,
            message="Job updated successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
