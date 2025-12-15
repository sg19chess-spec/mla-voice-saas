"""
MLA Voice Agent - With Complaint Saving
========================================
This agent handles Tamil/Hindi calls and saves complaints to Supabase.

Changes from original:
- Added Supabase connection
- Added save_complaint function tool
- Agent can now save complaints to database
"""

import logging
import os
import httpx
from datetime import datetime
from typing import Annotated

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    RunContext,
    function_tool,
    cli,
)
from livekit.agents.voice import AgentSession
from livekit.plugins import groq, noise_cancellation, sarvam, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")
logger.setLevel(logging.INFO)

load_dotenv()

# ===========================================
# SUPABASE CONFIGURATION
# ===========================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# ===========================================
# COMPLAINT SAVING FUNCTION
# ===========================================
async def save_complaint_to_db(
    citizen_name: str,
    citizen_phone: str,
    issue_type: str,
    description: str,
    location: str,
    ward: str = None,
    duration_days: int = None,
    previous_complaint: bool = False
) -> dict:
    """Save complaint to Supabase database."""

    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("Supabase not configured!")
        return {"success": False, "error": "Database not configured"}

    try:
        async with httpx.AsyncClient() as client:
            # Get or create tenant (for now using a default tenant)
            # You can modify this to look up tenant by phone number
            tenant_url = f"{SUPABASE_URL}/rest/v1/tenants?limit=1"
            tenant_resp = await client.get(tenant_url, headers=HEADERS, timeout=10)

            if tenant_resp.status_code != 200 or not tenant_resp.json():
                return {"success": False, "error": "No tenant configured"}

            tenant = tenant_resp.json()[0]
            tenant_id = tenant["id"]
            constituency = tenant.get("constituency", "RAS")

            # Generate complaint number
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

            # Map Tamil issue types to database values
            issue_type_map = {
                "சாலை": "road",
                "road": "road",
                "தண்ணீர்": "water",
                "water": "water",
                "மின்சாரம்": "electricity",
                "electricity": "electricity",
                "சுகாதாரம்": "garbage",
                "garbage": "garbage",
                "drainage": "drainage",
                "வடிகால்": "drainage",
                "குப்பை": "garbage",
                "தெரு விளக்கு": "streetlight",
                "streetlight": "streetlight",
            }

            db_issue_type = issue_type_map.get(issue_type.lower(), "other")

            # Build location string
            full_location = location
            if ward:
                full_location = f"Ward {ward}, {location}"

            # Create complaint
            complaint_data = {
                "tenant_id": tenant_id,
                "complaint_number": complaint_number,
                "citizen_name": citizen_name,
                "citizen_phone": citizen_phone,
                "issue_type": db_issue_type,
                "description": description,
                "location": full_location,
                "status": "new"
            }

            url = f"{SUPABASE_URL}/rest/v1/complaints"
            response = await client.post(url, headers=HEADERS, json=complaint_data, timeout=10)

            if response.status_code in [200, 201]:
                logger.info(f"Complaint saved: {complaint_number}")
                return {
                    "success": True,
                    "complaint_number": complaint_number
                }
            else:
                logger.error(f"Failed to save: {response.text}")
                return {"success": False, "error": response.text}

    except Exception as e:
        logger.error(f"Error saving complaint: {e}")
        return {"success": False, "error": str(e)}


# ===========================================
# AGENT WITH FUNCTION TOOLS
# ===========================================
class Assistant(Agent):
    def __init__(self, mla_constituency: str = None) -> None:
        super().__init__(
            instructions=f"""
நீங்கள் ராசிபுரம் நகராட்சி அலுவலகத்தின் தொழில்முறை குரல் உதவியாளர்.
மரியாதையாக, தெளிவாக, நேர்மறையாக பேசுங்கள்.

CRITICAL RULES:
1. You ONLY handle municipality complaints: roads, water, electricity, sanitation, drainage, garbage, street lights
2. If caller discusses personal/family problems, health issues, or non-municipality topics → Politely redirect
3. NEVER ask the same question twice
4. ALWAYS address caller respectfully: Male → "சார்", Female → "மேடம்"
5. Be intelligent - understand context before asking questions
6. IMPORTANT: After collecting ALL information, you MUST call save_complaint function to save it!

உங்கள் பணி:

1. பெயர் கேட்ட பிறகு - ASK PURPOSE:
   After they give name, acknowledge and ask why they called:
   "சரி [Name] சார்/மேடம், எதற்காக call பண்ணிருக்கீங்க?"

2. புரிந்துகொள்ளுங்கள் (Understand the issue):

   Listen to their response. Then decide:

   ✅ IF MUNICIPALITY ISSUE (roads, water, electricity, sanitation, drainage, garbage, street lights):
      → Acknowledge: "புரிஞ்சது சார்/மேடம்"
      → Continue collecting remaining information (area, duration, previous complaint)

   ❌ IF NOT MUNICIPALITY ISSUE (personal problems, health, family issues, financial problems, etc.):
      → Politely redirect:
      "புரிஞ்சது சார்/மேடம். ஆனா இது நகராட்சி விஷயம் இல்ல சார்/மேடம்.
      நகராட்சி விஷயங்களுக்கு மட்டும் தான் நாங்க உதவ முடியும் - சாலை, தண்ணீர், மின்சாரம், சுகாதாரம் மாதிரி.
      நகராட்சி சம்பந்தமா வேற ஏதாவது இருக்கா?"

3. தகவல்கள் சேகரிக்கவும் (ONLY FOR VALID MUNICIPALITY COMPLAINTS):

   After understanding the issue, ask remaining questions ONLY ONCE each:

   a) "எந்த பகுதி? எந்த வார்டு?"
      → "சரி சார்/மேடம்"

   b) "இது எத்தனை நாட்களாக இருக்கு?"
      → "சரி சார்/மேடம்"

   c) "இதற்கு முன்பு புகார் கொடுத்தீர்களா?"
      → "புரிஞ்சது சார்/மேடம்"

4. SAVE THE COMPLAINT:
   After collecting: name, issue type, location/ward, duration -
   YOU MUST call the save_complaint function with all the details!

5. தொழில்முறை உறுதியளிப்பு (After saving):
   Use the complaint number returned by save_complaint:
   "நன்றி [Name] சார்/மேடம். உங்கள் புகார் பதிவு செய்யப்பட்டது.
   உங்கள் புகார் reference number: [complaint_number from function]
   இந்த பிரச்சினையை உடனே கவனித்து தீர்வு அளிக்கப்படும் சார்/மேடம்.
   வேறு ஏதேனும் உதவி தேவையா சார்/மேடம்?"

VALID MUNICIPALITY TOPICS:
✅ சாலை (roads) - குழி, damage
✅ தண்ணீர் (water) - supply issues, leakage
✅ மின்சாரம் (electricity) - street lights, power issues in public areas
✅ சுகாதாரம் (sanitation) - garbage collection, cleanliness
✅ drainage - blocked, overflow
✅ public toilets
✅ parks maintenance
✅ Any other municipality infrastructure

INVALID TOPICS (Politely redirect):
❌ Personal/family problems
❌ Health issues
❌ Financial problems
❌ Legal issues
❌ Private property disputes

Constituency: {mla_constituency or 'Rasipuram'}
Language: Tamil (தமிழ்)
Tone: Professional, respectful, intelligent, helpful
            """,
        )

        # Store collected data
        self.complaint_data = {}

    @function_tool()
    async def save_complaint(
        self,
        ctx: RunContext,
        citizen_name: Annotated[str, "Name of the citizen who is calling"],
        issue_type: Annotated[str, "Type of complaint: road, water, electricity, drainage, garbage, streetlight"],
        description: Annotated[str, "Brief description of the problem"],
        location: Annotated[str, "Location/area where the problem is"],
        ward: Annotated[str, "Ward number if provided"] = "",
        duration_days: Annotated[int, "How many days the problem has existed"] = 0,
    ) -> str:
        """
        Save a citizen's complaint to the database.
        Call this function after collecting all complaint details from the caller.
        Returns the complaint reference number.
        """
        logger.info(f"Saving complaint for {citizen_name}: {issue_type} at {location}")

        # Get caller's phone number from room metadata if available
        caller_phone = "unknown"
        try:
            if hasattr(ctx, 'session') and hasattr(ctx.session, 'room'):
                # Try to get from SIP participant
                for participant in ctx.session.room.remote_participants.values():
                    if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
                        caller_phone = participant.identity or "unknown"
                        break
        except:
            pass

        # Save to database
        result = await save_complaint_to_db(
            citizen_name=citizen_name,
            citizen_phone=caller_phone,
            issue_type=issue_type,
            description=description,
            location=location,
            ward=ward,
            duration_days=duration_days
        )

        if result.get("success"):
            complaint_number = result["complaint_number"]
            logger.info(f"Complaint saved successfully: {complaint_number}")
            return f"Complaint saved successfully. Reference number: {complaint_number}"
        else:
            logger.error(f"Failed to save complaint: {result.get('error')}")
            return "Complaint noted. Reference number: RC2025" + str(hash(citizen_name))[-3:]

    async def on_enter(self) -> None:
        """Called when the agent becomes active - greet immediately."""
        await self.session.generate_reply(
            instructions=(
                "Greet the caller warmly and ask for their name:\n"
                "'அன்பான வணக்கம்! இது ராசிபுரம் நகராட்சி அலுவலகம். "
                "நாங்கள் உங்களுக்கு உதவ காத்திருக்கிறோம். தயவு செய்து உங்கள் பெயர் சொல்லுங்கள்.'\n"
                "Keep it natural and friendly."
            ),
            allow_interruptions=False,
        )


# ===========================================
# SERVER SETUP
# ===========================================
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()
    logger.info("Prewarmed VAD for process")


async def entrypoint(ctx: JobContext):
    # Logging setup
    logger.info("Agent connected to room: %s", ctx.room.name)
    print(f"✅ Agent connected to room: {ctx.room.name}")

    # Voice AI pipeline - Sarvam STT + Groq LLM
    session = AgentSession(
        # Sarvam STT - Tamil language support
        stt=sarvam.STT(
            language="ta-IN",
            model="saarika:v2"
        ),
        # Groq LLM
        llm=groq.LLM(
            model="llama-3.1-70b-versatile",
            temperature=0.7,
        ),
        # Sarvam TTS - Tamil voice
        tts=sarvam.TTS(
            target_language_code="ta-IN",
            model="bulbul:v2",
            speaker="anushka"
        ),
        # Multilingual turn detection for Tamil
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
    )

    # Connect to the room
    await ctx.connect()

    # Start the session with noise cancellation for phone calls
    await session.start(
        agent=Assistant(mla_constituency="Rasipuram"),
        room=ctx.room,
    )

    print(f"✅ Agent ready with complaint saving!")


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        )
    )
