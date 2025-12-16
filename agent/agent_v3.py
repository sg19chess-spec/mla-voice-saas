"""
MLA Voice Agent - With Tasks for Step-by-Step Collection
"""
import logging
import time
from dataclasses import dataclass
from typing import Annotated
from complaint_tools import save_complaint_to_db
from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent, AgentTask, AgentServer, AgentSession, JobContext, JobProcess,
    RunContext, function_tool, cli, room_io,
)
from livekit.plugins import groq, noise_cancellation, sarvam, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")
logger.setLevel(logging.INFO)
load_dotenv(".env.local")

# Global room reference (needed because self.session.room may not work)
ROOM = None
ROOM_NAME = None


def get_gender_from_name(name: str) -> str:
    """Detect gender from Indian/Tamil name. Returns 'male' or 'female'."""
    name_lower = name.lower().strip()

    # Common female name endings/patterns in Tamil/Indian names
    female_patterns = [
        'priya', 'lakshmi', 'devi', 'mala', 'valli', 'selvi', 'mari', 'ammal',
        'amma', 'akka', 'sri', 'uma', 'geetha', 'seetha', 'radha', 'padma',
        'kamala', 'vijaya', 'jaya', 'saroja', 'pushpa', 'meena', 'leela',
        'shanti', 'rani', 'banu', 'begum', 'fatima', 'ayesha', 'nisha',
        'anitha', 'sunitha', 'kavitha', 'lalitha', 'vanitha', 'sangeetha',
        'deepa', 'ramya', 'divya', 'sowmya', 'pooja', 'sneha', 'swathi',
        'keerthana', 'harini', 'varshini', 'nandhini', 'ranjani', 'bhavani'
    ]

    # Common male name endings/patterns
    male_patterns = [
        'kumar', 'raj', 'rajan', 'krishnan', 'nathan', 'muthu', 'vel',
        'pandian', 'selvam', 'moorthy', 'swamy', 'lingam', 'kannan',
        'mani', 'babu', 'reddy', 'naidu', 'pillai', 'khan', 'sheikh',
        'ram', 'ganesh', 'suresh', 'ramesh', 'mahesh', 'dinesh', 'rajesh',
        'prakash', 'venkatesh', 'srinivas', 'anand', 'arun', 'vijay',
        'senthil', 'karthi', 'surya', 'ajith', 'vikram', 'gautham', 'karthik'
    ]

    # Check female patterns first
    for pattern in female_patterns:
        if pattern in name_lower or name_lower.endswith(pattern):
            return 'female'

    # Check male patterns
    for pattern in male_patterns:
        if pattern in name_lower or name_lower.endswith(pattern):
            return 'male'

    # Default heuristics for Tamil names
    if name_lower.endswith(('a', 'i', 'ya')) and not name_lower.endswith(('anna', 'appa')):
        return 'female'

    # Default to male if uncertain
    return 'male'


def get_honorific(name: str) -> str:
    """Get Tamil honorific based on detected gender."""
    gender = get_gender_from_name(name)
    return "மேடம்" if gender == 'female' else "சார்"


@dataclass
class CollectedName:
    name: str

@dataclass
class CollectedIssue:
    issue: str
    description: str

@dataclass
class CollectedLocation:
    location: str
    ward: str


class CollectNameTask(AgentTask[CollectedName]):
    """Task to collect caller's name only."""

    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions="""
உங்கள் வேலை: பெயர் மட்டும் கேட்கவும்.

RULES:
- Ask ONLY for name, nothing else
- Wait for response
- If unclear, ask again politely
- Once you have the name, call got_name function
- Do NOT use sir/madam - just ask neutrally
            """,
            chat_ctx=chat_ctx
        )

    async def on_enter(self) -> None:
        """Ask for name immediately."""
        await self.session.generate_reply(
            instructions="Ask in Tamil: 'உங்கள் பெயர் என்ன?'"
        )

    @function_tool()
    async def got_name(
        self,
        ctx: RunContext,
        name: Annotated[str, "The caller's name"]
    ) -> None:
        """Call this when you have the caller's name."""
        logger.info(f"✅ Got name: {name}")
        self.complete(CollectedName(name=name))


class CollectIssueTask(AgentTask[CollectedIssue]):
    """Task to collect issue type and description only."""

    def __init__(self, caller_name: str, honorific: str, chat_ctx=None) -> None:
        self._caller_name = caller_name
        self._honorific = honorific
        super().__init__(
            instructions=f"""
உங்கள் வேலை: பிரச்சினை வகை மட்டும் கேட்கவும்.

Caller name: {caller_name}
Honorific: {honorific}

RULES:
- Ask ONLY about the problem, nothing else
- Wait for response
- If unclear, ask for more details
- Once you understand the issue, call got_issue function
- Address caller as "{caller_name} {honorific}"

VALID ISSUES: சாலை, தண்ணீர், மின்சாரம், வடிகால், குப்பை, தெரு விளக்கு
            """,
            chat_ctx=chat_ctx
        )

    async def on_enter(self) -> None:
        """Ask for issue immediately."""
        await self.session.generate_reply(
            instructions=f"Ask in Tamil: 'சரி {self._caller_name} {self._honorific}, என்ன பிரச்சினை சொல்லுங்க?'"
        )

    @function_tool()
    async def got_issue(
        self,
        ctx: RunContext,
        issue_type: Annotated[str, "Type: road/water/electricity/drainage/garbage/streetlight"],
        description: Annotated[str, "What is the problem"]
    ) -> None:
        """Call this when you understand the issue."""
        logger.info(f"✅ Got issue: {issue_type} - {description}")
        self.complete(CollectedIssue(issue=issue_type, description=description))


class CollectLocationTask(AgentTask[CollectedLocation]):
    """Task to collect location and ward only."""

    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions="""
உங்கள் வேலை: இடம் மற்றும் வார்டு மட்டும் கேட்கவும்.

RULES:
- First ask for location/area
- Then ask for ward number
- If they don't know ward, say "பரவாயில்ல" and proceed
- ONLY call got_location after getting BOTH location AND ward (or they said they don't know ward)
            """,
            chat_ctx=chat_ctx
        )

    async def on_enter(self) -> None:
        """Ask for location immediately."""
        await self.session.generate_reply(
            instructions="Ask in Tamil: 'புரிந்தது. இது எந்த பகுதி அல்லது தெருவில்?'"
        )

    @function_tool()
    async def got_location(
        self,
        ctx: RunContext,
        location: Annotated[str, "Area or street name"],
        ward: Annotated[str, "Ward number, empty if unknown"] = ""
    ) -> None:
        """Call this when you have the location."""
        logger.info(f"✅ Got location: {location}, Ward: {ward}")
        self.complete(CollectedLocation(location=location, ward=ward))


class ComplaintAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""
நீங்கள் ராசிபுரம் நகராட்சி அலுவலகத்தின் AI உதவியாளர்.
Be friendly, speak Tamil, use caller's name once known.
Do NOT use sir/madam or any gender terms.
            """,
        )
        self._start_time = time.time()

    async def on_enter(self) -> None:
        """Greet and start collecting data step by step."""
        self._start_time = time.time()

        # Step 1: Greet
        await self.session.generate_reply(
            instructions="Greet in Tamil: 'வணக்கம்! இது ராசிபுரம் நகராட்சி அலுவலகம். உங்களுக்கு எப்படி உதவ முடியும்?'"
        )

        # Step 2: Collect name
        logger.info("📝 Starting name collection...")
        name_result = await CollectNameTask(chat_ctx=self.chat_ctx)
        caller_name = name_result.name if name_result else "நண்பரே"
        honorific = get_honorific(caller_name)
        logger.info(f"📌 Name collected: {caller_name}, Honorific: {honorific}")

        # Step 3: Collect issue
        logger.info("📝 Starting issue collection...")
        issue_result = await CollectIssueTask(caller_name, honorific, chat_ctx=self.chat_ctx)
        issue_type = issue_result.issue if issue_result else "other"
        description = issue_result.description if issue_result else ""
        logger.info(f"📌 Issue collected: {issue_type} - {description}")

        # Step 4: Collect location
        logger.info("📝 Starting location collection...")
        location_result = await CollectLocationTask(chat_ctx=self.chat_ctx)
        location = location_result.location if location_result else ""
        ward = location_result.ward if location_result else ""
        logger.info(f"📌 Location collected: {location}, Ward: {ward}")

        # Step 5: Get caller phone from room name or SIP participant
        caller_phone = "unknown"
        try:
            global ROOM, ROOM_NAME
            import re

            # Method 1: Extract from room name (most reliable)
            # Room name format: call-_+916369675744_VeqLvMNp9z5R
            if ROOM_NAME:
                logger.info(f"📞 Room name: {ROOM_NAME}")
                # Look for phone number pattern: +91 followed by 10 digits
                match = re.search(r'\+91\d{10}', ROOM_NAME)
                if match:
                    caller_phone = match.group()
                    logger.info(f"📞 Phone from room name: {caller_phone}")

            # Method 2: If not found, try SIP participant identity
            if caller_phone == "unknown" and ROOM:
                for p in ROOM.remote_participants.values():
                    identity = p.identity or ""
                    logger.info(f"📞 Checking participant: {identity}")

                    # Check for sip_ prefix in identity
                    if identity.startswith("sip_"):
                        # Extract phone: sip_+916369675744 -> +916369675744
                        caller_phone = identity[4:]  # Remove "sip_" prefix
                        logger.info(f"📞 Phone from SIP participant: {caller_phone}")
                        break
        except Exception as e:
            logger.error(f"❌ Failed to extract phone: {e}")

        # Step 6: Save complaint
        duration = int(time.time() - self._start_time)

        # Build structured summary
        summary = f"Name: {caller_name}\nIssue: {issue_type}\nProblem: {description}\nLocation: {location}\nWard: {ward}"

        # Build full conversation transcript
        full_transcript = []
        try:
            for msg in self.chat_ctx.messages:
                role = "Agent" if msg.role == "assistant" else "User"
                content = msg.content
                # Extract text from content if it's a list
                if isinstance(content, list):
                    text_parts = [item.text if hasattr(item, 'text') else str(item) for item in content]
                    content = ' '.join(text_parts)
                full_transcript.append(f"{role}: {content}")
        except Exception as e:
            logger.error(f"Error building transcript: {e}")
            full_transcript = [f"Summary: {summary}"]

        # Combine summary and full conversation
        complete_transcript = f"=== SUMMARY ===\n{summary}\n\n=== FULL CONVERSATION ===\n" + "\n".join(full_transcript)

        logger.info("=" * 60)
        logger.info("💾 SAVING COMPLAINT WITH DATA:")
        logger.info(f"   Name: {caller_name}")
        logger.info(f"   Phone: {caller_phone}")
        logger.info(f"   Issue: {issue_type}")
        logger.info(f"   Description: {description}")
        logger.info(f"   Location: {location}")
        logger.info(f"   Ward: {ward}")
        logger.info(f"   Duration: {duration}s")
        logger.info(f"   Transcript lines: {len(full_transcript)}")
        logger.info("=" * 60)

        result = await save_complaint_to_db(
            citizen_name=caller_name,
            citizen_phone=caller_phone,
            issue_type=issue_type,
            description=description,
            location=location,
            ward=ward,
            transcript=complete_transcript,
            call_duration_seconds=duration
        )

        ref = result.get('complaint_number', 'RC000')
        logger.info(f"✅ SAVED SUCCESSFULLY: {ref} | Phone: {caller_phone}")

        # Step 7: Confirm and ask if anything else
        await self.session.generate_reply(
            instructions=f"Thank caller in Tamil: 'நன்றி {caller_name} {honorific}! உங்கள் புகார் பதிவு செய்யப்பட்டது. புகார் எண் {ref}. விரைவில் கவனிக்கப்படும். வேற ஏதாவது உதவி வேணுமா?'"
        )

    @function_tool()
    async def end_call(
        self,
        ctx: RunContext,
        reason: Annotated[str, "Reason"] = "done"
    ) -> str:
        """End the call politely."""
        return "Say goodbye: 'நன்றி! வணக்கம்!'"


server = AgentServer()

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

server.setup_fnc = prewarm

@server.rtc_session(agent_name="gautham-agent")
async def entrypoint(ctx: JobContext):
    global ROOM, ROOM_NAME
    ROOM = ctx.room
    ROOM_NAME = ctx.room.name
    logger.info(f"🎙️ Agent joined room: {ROOM_NAME}")

    session = AgentSession(
        stt=sarvam.STT(language="ta-IN", model="saarika:v2"),
        llm=groq.LLM(model="openai/gpt-oss-120b", temperature=0.3),
        tts=sarvam.TTS(target_language_code="ta-IN", model="bulbul:v2", speaker="anushka"),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
    )

    await session.start(
        agent=ComplaintAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )
    await ctx.connect()
    logger.info("✅ Agent connected and ready!")

if __name__ == "__main__":
    cli.run_app(server)
