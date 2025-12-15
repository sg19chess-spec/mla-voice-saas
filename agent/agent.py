"""
MLA Voice Agent - Main Agent Logic
==================================
This is the brain of the voice system. When a citizen calls:

1. LiveKit receives the call
2. This agent starts and greets the caller
3. Listens to the citizen's complaint (using Sarvam STT)
4. Uses Groq LLM to understand and respond
5. Collects complaint details through conversation
6. Saves the complaint to database
7. Confirms with the citizen

HOW TO RUN:
    python agent.py dev  (for development/testing)
    python agent.py      (for production)
"""

import os
import asyncio
import json
from typing import Optional
from dotenv import load_dotenv

from livekit import rtc
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
    llm,
)
from livekit.agents.voice_assistant import VoiceAssistant
from livekit.plugins import openai as openai_plugin

from tools import (
    save_complaint,
    get_tenant_by_phone,
    get_issue_types,
    log_call,
    TOOL_DEFINITIONS
)
from sarvam_stt import SarvamSTT, get_language_code
from sarvam_tts import SarvamTTS

# Load environment variables
load_dotenv()

# Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
LIVEKIT_URL = os.getenv("LIVEKIT_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")


# System prompt for the AI agent
SYSTEM_PROMPT = """You are a helpful AI assistant for an MLA (Member of Legislative Assembly) office in India. Your job is to:

1. Greet the caller warmly in their language (Tamil or Hindi or English)
2. Collect their complaint details:
   - Their name
   - Location of the problem
   - Type of issue (water, road, electricity, drainage, garbage, streetlight, or other)
   - Description of the problem
   - Any nearby landmark

3. Confirm all details with the caller
4. Save the complaint using the save_complaint function
5. Give them their complaint number and assure them it will be addressed

IMPORTANT GUIDELINES:
- Be polite and empathetic - citizens are calling with problems
- Speak clearly and simply
- If you don't understand, politely ask them to repeat
- Always confirm details before saving
- Give the complaint number at the end

CONVERSATION FLOW:
1. "Vanakkam/Namaste! Welcome to [MLA name]'s office. How can I help you?"
2. "May I have your name please?"
3. "What is the nature of your complaint? Is it about water, road, electricity, or something else?"
4. "Where exactly is this problem located?"
5. "Is there any landmark nearby?"
6. "Let me confirm: [repeat details]. Is this correct?"
7. [Save complaint]
8. "Your complaint number is [number]. We will look into this. Thank you for calling!"

You have access to these functions:
- save_complaint: Save the complaint to database
- get_issue_types: Get list of valid complaint categories
"""


class MLAVoiceAgent:
    """
    Main voice agent class that handles the conversation.
    """

    def __init__(self, ctx: JobContext, tenant_info: Optional[dict] = None):
        self.ctx = ctx
        self.tenant_info = tenant_info or {}
        self.tenant_id = tenant_info.get("id") if tenant_info else None
        self.language = "ta-IN"  # Default to Tamil

        # Get language from tenant config
        languages = tenant_info.get("languages", ["tamil"]) if tenant_info else ["tamil"]
        if languages:
            self.language = get_language_code(languages[0])

        # Initialize Sarvam AI
        self.stt = SarvamSTT(SARVAM_API_KEY)
        self.tts = SarvamTTS(SARVAM_API_KEY)

        # Collected complaint data
        self.complaint_data = {
            "citizen_name": None,
            "citizen_phone": None,
            "issue_type": None,
            "description": None,
            "location": None,
            "landmark": None
        }

    def get_system_prompt(self) -> str:
        """Get customized system prompt with MLA info."""
        mla_name = self.tenant_info.get("name", "the MLA")
        constituency = self.tenant_info.get("constituency", "this constituency")
        greeting = self.tenant_info.get("greeting_message", "")

        prompt = SYSTEM_PROMPT.replace("[MLA name]", mla_name)

        if greeting:
            prompt += f"\n\nUse this greeting: {greeting}"

        prompt += f"\n\nYou are serving {constituency} constituency."

        return prompt

    async def handle_function_call(self, function_name: str, arguments: dict) -> str:
        """
        Handle when the LLM wants to call a function/tool.

        Args:
            function_name: Name of the function to call
            arguments: Arguments for the function

        Returns:
            Result string to send back to LLM
        """
        if function_name == "save_complaint":
            # Add tenant_id and citizen phone
            result = await save_complaint(
                tenant_id=self.tenant_id,
                citizen_name=arguments.get("citizen_name"),
                citizen_phone=self.complaint_data.get("citizen_phone", "unknown"),
                issue_type=arguments.get("issue_type"),
                description=arguments.get("description"),
                location=arguments.get("location"),
                landmark=arguments.get("landmark")
            )

            if result.get("success"):
                return f"Complaint saved successfully! Complaint number: {result['complaint_number']}"
            else:
                return f"Failed to save complaint: {result.get('error', 'Unknown error')}"

        elif function_name == "get_issue_types":
            types = get_issue_types()
            return json.dumps(types)

        return "Unknown function"


async def entrypoint(ctx: JobContext):
    """
    Main entry point when a call/session starts.

    This function is called by LiveKit when:
    1. A phone call comes in (via SIP)
    2. Someone joins from the web
    """
    print(f"Agent starting for room: {ctx.room.name}")

    # Get room metadata (contains caller info)
    room_metadata = ctx.room.metadata or "{}"
    try:
        metadata = json.loads(room_metadata)
    except:
        metadata = {}

    # Get caller phone from SIP headers or metadata
    caller_phone = metadata.get("caller_phone", "unknown")
    called_number = metadata.get("called_number", "")

    # Find which MLA (tenant) this call is for
    tenant_info = None
    if called_number:
        tenant_info = await get_tenant_by_phone(called_number)
        if tenant_info:
            print(f"Call for MLA: {tenant_info['name']} ({tenant_info['constituency']})")

    # Create our agent
    agent = MLAVoiceAgent(ctx, tenant_info)
    agent.complaint_data["citizen_phone"] = caller_phone

    # Set up Groq LLM (OpenAI-compatible API)
    groq_llm = openai_plugin.LLM(
        model="llama-3.1-8b-instant",  # Fast Groq model
        base_url="https://api.groq.com/openai/v1",
        api_key=GROQ_API_KEY,
    )

    # Create the voice assistant
    # Note: For full Sarvam integration, we'd need custom STT/TTS plugins
    # For now, using OpenAI's Whisper for STT and basic TTS
    assistant = VoiceAssistant(
        vad=None,  # Voice Activity Detection (use default)
        stt=openai_plugin.STT(),  # Will replace with Sarvam
        llm=groq_llm,
        tts=openai_plugin.TTS(voice="alloy"),  # Will replace with Sarvam
        chat_ctx=llm.ChatContext().append(
            role="system",
            text=agent.get_system_prompt()
        ),
        fnc_ctx=llm.FunctionContext(),  # For tool calling
    )

    # Register tool functions
    @assistant.fnc_ctx.ai_callable(description="Save a citizen complaint to the database")
    async def save_complaint_tool(
        citizen_name: str,
        issue_type: str,
        description: str,
        location: str = "",
        landmark: str = ""
    ) -> str:
        """Save complaint and return confirmation."""
        result = await save_complaint(
            tenant_id=agent.tenant_id,
            citizen_name=citizen_name,
            citizen_phone=agent.complaint_data.get("citizen_phone", "unknown"),
            issue_type=issue_type,
            description=description,
            location=location,
            landmark=landmark
        )

        if result.get("success"):
            return f"Complaint registered! Number: {result['complaint_number']}"
        return f"Error: {result.get('error', 'Could not save complaint')}"

    @assistant.fnc_ctx.ai_callable(description="Get valid complaint categories")
    async def get_categories() -> str:
        """Return list of issue types."""
        types = get_issue_types()
        return ", ".join([t["type"] for t in types])

    # Connect to the room
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Start the assistant
    assistant.start(ctx.room)

    # Initial greeting
    mla_name = tenant_info.get("name", "the MLA") if tenant_info else "the MLA"
    greeting = f"Vanakkam! Welcome to {mla_name}'s office. How can I help you today?"

    await assistant.say(greeting, allow_interruptions=True)

    # Log the call start
    await log_call(
        tenant_id=agent.tenant_id,
        caller_phone=caller_phone,
        called_number=called_number,
        call_status="in_progress",
        livekit_room_id=ctx.room.name
    )


def prewarm(proc: JobProcess):
    """
    Called before the agent starts to load resources.
    """
    proc.userdata["sarvam_ready"] = True


if __name__ == "__main__":
    # Run the agent
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        )
    )
