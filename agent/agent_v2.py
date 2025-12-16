"""
MLA Voice Agent v2 - With Tasks and Full Data Collection
=========================================================
Collects: name, issue_type, description, location, ward, landmark, transcript
Saves all data to Supabase including conversation transcript
Uses GPT-OSS 120B model
"""

import logging
import time
from dataclasses import dataclass
from typing import Annotated
from complaint_tools import save_complaint_to_db, log_call
from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentTask,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    function_tool,
    cli,
    room_io,
)
from livekit.plugins import groq, noise_cancellation, sarvam, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")
logger.setLevel(logging.INFO)

load_dotenv(".env.local")


# ===========================================
# DATA CLASS FOR COMPLAINT RESULT
# ===========================================
@dataclass
class ComplaintResult:
    """Complete complaint data collected from caller."""
    citizen_name: str
    issue_type: str
    description: str
    location: str
    ward: str
    landmark: str
    complaint_number: str
    transcript: str


# ===========================================
# TASK: COLLECT COMPLAINT DETAILS
# ===========================================
class CollectComplaintTask(AgentTask[ComplaintResult]):
    """
    Task to collect all complaint details from the caller.
    Collects: name, issue type, description, location, ward, landmark
    Builds transcript of the conversation
    """

    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions="""
நீங்கள் ராசிபுரம் நகராட்சியின் புகார் சேகரிப்பு உதவியாளர்.

COLLECT THESE DETAILS (ONE AT A TIME):
1. பெயர் (Name) - Ask for caller's name
2. பிரச்சினை வகை (Issue type) - road/water/electricity/drainage/garbage/streetlight
3. விளக்கம் (Description) - What exactly is the problem? Be specific.
4. இடம் (Location) - Which area/street?
5. வார்டு (Ward) - Ward number (if known, otherwise skip)
6. அடையாளம் (Landmark) - Any nearby landmark?

RULES:
- Ask ONE question at a time
- Wait for answer before next question
- Acknowledge briefly: "சரி" or "புரிஞ்சது"
- Be respectful: Use "சார்" or "மேடம்"
- Build a clear description/summary of the problem

VALID MUNICIPALITY ISSUES:
✅ சாலை (road) - potholes, damage, repairs
✅ தண்ணீர் (water) - supply issues, leaks, no water
✅ மின்சாரம் (electricity) - power cuts, street lights
✅ வடிகால் (drainage) - blocked drains, sewage
✅ குப்பை (garbage) - not collected, dumping
✅ தெரு விளக்கு (streetlight) - not working

INVALID (Politely redirect):
❌ Personal problems, health, money, legal, family issues
→ Say: "இது நகராட்சி விஷயம் இல்ல. வேற நகராட்சி சம்பந்தமா இருக்கா?"

After collecting ALL details, call record_complaint function with complete info.
            """,
            chat_ctx=chat_ctx,
        )
        self._transcript_parts = []
        self._start_time = time.time()

    async def on_enter(self) -> None:
        """Start collecting - ask for name."""
        self._transcript_parts.append("Agent: வணக்கம்! உங்கள் பெயர் என்ன?")
        await self.session.generate_reply(
            instructions="Ask for caller's name in Tamil: 'உங்கள் பெயர் என்ன சார்/மேடம்?'"
        )

    @function_tool()
    async def record_complaint(
        self,
        ctx: RunContext,
        citizen_name: Annotated[str, "Full name of the caller"],
        issue_type: Annotated[str, "Category: road/water/electricity/drainage/garbage/streetlight/other"],
        description: Annotated[str, "Clear summary of the main problem - be specific and detailed"],
        location: Annotated[str, "Area, street, or address where problem is located"],
        ward: Annotated[str, "Ward number if provided, otherwise empty"] = "",
        landmark: Annotated[str, "Nearby landmark for easy identification"] = "",
    ) -> None:
        """
        Save the complete complaint after collecting all details.
        Call this only after you have: name, issue type, description, location.
        """
        # Build transcript
        self._transcript_parts.append(f"Collected: Name={citizen_name}, Issue={issue_type}, Location={location}")
        transcript = "\n".join(self._transcript_parts)

        # Calculate duration
        duration = int(time.time() - self._start_time)

        logger.info(f"💾 Saving complaint for {citizen_name}: {issue_type} at {location}")

        # Get caller phone from session if available
        caller_phone = "unknown"
        try:
            for participant in ctx.session.room.remote_participants.values():
                if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
                    caller_phone = participant.identity or "unknown"
                    break
        except:
            pass

        # Save to database with all fields
        result = await save_complaint_to_db(
            citizen_name=citizen_name,
            citizen_phone=caller_phone,
            issue_type=issue_type,
            description=description,
            location=location,
            ward=ward,
            landmark=landmark,
            transcript=transcript,
            call_duration_seconds=duration
        )

        complaint_number = result.get('complaint_number', 'RC000')
        logger.info(f"✅ Complaint saved: {complaint_number}")

        # Complete task with full result
        self.complete(ComplaintResult(
            citizen_name=citizen_name,
            issue_type=issue_type,
            description=description,
            location=location,
            ward=ward,
            landmark=landmark,
            complaint_number=complaint_number,
            transcript=transcript
        ))

    @function_tool()
    async def not_municipality_issue(self, ctx: RunContext) -> None:
        """Use when caller's issue is NOT related to municipality services."""
        await ctx.session.generate_reply(
            instructions="""
            Politely explain in Tamil:
            'இது நகராட்சி சம்பந்தமான விஷயம் இல்ல சார்/மேடம்.
            சாலை, தண்ணீர், மின்சாரம், வடிகால், குப்பை, தெரு விளக்கு - இது மாதிரி விஷயங்களுக்கு மட்டும் உதவ முடியும்.
            வேற நகராட்சி சம்பந்தமான பிரச்சினை இருக்கா?'
            Wait for their response.
            """
        )


# ===========================================
# MAIN AGENT
# ===========================================
class Assistant(Agent):
    """Main agent that greets and handles complaint collection."""

    def __init__(self, mla_constituency: str = None) -> None:
        super().__init__(
            instructions=f"""
நீங்கள் ராசிபுரம் நகராட்சி அலுவலகத்தின் AI குரல் உதவியாளர்.

YOUR JOB:
1. Greet callers warmly in Tamil
2. Collect their municipality complaints
3. Save all details to database
4. Give them a reference number

BEHAVIOR:
- Be polite, professional, helpful
- Use "சார்" for men, "மேடம்" for women
- Speak clearly in Tamil
- Don't repeat yourself unnecessarily
- After giving reference number, ask if they need anything else
- If no, say goodbye politely

VALID COMPLAINTS (Municipality only):
- Roads (சாலை) - potholes, repairs
- Water (தண்ணீர்) - supply, leaks
- Electricity (மின்சாரம்) - street lights, power
- Drainage (வடிகால்) - blocks, sewage
- Garbage (குப்பை) - collection
- Street lights (தெரு விளக்கு)

Constituency: {mla_constituency or 'Rasipuram'}
Language: Tamil (தமிழ்)
            """,
        )
        self._call_start_time = None

    async def on_enter(self) -> None:
        """Called when agent becomes active - greet and start collection."""
        self._call_start_time = time.time()

        # Greet the caller warmly
        await self.session.generate_reply(
            instructions="""
            Greet the caller warmly in Tamil:
            'அன்பான வணக்கம்! இது ராசிபுரம் நகராட்சி அலுவலகம்.
            உங்களுக்கு எப்படி உதவ முடியும்?'
            Be warm and welcoming.
            """
        )

        # Start complaint collection task
        result = await CollectComplaintTask(chat_ctx=self.chat_ctx)

        if result:
            # Complaint saved - give reference number ONCE and ask if need more help
            await self.session.generate_reply(
                instructions=f"""
                Thank the caller and provide the reference number in Tamil:

                'நன்றி {result.citizen_name} சார்/மேடம்! உங்கள் புகார் பதிவு செய்யப்பட்டது.
                புகார் எண்: {result.complaint_number}

                {result.issue_type} பிரச்சினை - {result.location} - விரைவில் கவனிக்கப்படும்.

                வேறு ஏதேனும் உதவி தேவையா?'

                IMPORTANT:
                - Say reference number clearly
                - Do NOT repeat that details were saved
                - If they say no more help needed, say 'நன்றி! வணக்கம்!' and end politely
                """
            )

    @function_tool()
    async def new_complaint(self, ctx: RunContext) -> str:
        """Start collecting a new complaint if caller has another issue."""
        result = await CollectComplaintTask(chat_ctx=self.chat_ctx)
        if result:
            return f"New complaint {result.complaint_number} saved"
        return "Complaint not filed"

    @function_tool()
    async def end_call(self, ctx: RunContext) -> None:
        """End the call politely when caller has no more issues."""
        await ctx.session.generate_reply(
            instructions="Say goodbye politely in Tamil: 'நன்றி! உங்கள் புகார் விரைவில் தீர்க்கப்படும். வணக்கம்!'"
        )


# ===========================================
# SERVER SETUP
# ===========================================
server = AgentServer()


def prewarm(proc: JobProcess):
    """Preload VAD model for faster startup."""
    proc.userdata["vad"] = silero.VAD.load()
    logger.info("Prewarmed VAD for process")


server.setup_fnc = prewarm


@server.rtc_session(agent_name="gautham-agent")
async def my_agent(ctx: JobContext):
    """Main entry point for each call."""
    ctx.log_context_fields = {"room": ctx.room.name}

    logger.info("Agent connected to room: %s", ctx.room.name)
    print(f"✅ Agent connected to room: {ctx.room.name}")

    # Create agent session with Sarvam STT/TTS + Groq LLM
    session = AgentSession(
        # Sarvam STT - Tamil speech recognition
        stt=sarvam.STT(
            language="ta-IN",
            model="saarika:v2"
        ),
        # Groq LLM - GPT-OSS 120B model
        llm=groq.LLM(
            model="openai/gpt-oss-120b",
            temperature=0.7,
        ),
        # Sarvam TTS - Tamil voice synthesis
        tts=sarvam.TTS(
            target_language_code="ta-IN",
            model="bulbul:v2",
            speaker="anushka"
        ),
        # Turn detection for Tamil
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    # Start session with agent and room configuration
    await session.start(
        agent=Assistant(mla_constituency="Rasipuram"),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                # Telephony noise cancellation for SIP calls
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )

    # Connect to room
    await ctx.connect()

    print(f"✅ Agent ready: Sarvam STT/TTS + Groq GPT-OSS 120B")


if __name__ == "__main__":
    cli.run_app(server)
