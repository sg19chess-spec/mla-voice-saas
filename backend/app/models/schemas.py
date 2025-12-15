"""
Data Schemas (Models)
=====================
This file defines the STRUCTURE of your data.

WHAT ARE SCHEMAS?
Think of them as "templates" or "forms" that define:
- What fields does a complaint have?
- What type is each field? (text, number, date?)
- Which fields are required vs optional?

WHY WE NEED THIS:
1. Validation: Ensures data is correct before saving
2. Documentation: Shows what data looks like
3. Type hints: Helps your code editor autocomplete

EXAMPLE:
    When someone creates a complaint, they must provide:
    - name (required, text)
    - phone (required, text)
    - issue_type (required, one of: water/road/electricity)
    - description (required, text)
    - location (optional, text)
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum


# ============================================
# ENUMS (Fixed choices)
# ============================================

class IssueType(str, Enum):
    """Types of complaints citizens can file"""
    WATER = "water"
    ROAD = "road"
    ELECTRICITY = "electricity"
    DRAINAGE = "drainage"
    GARBAGE = "garbage"
    STREETLIGHT = "streetlight"
    OTHER = "other"


class ComplaintStatus(str, Enum):
    """Status of a complaint as it moves through the system"""
    NEW = "new"                    # Just created
    ASSIGNED = "assigned"          # Given to an officer
    IN_PROGRESS = "in_progress"    # Officer is working on it
    COMPLETED = "completed"        # Officer finished the job
    VERIFIED = "verified"          # MLA verified the completion
    CLOSED = "closed"              # Archived


class JobStatus(str, Enum):
    """Status of a job assigned to an officer"""
    ASSIGNED = "assigned"          # Just assigned
    ACCEPTED = "accepted"          # Officer accepted
    IN_PROGRESS = "in_progress"    # Work started
    COMPLETED = "completed"        # Work done, photos uploaded
    OVERDUE = "overdue"            # Past deadline


# ============================================
# TENANT (MLA) SCHEMAS
# ============================================

class TenantCreate(BaseModel):
    """Data needed to create a new MLA account"""
    name: str = Field(..., description="MLA's full name", example="Shri Rajesh Kumar")
    constituency: str = Field(..., description="Constituency name", example="Chennai South")
    phone_number: str = Field(..., description="MLA office phone", example="+914423456789")
    email: str = Field(..., description="MLA email", example="rajesh@example.com")
    languages: list[str] = Field(
        default=["tamil", "english"],
        description="Languages the AI agent should speak"
    )
    greeting_message: Optional[str] = Field(
        default=None,
        description="Custom greeting for the AI agent"
    )


class TenantResponse(BaseModel):
    """Data returned after creating a tenant"""
    id: str
    name: str
    constituency: str
    phone_number: str
    email: str
    languages: list[str]
    created_at: datetime
    is_active: bool


# ============================================
# COMPLAINT SCHEMAS
# ============================================

class ComplaintCreate(BaseModel):
    """Data collected from citizen during the call"""
    citizen_name: str = Field(..., description="Citizen's name")
    citizen_phone: str = Field(..., description="Citizen's phone number")
    issue_type: IssueType = Field(..., description="Type of complaint")
    description: str = Field(..., description="What is the problem?")
    location: Optional[str] = Field(None, description="Where is the problem?")
    landmark: Optional[str] = Field(None, description="Nearby landmark")


class ComplaintResponse(BaseModel):
    """Full complaint data with all fields"""
    id: str
    tenant_id: str
    citizen_name: str
    citizen_phone: str
    issue_type: IssueType
    description: str
    location: Optional[str]
    landmark: Optional[str]
    status: ComplaintStatus
    audio_url: Optional[str]          # Link to call recording
    transcript: Optional[str]         # Full conversation text
    created_at: datetime
    updated_at: datetime


# ============================================
# OFFICER SCHEMAS
# ============================================

class OfficerCreate(BaseModel):
    """Data needed to add a new officer"""
    name: str = Field(..., description="Officer's full name")
    phone: str = Field(..., description="Officer's phone number")
    email: Optional[str] = Field(None, description="Officer's email")
    department: str = Field(..., description="e.g., PWD, Water Board")
    designation: str = Field(..., description="e.g., Junior Engineer")


class OfficerResponse(BaseModel):
    """Full officer data"""
    id: str
    tenant_id: str
    name: str
    phone: str
    email: Optional[str]
    department: str
    designation: str
    is_active: bool
    created_at: datetime


# ============================================
# JOB ASSIGNMENT SCHEMAS
# ============================================

class JobCreate(BaseModel):
    """Data needed to assign a job to an officer"""
    complaint_id: str = Field(..., description="Which complaint this is for")
    officer_id: str = Field(..., description="Which officer to assign")
    deadline: datetime = Field(..., description="When should this be done?")
    instructions: Optional[str] = Field(None, description="Special instructions")


class JobResponse(BaseModel):
    """Full job data"""
    id: str
    complaint_id: str
    officer_id: str
    deadline: datetime
    instructions: Optional[str]
    status: JobStatus
    photo_urls: list[str]             # Proof photos uploaded by officer
    completion_notes: Optional[str]   # Officer's notes on completion
    completed_at: Optional[datetime]
    created_at: datetime


# ============================================
# API RESPONSE WRAPPERS
# ============================================

class SuccessResponse(BaseModel):
    """Standard success response"""
    success: bool = True
    message: str
    data: Optional[dict] = None


class ErrorResponse(BaseModel):
    """Standard error response"""
    success: bool = False
    error: str
    details: Optional[str] = None
