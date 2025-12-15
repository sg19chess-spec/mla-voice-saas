"""
MLA Voice AI - Main Application
================================
This is the ENTRY POINT of your backend server.

WHAT THIS FILE DOES:
1. Creates the FastAPI application
2. Sets up CORS (allows frontend to talk to backend)
3. Includes all API routes
4. Provides health check endpoint

HOW TO RUN:
    cd backend
    uvicorn app.main:app --reload

    Then open: http://localhost:8000/docs
    (You'll see all your API endpoints!)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.api import tenants, complaints, officers, health

# Get settings
settings = get_settings()

# ============================================
# CREATE THE APP
# ============================================
app = FastAPI(
    title="MLA Voice AI API",
    description="""
    Backend API for the MLA Voice AI Complaint Management System.

    ## Features
    - **Tenants**: Create and manage MLA accounts
    - **Complaints**: Log and track citizen complaints
    - **Officers**: Manage officers and job assignments
    - **Health**: Check system status
    """,
    version="1.0.0",
    docs_url="/docs",      # Swagger UI at /docs
    redoc_url="/redoc",    # ReDoc at /redoc
)

# ============================================
# CORS MIDDLEWARE
# ============================================
# CORS = Cross-Origin Resource Sharing
# This allows your frontend (Next.js) to call your backend (FastAPI)
# Without this, browsers block the requests!

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",    # Next.js dev server
        "http://127.0.0.1:3000",
        # Add your production frontend URL here later
    ],
    allow_credentials=True,
    allow_methods=["*"],     # Allow all HTTP methods
    allow_headers=["*"],     # Allow all headers
)

# ============================================
# INCLUDE API ROUTES
# ============================================
# Each "router" handles a group of related endpoints
# e.g., /api/tenants/... for tenant operations

app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(tenants.router, prefix="/api/tenants", tags=["Tenants"])
app.include_router(complaints.router, prefix="/api/complaints", tags=["Complaints"])
app.include_router(officers.router, prefix="/api/officers", tags=["Officers"])


# ============================================
# ROOT ENDPOINT
# ============================================
@app.get("/")
async def root():
    """
    Root endpoint - just confirms the API is running.

    Visit http://localhost:8000/ to see this.
    """
    return {
        "message": "MLA Voice AI API is running!",
        "docs": "Visit /docs for API documentation",
        "health": "Visit /api/health for system status"
    }


# ============================================
# STARTUP EVENT
# ============================================
@app.on_event("startup")
async def startup_event():
    """
    Runs when the server starts.
    Good place to initialize connections, check configs, etc.
    """
    print("=" * 50)
    print("🚀 MLA Voice AI Backend Starting...")
    print(f"📍 Environment: {settings.app_env}")
    print(f"📖 API Docs: http://localhost:8000/docs")
    print("=" * 50)
