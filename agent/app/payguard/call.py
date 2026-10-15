"""The verification call: an ADK agent on Gemini Live phones the number from the check and asks the payee to
state the transfer.

The agent is told whom it is calling and why, never the account or the amount being sent. It records what
the payee states with `record_answer`; code compares that with the transfer (`verify.compare`) and the
approval queue logs the outcome. The model decides nothing: a call it cannot finish confirms nothing.

In the demo the "phone" is the browser: the person playing the payee holds a button to talk, and each turn
is one request whose response streams the agent's voice as it is spoken. The agent runs on ADK's
`Runner.run_live`, which stays open between turns, so the payee's words go from the browser to the agent and
to Gemini, and the result never comes from the browser. One call runs at a time; a call left idle is closed.
"""

import asyncio
import base64
import contextlib
import logging
import os
import time
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager
from types import SimpleNamespace
from typing import Any, Literal

from google import genai
from google.adk.agents import LlmAgent
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.events import Event as AdkEvent
from google.adk.models import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.adk.utils.variant_utils import GoogleLLMVariant
from google.genai import types
from pydantic import BaseModel, Field, ValidationError

from . import demo, ledger
from .approvals import AGENT, DecisionError, store
from .models import Contact, Payment
from .verify import Outcome, Statement, Turn

LIVE_MODEL = os.getenv("LIVE_MODEL", "gemini-3.8-live")
LIVE_LOCATION = os.getenv("LIVE_LOCATION", "us-central1")
LANGUAGE = "en-US"  # fixed: Live can drift between languages mid-call
PAYER = "Miori Koumuten"
MAX_TURNS = 10
IDLE_SECONDS = 180
REPLY_TIMEOUT = 30
FOLLOW_UP_TIMEOUT = 8  # after record_answer, how long to wait for the agent to say goodbye
MAX_AUDIO_BYTES = 30 * 16_000 * 2  # 30 s of 16 kHz 16-bit mono
RECORD = "record_answer"
APP_NAME = "payguard_call"
ANSWERED = "(The call is answered.)"  # tells the agent to start speaking
# How the agent says the demo's names in English; the ledger keeps them in Japanese.
NAMES_EN = {
    "ツバクロ建材株式会社": "Tsubakuro Kenzai",
    "ツバクロ建材 営業部 田中": "Mr. Tanaka in sales",
    "株式会社ヒサゴ設備": "Hisago Setsubi",
    "ヒサゴ設備 経理部": "the accounts department",
    "ノギク運送有限会社": "Nogiku Unso",
    "ノギク運送 事務所": "the office",
    "合同会社ルリカケ": "Rurikake LLC",
    "佐藤 一郎": "Mr. Ichiro Sato",
    "代表取締役": "the CEO",
    "鈴木 花子": "Ms. Hanako Suzuki",
    "経理": "accounts",
}

logger = logging.getLogger("payguard.call")

RECORD_ANSWER = types.FunctionDeclaration(
    name=RECORD,
    description=(
        "Record what the person stated. Call it once, at the end, after they have stated the bank account and the "
        "amount, refused to, or said they made no such request. Record only what they said, never a guess."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "bank_name": types.Schema(type="STRING"),
            "branch_name": types.Schema(type="STRING"),
            "account_number": types.Schema(type="STRING", description="The digits exactly as stated"),
            "account_holder": types.Schema(type="STRING"),
            "amount": types.Schema(type="INTEGER", description="In yen"),
            "refused": types.Schema(type="BOOLEAN", description="They would not state the account or the amount"),
            "denied": types.Schema(type="BOOLEAN", description="They say they made no such request"),
        },
    ),
)


class CallError(Exception):
    pass


class Event(BaseModel):
    """One line of the streamed reply.

    audio: a chunk of the agent's voice (base64 16-bit PCM, 24 kHz mono). said / heard: transcript text of
    the agent / the payee as it arrives. done: the call is over and code has decided. error: the call dropped.
    """

    type: Literal["audio", "said", "heard", "done", "error"]
    data: str | None = None
    text: str | None = None
    outcome: Outcome | None = None


def _en(name: str) -> str:
    return NAMES_EN.get(name, name)


def brief(payment: Payment, contact: Contact) -> str:
    """What the agent is told. It carries no account number and no amount."""
    vendor = next((v for v in ledger.current().vendors if v.id == payment.vendor_id), None)
    person = next((p for p in ledger.current().people if p.contact.phone == contact.phone), None)
    if person is not None:
        who = f"{_en(contact.name)}, {_en(person.role)} of {PAYER}"
        ask = (
            "A request for a bank transfer in their name is waiting for approval. Ask whether they asked for a "
            "transfer. If they did, ask them to state the payee, the bank, the account number and the amount."
        )
    else:
        org = _en(vendor.name if vendor else payment.payee_name)
        who = f"{_en(contact.name)} at {org}, a supplier of {PAYER}"
        ask = (
            f"{PAYER} is about to pay {org}. Ask them to state the bank, branch, account number, account holder "
            "and amount they expect to be paid, so the transfer can be checked."
        )
    return (
        f"You are an automated verification call from the accounts payable team of {PAYER}. "
        f"You are calling {who}, on a number from {PAYER}'s own records. "
        "Speak English only. Start by saying in one sentence that this is an automated call and why. "
        f"{ask} "
        "You do not know the account or the amount, and you must never suggest one, read one back as correct, "
        "or say whether what they state matches, or what will happen to the payment. If they ask, say the "
        "accounts team will check it. "
        "If they say they made no such request, or will not state it, do not press. "
        "The account number and the amount are what matter: once both have been stated, ask for nothing more. "
        f"When you have the answer, call {RECORD} once, thank them and end the call. "
        "Keep every reply to one or two short sentences."
    )


def run_config() -> RunConfig:
    return RunConfig(
        streaming_mode=StreamingMode.BIDI,
        response_modalities=[types.Modality.AUDIO],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        speech_config=types.SpeechConfig(language_code=LANGUAGE),
        # Push to talk: the browser marks where the payee starts and stops speaking.
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(disabled=True)
        ),
    )


Connect = Callable[[types.LiveConnectConfig], AbstractAsyncContextManager]


def live_connect(config: types.LiveConnectConfig) -> AbstractAsyncContextManager:
    client = genai.Client(vertexai=True, project=os.environ.get("GOOGLE_CLOUD_PROJECT"), location=LIVE_LOCATION)
    return client.aio.live.connect(model=LIVE_MODEL, config=config)


class LiveGemini(Gemini):
    """ADK's Gemini, connecting through `transport`: Live runs in `LIVE_LOCATION`, not the reader's location."""

    transport: Any = Field(default=None, exclude=True)

    @property
    def _live_api_client(self) -> Any:
        connect = self.transport
        return SimpleNamespace(aio=SimpleNamespace(live=SimpleNamespace(connect=lambda model, config: connect(config))))

    @property
    def _api_backend(self) -> GoogleLLMVariant:
        return GoogleLLMVariant.VERTEX_AI


class RecordAnswer(BaseTool):
    """The agent's one tool: it records what the payee stated, and code compares it later."""

    def __init__(self, call: "Call") -> None:
        super().__init__(name=RECORD, description=RECORD_ANSWER.description or "")
        self.call = call

    def _get_declaration(self) -> types.FunctionDeclaration:
        return RECORD_ANSWER

    async def run_async(self, *, args: dict[str, Any], tool_context: ToolContext) -> dict[str, bool]:
        if self.call.statement is None:
            try:
                self.call.statement = Statement.model_validate(args or {})
            except ValidationError:
                self.call.statement = Statement()  # an answer code cannot read confirms nothing
        return {"recorded": True}


class Call:
    """One call: an ADK agent on `Runner.run_live`, fed by a `LiveRequestQueue`.

    The run lasts the whole call, across the payee's HTTP turns, so a task moves its events into a queue and
    each turn reads that queue up to the agent's turn_complete.
    """

    def __init__(self, payment_id: str, payment: Payment, contact: Contact, connect: Connect) -> None:
        self.payment_id = payment_id
        self.transcript: list[Turn] = []
        self.statement: Statement | None = None
        self.turns = 0
        self.last = time.monotonic()
        instruction = brief(payment, contact)
        self.agent = LlmAgent(
            name="verification_call",
            model=LiveGemini(model=LIVE_MODEL, transport=connect),
            instruction=lambda _ctx: instruction,  # a provider, so the brief is not read as a template
            tools=[RecordAnswer(self)],
        )
        self.sessions = InMemorySessionService()
        self.runner = Runner(app_name=APP_NAME, agent=self.agent, session_service=self.sessions)
        self.requests = LiveRequestQueue()
        self.events: asyncio.Queue[AdkEvent | BaseException] = asyncio.Queue()
        self.task: asyncio.Task | None = None
        self.head: AdkEvent | None = None

    async def start(self) -> None:
        """Connect and have the call answered; fails here, before anything streams, if Live cannot be reached."""
        session = await self.sessions.create_session(app_name=APP_NAME, user_id=self.payment_id)
        self.task = asyncio.create_task(self._pump(session.id))
        self.say(ANSWERED, log=False)
        async with asyncio.timeout(REPLY_TIMEOUT):
            self.head = await self._next()

    async def _pump(self, session_id: str) -> None:
        try:
            async for event in self.runner.run_live(
                user_id=self.payment_id, session_id=session_id, live_request_queue=self.requests, run_config=run_config()
            ):
                await self.events.put(event)
        except Exception as e:
            await self.events.put(e)
        else:
            await self.events.put(CallError("The call ended."))

    async def _next(self) -> AdkEvent:
        if self.head is not None:
            event, self.head = self.head, None
            return event
        event = await self.events.get()
        if isinstance(event, BaseException):
            raise event
        if event.error_code:
            raise CallError(event.error_code)
        return event

    def say(self, text: str, log: bool = True) -> None:
        self.requests.send_content(types.Content(role="user", parts=[types.Part(text=text)]))
        if log:
            self.transcript.append(Turn(speaker="payee", text=text))

    def speak(self, audio: bytes) -> None:
        self.requests.send_activity_start()
        self.requests.send_realtime(types.Blob(data=audio, mime_type="audio/pcm;rate=16000"))
        self.requests.send_activity_end()

    async def listen(self) -> AsyncIterator[Event]:
        """Stream the agent's reply. The turn that records the answer ends there; the goodbye comes next."""
        heard: list[str] = []
        said: list[str] = []
        recorded = self.statement is not None
        async for event in self._turn(heard, said):
            yield event
        if self.statement is not None and not recorded:
            try:
                async with asyncio.timeout(FOLLOW_UP_TIMEOUT):
                    async for event in self._turn(heard, said):
                        yield event
            except TimeoutError:
                pass  # the answer is recorded; a missing goodbye changes nothing
        if heard:
            self.transcript.append(Turn(speaker="payee", text="".join(heard).strip()))
        if said:
            self.transcript.append(Turn(speaker="agent", text="".join(said).strip()))
        self.last = time.monotonic()

    async def _turn(self, heard: list[str], said: list[str]) -> AsyncIterator[Event]:
        # Transcripts arrive as pieces, then once more whole (finished); the whole one is used only if no pieces came.
        pieces = {"heard": False, "said": False}
        while True:
            event = await self._next()
            for kind, piece, into in (("heard", event.input_transcription, heard), ("said", event.output_transcription, said)):
                if piece is None or not piece.text or (piece.finished and pieces[kind]):
                    continue
                pieces[kind] = pieces[kind] or not piece.finished
                into.append(piece.text)
                yield Event(type=kind, text=piece.text)
            for part in event.content.parts if event.content and event.content.parts else []:
                if part.inline_data and part.inline_data.data:
                    yield Event(type="audio", data=base64.b64encode(part.inline_data.data).decode())
            if event.turn_complete:
                return

    async def close(self) -> None:
        self.requests.close()
        if self.task is not None:
            self.task.cancel()
            with contextlib.suppress(BaseException):
                await self.task


class Calls:
    """The call in progress, if any. The agent runs as one instance, so this lives in memory.

    `open` and `send` check and fail before anything streams; `stream` then streams the agent's reply.
    """

    def __init__(self, connect: Connect = live_connect) -> None:
        self._connect = connect
        self._call: Call | None = None

    async def _expire(self) -> None:
        if self._call is not None and time.monotonic() - self._call.last > IDLE_SECONDS:
            await self._close()  # left idle: nothing was recorded, so the call is left to a person

    def _current(self, payment_id: str) -> Call:
        call = self._call
        if call is None or call.payment_id != payment_id:
            raise CallError("No call in progress for this payment.")
        return call

    async def open(self, payment_id: str) -> None:
        await self._expire()
        if self._call is not None:
            if self._call.payment_id != payment_id:
                raise CallError("Another verification call is in progress. Try again in a few minutes.")
            await self._close()
        item = store.get(payment_id)
        if item.status != "pending" or item.tier != "verify" or item.verify_with is None:
            raise CallError("This payment has no call to make.")
        call = Call(payment_id, demo.scenario_for(payment_id).payment, item.verify_with, self._connect)
        try:
            await call.start()
        except Exception as e:
            logger.warning("verification call could not connect: %s", type(e).__name__)
            await call.close()
            raise CallError("The call could not be placed. Call the number yourself.") from None
        self._call = call

    async def send(self, payment_id: str, audio: bytes | None = None, text: str | None = None) -> None:
        await self._expire()
        call = self._current(payment_id)
        if bool(audio) == bool(text):
            raise CallError("Send either audio or text.")
        if audio and len(audio) > MAX_AUDIO_BYTES:
            raise CallError("Say it in under 30 seconds.")
        if audio:
            call.speak(audio)
        else:
            call.say(text or "")
        call.turns += 1

    async def stream(self, payment_id: str) -> AsyncIterator[Event]:
        call = self._current(payment_id)
        try:
            async with asyncio.timeout(REPLY_TIMEOUT):
                async for event in call.listen():
                    yield event
        except Exception as e:  # a timeout or a dropped session: whatever was said confirms nothing
            logger.warning("verification call dropped: %s", type(e).__name__)
            yield Event(type="error", text="The call dropped. Call the number yourself.")
            yield await self._finish(call)
            return
        if call.statement is not None or call.turns >= MAX_TURNS:
            yield await self._finish(call)

    async def hang_up(self, payment_id: str) -> Event:
        return await self._finish(self._current(payment_id))

    async def _finish(self, call: Call) -> Event:
        await self._close()
        try:
            item = store.log_agent_call(call.payment_id, call.statement or Statement(), call.transcript)
        except DecisionError as e:
            return Event(type="error", text=str(e))
        outcome = item.call.outcome if item.call and item.call.by == AGENT else "incomplete"
        return Event(type="done", outcome=outcome)

    async def _close(self) -> None:
        call, self._call = self._call, None
        if call is not None:
            await call.close()


calls = Calls()
