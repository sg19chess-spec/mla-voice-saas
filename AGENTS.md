# MLA Voice AI - Agent Instructions

## Project
Multi-tenant SaaS for Indian MLAs to handle constituent complaints via AI voice agents.

## Stack
- Voice: LiveKit (self-hosted RunPod)
- Backend: FastAPI (Python)
- Frontend: Next.js 14
- DB: Supabase (PostgreSQL)
- AI: Deepgram STT, OpenAI GPT-4.1-mini, Cartesia TTS

## LiveKit MCP
**Always use LiveKit MCP server for latest docs**: `https://docs.livekit.io/mcp`

Search MCP before any LiveKit code:
- "Create room with metadata"
- "SIP dispatch rules"
- "Agents function tools"

## Architecture

### Multi-Tenant Isolation
Each MLA gets:
- DB schema: `tenant_{id}`
- LiveKit room: `mla-{id}`
- SIP route: phone → tenant mapping
- Agent config in Redis

### Auto-Provisioning Flow
When admin creates tenant:
1. Generate tenant_id
2. Create DB schema + tables
3. Create LiveKit room
4. Configure SIP dispatch rule
5. Store agent config (Redis)
6. Create dashboard login
7. Send welcome email

All in ONE API call.

### Voice Agent Flow
```
Call → Exotel → LiveKit SIP → Maps phone to tenant
→ Agent loads config → Greets in Tamil/Hindi
→ Collects complaint → Logs to tenant schema
→ Sends SMS confirmation
```

## Code Structure
```
src/
├── admin/
│   ├── api/tenants.py
│   ├── services/tenant_provisioner.py
│   └── ui/
├── dashboard/
│   ├── api/complaints.py
│   └── pages/
├── agent/
│   ├── agent.py
│   ├── tools.py
│   └── entrypoint.py
└── shared/
    ├── database.py
    ├── livekit_client.py
    └── redis_client.py
```

## Key Patterns

### Tenant Context Injection
```python
async def entrypoint(ctx: JobContext):
    # Get phone from SIP
    phone = ctx.room.metadata.get('to_number')
    # Map to tenant
    tenant = await get_tenant_from_phone(phone)
    # Load config
    config = await redis.get(f"agent:config:{tenant['id']}")
    # Start agent with tenant context
    agent = MLAAgent(tenant_id=tenant['id'], **config)
```

### SIP Routing (Use MCP for latest API!)
```python
await livekit.sip.create_dispatch_rule(
    room_name=f"mla-{tenant_id}",
    phone_numbers=['+914423456789'],
    trunk_ids=['shared_trunk']
)
```

## Build Order
1. Tenant provisioning service
2. Super admin panel
3. Voice agent
4. MLA dashboard

---
Always consult LiveKit MCP for current APIs!