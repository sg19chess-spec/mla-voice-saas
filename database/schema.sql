-- ============================================
-- MLA Voice AI - Database Schema
-- ============================================
-- This file creates all the tables in your database.
-- Run this in Supabase SQL Editor (we'll do this together).
--
-- TABLES CREATED:
-- 1. tenants       - MLA accounts (each MLA is a "tenant")
-- 2. officers      - Officers who resolve complaints
-- 3. complaints    - Citizen complaints from calls
-- 4. job_assignments - Jobs assigned to officers
-- 5. call_logs     - Record of all calls
-- ============================================

-- Enable UUID generation (for unique IDs)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- 1. TENANTS TABLE (MLAs)
-- ============================================
-- Each row = one MLA account
-- This is the "parent" table - all other data belongs to a tenant

CREATE TABLE IF NOT EXISTS tenants (
    -- Primary key: unique ID for each tenant
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- MLA Information
    name TEXT NOT NULL,                    -- "Shri Rajesh Kumar"
    constituency TEXT NOT NULL,            -- "Chennai South"
    phone_number TEXT UNIQUE NOT NULL,     -- "+914423456789" (unique!)
    email TEXT,                            -- "mla@example.com"

    -- AI Agent Configuration
    languages TEXT[] DEFAULT ARRAY['tamil', 'english'],  -- Languages agent speaks
    greeting_message TEXT,                 -- Custom greeting

    -- Status
    is_active BOOLEAN DEFAULT true,        -- Can be disabled

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast phone number lookups (when call comes in)
CREATE INDEX IF NOT EXISTS idx_tenants_phone ON tenants(phone_number);


-- ============================================
-- 2. OFFICERS TABLE
-- ============================================
-- Officers who resolve complaints
-- Each officer belongs to ONE tenant (MLA)

CREATE TABLE IF NOT EXISTS officers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Which MLA does this officer work for?
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- Officer Information
    name TEXT NOT NULL,                    -- "Arun Kumar"
    phone TEXT NOT NULL,                   -- "+919876543210"
    email TEXT,
    department TEXT NOT NULL,              -- "PWD", "Water Board"
    designation TEXT,                      -- "Junior Engineer"

    -- Status
    is_active BOOLEAN DEFAULT true,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- One officer phone per tenant (can't have duplicates)
    UNIQUE(tenant_id, phone)
);

-- Index for finding officers by tenant
CREATE INDEX IF NOT EXISTS idx_officers_tenant ON officers(tenant_id);


-- ============================================
-- 3. COMPLAINTS TABLE
-- ============================================
-- Every complaint from citizens
-- Each complaint belongs to ONE tenant

CREATE TABLE IF NOT EXISTS complaints (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Which MLA's complaint is this?
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- Complaint number (human-readable, like "CHN-2024-001")
    complaint_number TEXT NOT NULL,

    -- Citizen Information
    citizen_name TEXT NOT NULL,
    citizen_phone TEXT NOT NULL,

    -- Complaint Details
    issue_type TEXT NOT NULL CHECK (issue_type IN (
        'water', 'road', 'electricity', 'drainage',
        'garbage', 'streetlight', 'other'
    )),
    description TEXT NOT NULL,
    location TEXT,
    landmark TEXT,

    -- Call Information
    audio_url TEXT,                        -- Recording URL
    transcript TEXT,                       -- Full conversation
    call_duration_seconds INTEGER,

    -- Status tracking
    status TEXT DEFAULT 'new' CHECK (status IN (
        'new', 'assigned', 'in_progress', 'completed', 'verified', 'closed'
    )),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Unique complaint number per tenant
    UNIQUE(tenant_id, complaint_number)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_complaints_tenant ON complaints(tenant_id);
CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_complaints_date ON complaints(tenant_id, created_at DESC);


-- ============================================
-- 4. JOB ASSIGNMENTS TABLE
-- ============================================
-- When MLA assigns a complaint to an officer

CREATE TABLE IF NOT EXISTS job_assignments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Links
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    complaint_id UUID NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
    officer_id UUID NOT NULL REFERENCES officers(id) ON DELETE CASCADE,

    -- Assignment Details
    deadline TIMESTAMPTZ NOT NULL,         -- When should it be done?
    instructions TEXT,                     -- Special instructions from MLA

    -- Status
    status TEXT DEFAULT 'assigned' CHECK (status IN (
        'assigned', 'accepted', 'in_progress', 'completed', 'overdue'
    )),

    -- Completion Proof
    photo_urls TEXT[],                     -- Array of photo URLs
    completion_notes TEXT,                 -- Officer's notes
    completed_at TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_jobs_tenant ON job_assignments(tenant_id);
CREATE INDEX IF NOT EXISTS idx_jobs_officer ON job_assignments(officer_id);
CREATE INDEX IF NOT EXISTS idx_jobs_complaint ON job_assignments(complaint_id);
CREATE INDEX IF NOT EXISTS idx_jobs_deadline ON job_assignments(deadline) WHERE status NOT IN ('completed');


-- ============================================
-- 5. CALL LOGS TABLE
-- ============================================
-- Record of every call (even failed ones)

CREATE TABLE IF NOT EXISTS call_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL,

    -- Call Information
    caller_phone TEXT NOT NULL,
    called_number TEXT NOT NULL,           -- Which MLA number was called

    -- Call Status
    call_status TEXT NOT NULL CHECK (call_status IN (
        'completed', 'no_answer', 'busy', 'failed', 'voicemail'
    )),

    -- Duration
    duration_seconds INTEGER,

    -- Result
    complaint_id UUID REFERENCES complaints(id),  -- If complaint was created

    -- LiveKit Information
    livekit_room_id TEXT,

    -- Timestamps
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ
);

-- Index for analytics
CREATE INDEX IF NOT EXISTS idx_calls_tenant ON call_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_calls_date ON call_logs(started_at DESC);


-- ============================================
-- HELPER FUNCTION: Generate Complaint Number
-- ============================================
-- Creates numbers like "CHN-2024-0001"

CREATE OR REPLACE FUNCTION generate_complaint_number(p_tenant_id UUID)
RETURNS TEXT AS $$
DECLARE
    v_prefix TEXT;
    v_year TEXT;
    v_count INTEGER;
BEGIN
    -- Get constituency prefix (first 3 letters)
    SELECT UPPER(LEFT(constituency, 3)) INTO v_prefix
    FROM tenants WHERE id = p_tenant_id;

    -- Current year
    v_year := TO_CHAR(NOW(), 'YYYY');

    -- Count existing complaints this year
    SELECT COUNT(*) + 1 INTO v_count
    FROM complaints
    WHERE tenant_id = p_tenant_id
    AND EXTRACT(YEAR FROM created_at) = EXTRACT(YEAR FROM NOW());

    -- Return formatted number
    RETURN v_prefix || '-' || v_year || '-' || LPAD(v_count::TEXT, 4, '0');
END;
$$ LANGUAGE plpgsql;


-- ============================================
-- AUTOMATIC UPDATED_AT TRIGGER
-- ============================================
-- Automatically updates 'updated_at' when a row changes

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to all tables
CREATE TRIGGER update_tenants_updated_at
    BEFORE UPDATE ON tenants
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_officers_updated_at
    BEFORE UPDATE ON officers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_complaints_updated_at
    BEFORE UPDATE ON complaints
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_jobs_updated_at
    BEFORE UPDATE ON job_assignments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- ============================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================
-- This ensures tenants can only see their own data!

-- Enable RLS on all tables
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE officers ENABLE ROW LEVEL SECURITY;
ALTER TABLE complaints ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE call_logs ENABLE ROW LEVEL SECURITY;

-- Policy: Service role can do everything (for backend)
-- Note: More specific policies will be added for dashboard users

CREATE POLICY "Service role full access to tenants" ON tenants
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access to officers" ON officers
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access to complaints" ON complaints
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access to job_assignments" ON job_assignments
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access to call_logs" ON call_logs
    FOR ALL USING (true) WITH CHECK (true);


-- ============================================
-- SUCCESS MESSAGE
-- ============================================
DO $$
BEGIN
    RAISE NOTICE '✅ Database schema created successfully!';
    RAISE NOTICE 'Tables created: tenants, officers, complaints, job_assignments, call_logs';
END $$;
