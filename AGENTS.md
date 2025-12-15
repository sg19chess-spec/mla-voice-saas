# MLA Voice AI - Complete System Guide

## What This System Does
A platform where citizens can call and log complaints, MLAs can view and manage them, and officers can resolve issues with photo proof.

---

## Complete Workflow

### 1. CALL FLOW (Citizen Side)
```
Citizen calls MLA number 
    ↓
AI voice agent answers (in Tamil/Hindi)
    ↓
AI collects complaint details:
    - Name
    - Location
    - Issue type (water/road/electric)
    - Description
    ↓
AI logs complaint to database
    ↓
SMS sent to citizen: "Your complaint #123 has been registered. You will be notified once resolved."
```

### 2. DASHBOARD VIEW (MLA Side)
**What MLA sees:**
- List of all complaints with:
  - Complaint summary
  - Audio recording link
  - Full transcript
  - Citizen phone number
  - Date & time
  - Status (New/Assigned/In Progress/Completed)

**MLA can:**
- **Filter** complaints by:
  - Type: Water, Road, Electricity
  - Status: New, Assigned, Completed
  - Date range
- **Sort** complaints by:
  - Date (newest/oldest)
  - Status
  - Urgency level
- **Search** by:
  - Citizen name
  - Location
  - Phone number

### 3. JOB ASSIGNMENT (MLA Staff Action)
**Steps:**
1. MLA staff clicks on a complaint
2. Clicks "Forward" button
3. Popup appears with:
   - Dropdown: Select officer (from officer list)
   - Date picker: Set deadline
   - Text area: Add instructions (optional)
4. Click "OK" button
5. System creates job assignment

**What happens behind the scenes:**
```
Job record created in database:
    - complaint_id
    - assigned_to (officer_id)
    - deadline_date
    - status: "assigned"
    - created_at
```

### 4. JOB TRACKING (Automated Alerts)

**Immediate alert (when assigned):**
- SMS sent to officer:  
  `"New job assigned: [Complaint summary]. Location: [Address]. Deadline: [Date]. View: [Link]"`

**Deadline monitoring:**
- If deadline passes without completion:
  - Alert to MLA:  
    `"OVERDUE: Job #123 assigned to [Officer name] has crossed deadline."`
  - Alert to Officer:  
    `"REMINDER: Job #123 is overdue. Please complete and upload proof."`

**Officer actions:**
1. Officer visits site
2. Resolves issue
3. Takes photos as proof
4. Logs into app/portal
5. Uploads photos (max 5)
6. Clicks "Mark as Complete" button

### 5. COMPLETION FLOW

**When officer marks job done:**
```
System checks:
    - At least 1 photo uploaded? YES
    ↓
Update job status: "completed"
Update complaint status: "resolved"
Store completion timestamp
    ↓
Send SMS to citizen:
"Your complaint #123 has been resolved. 
View photos: https://portal.mla.in/proof/123"
    ↓
Send notification to MLA:
"Complaint #123 resolved by [Officer name]"
```

---

## Technical Stack

### Voice System
- **LiveKit**: Handles voice calls (self-hosted on RunPod servers)
- **Deepgram**: Converts speech to text (STT)
- **OpenAI GPT-4.1-mini**: AI brain that understands and responds
- **Cartesia**: Converts text back to speech (TTS)

### Backend (Server)
- **FastAPI**: Python framework to handle all API requests
- **Supabase/PostgreSQL**: Database to store everything

### Frontend (Dashboard)
- **Next.js 14**: Modern web framework for MLA dashboard

### Phone Integration
- **Exotel**: Receives calls and routes to LiveKit
- **SMS Gateway**: Sends SMS notifications

---

## Multi-Tenant Architecture

### What is Multi-Tenant?
Each MLA gets their own **isolated space**:
- Their own database section (schema)
- Their own phone number
- Their own set of complaints and officers
- **MLAs cannot see each other's data**

### Auto-Provisioning (Creating New MLA Account)

**When admin creates a new MLA:**
```
1. Generate unique tenant_id (e.g., "mla_chennai_123")
2. Create database schema: tenant_mla_chennai_123
3. Create tables inside schema:
   - complaints
   - officers
   - job_assignments
   - call_logs
4. Register phone number with LiveKit
5. Create SIP routing rule (phone → tenant mapping)
6. Store agent configuration in Redis:
   - MLA name
   - Constituency name
   - Languages (Tamil/Hindi)
   - Greeting message
7. Create dashboard login credentials
8. Send welcome email with login details
```

**All happens in ONE click from admin panel!**

---

## Code Structure (Simplified)

```
project/
│
├── admin/                      # Super admin panel
│   ├── create_tenant.py       # Creates new MLA account
│   └── manage_tenants.py      # View/edit MLAs
│
├── agent/                      # AI Voice Agent
│   ├── agent.py               # Main agent logic
│   ├── tools.py               # Functions: save complaint, send SMS
│   └── start_agent.py         # Entry point when call comes
│
├── dashboard/                  # MLA Dashboard (Website)
│   ├── complaints.py          # View complaints page
│   ├── assign_job.py          # Forward to officer page
│   └── reports.py             # Analytics page
│
├── database/                   # Database logic
│   ├── models.py              # Define tables structure
│   └── queries.py             # Common database operations
│
└── notifications/              # SMS/Email alerts
    └── send_sms.py            # Send SMS function
```

---

## Key Patterns (For Developers)

### 1. Identifying Which MLA (Tenant Context)
```python
# When a call comes in:
def handle_call(phone_number):
    # Step 1: Find which MLA owns this phone number
    tenant = database.query("SELECT * FROM tenants WHERE phone = ?", phone_number)
    
    # Step 2: Load that MLA's configuration
    config = redis.get(f"agent:config:{tenant['id']}")
    
    # Step 3: Start agent with MLA's specific settings
    agent = MLAAgent(
        tenant_id=tenant['id'],
        language=config['language'],
        greeting=config['greeting']
    )
```

### 2. Saving Complaint to Correct Database
```python
def save_complaint(tenant_id, complaint_data):
    # Use tenant-specific schema
    schema = f"tenant_{tenant_id}"
    
    # Save to their database section
    database.execute(
        f"INSERT INTO {schema}.complaints (name, issue, location) VALUES (?, ?, ?)",
        complaint_data['name'],
        complaint_data['issue'],
        complaint_data['location']
    )
```

### 3. Phone Number Routing (LiveKit SIP)
```python
# Map phone number to tenant room
await livekit.create_sip_rule(
    phone_number="+914423456789",
    route_to_room=f"mla-{tenant_id}",
    trunk_id="shared_trunk"
)
```

---

## Build Priority Order

**Phase 1: Foundation**
1. Database setup (tables for tenants, complaints, officers)
2. Tenant provisioning service (create new MLA accounts)
3. Super admin panel (UI to manage MLAs)

**Phase 2: Voice Agent**
4. Basic AI agent (answer calls, collect info)
5. Save complaints to database
6. Send SMS confirmations

**Phase 3: Dashboard**
7. MLA login page
8. View complaints page (with filters/sort)
9. Job assignment flow (forward to officer)
10. Officer portal (upload photos, mark complete)

**Phase 4: Tracking & Alerts**
11. Deadline monitoring system
12. Automated alerts (SMS/email)
13. Photo proof upload
14. Completion flow with citizen notification

**Phase 5: Polish**
15. Analytics/reports for MLA
16. Mobile app for officers
17. Multi-language support

---

## Important Resources

### LiveKit MCP Server
**Always check for latest APIs:**  
`https://docs.livekit.io/mcp`

**Example searches in MCP:**
- "How to create room with metadata"
- "SIP dispatch rules setup"
- "Agent function tools"
- "Voice pipeline configuration"

### Testing Strategy
1. Test with one MLA first (pilot)
2. Use test phone number
3. Check database isolation (tenant A can't see tenant B)
4. Verify SMS delivery
5. Test deadline alerts
6. Load test with multiple calls

---

## Key Success Metrics
- Call answer rate: >95%
- Complaint logging accuracy: >90%
- SMS delivery: >98%
- Average resolution time: <48 hours
- Photo proof upload rate: 100%

---

## Security Notes
- Each tenant's data is isolated (cannot access other MLAs)
- Officers can only see jobs assigned to them
- All calls are encrypted
- Photos stored with access control
- SMS contains only complaint ID (no sensitive data)

---

**Remember:** Always use LiveKit MCP to get the latest code examples and API documentation before implementing any LiveKit feature!
