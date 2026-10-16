import asyncio
from contextlib import asynccontextmanager

import pytest
from google.genai import types

from app.payguard import demo
from app.payguard.approvals import store
from app.payguard.call import ANSWERED, CallError, Calls, Event, brief
from app.payguard.rules import check


def said(text: str, audio: bytes = b"\x00\x01") -> list[types.LiveServerMessage]:
    return [
        types.LiveServerMessage(
            server_content=types.LiveServerContent(
                model_turn=types.Content(role="model", parts=[types.Part(inline_data=types.Blob(data=audio, mime_type="audio/pcm"))]),
                output_transcription=types.Transcription(text=text),
            )
        ),
        types.LiveServerMessage(server_content=types.LiveServerContent(turn_complete=True)),
    ]


def records(**args) -> list[list[types.LiveServerMessage]]:
    """As Live sends it: the tool call ends its turn, and the goodbye comes in the next one."""
    call = types.FunctionCall(id="1", name="record_answer", args=args)
    tool_turn = [
        types.LiveServerMessage(tool_call=types.LiveServerToolCall(function_calls=[call])),
        types.LiveServerMessage(server_content=types.LiveServerContent(turn_complete=True)),
    ]
    return [tool_turn, said("Thank you.")]


class FakeSession:
    """Plays the agent's side of the Live session ADK opens: one scripted reply each time the payee's turn ends
    (typed text, or the end of speech) or a tool response comes back. With no reply left, it stays silent."""

    def __init__(self, replies: list[list[types.LiveServerMessage]]) -> None:
        self.replies = replies
        self.sent: list = []
        self.tool_responses: list = []
        self.turns: asyncio.Queue | None = None
        self.session_id = "fake"

    async def close(self):
        pass

    def _queue(self) -> asyncio.Queue:
        if self.turns is None:
            self.turns = asyncio.Queue()
        return self.turns

    async def send_client_content(self, turns, turn_complete):
        self.sent.append(turns)

    async def send_realtime_input(self, **kwargs):
        self.sent.append(kwargs)
        if "text" in kwargs or "activity_end" in kwargs:
            self._queue().put_nowait(None)

    async def send_tool_response(self, function_responses):
        self.tool_responses += function_responses
        self._queue().put_nowait(None)

    async def receive(self):
        await self._queue().get()
        if not self.replies:
            await asyncio.Event().wait()
        for msg in self.replies.pop(0):
            yield msg


def connect_to(session: FakeSession, seen: list | None = None):
    @asynccontextmanager
    async def connect(config):
        if seen is not None:
            seen.append(config)
        yield session

    return connect


@pytest.fixture(autouse=True)
def fresh_store():
    store.reset()
    yield
    store.reset()


def checked(payment_id: str) -> None:
    s = demo.scenario_for(payment_id)
    store.checked(payment_id, check(demo.ledger(), s.payment, s.instruction))


async def start(calls: Calls, payment_id: str) -> list[Event]:
    await calls.open(payment_id)
    return [e async for e in calls.stream(payment_id)]


async def say(calls: Calls, payment_id: str, **kwargs) -> list[Event]:
    await calls.send(payment_id, **kwargs)
    return [e async for e in calls.stream(payment_id)]


def done(events: list[Event]) -> Event | None:
    return next((e for e in events if e.type == "done"), None)


def test_brief_never_carries_the_account_or_the_amount():
    for pid in ("P-1002", "P-1003"):
        checked(pid)
        payment = demo.scenario_for(pid).payment
        text = brief(payment, store.get(pid).verify_with, store.get(pid).ask)
        assert payment.account.number not in text
        assert str(payment.amount) not in text and f"{payment.amount:,}" not in text
        assert "automated" in text


def test_brief_names_people_in_english():
    checked("P-1003")
    text = brief(demo.scenario_for("P-1003").payment, store.get("P-1003").verify_with, store.get("P-1003").ask)
    assert "Ichiro Sato" in text and "佐藤" not in text


def test_agent_voice_streams_and_code_confirms_the_answer():
    checked("P-1002")
    session = FakeSession([said("This is an automated call."), *records(bank_name="Yuunagi Bank", account_number="2345")])
    calls = Calls(connect_to(session))

    async def go():
        first = await start(calls, "P-1002")
        assert [e.type for e in first] == ["audio", "said"] and done(first) is None
        last = await say(calls, "P-1002", text="Yuunagi Bank, ending 2345.")
        assert done(last).outcome == "confirmed" and last[-1].type == "done"
        assert any(e.type == "said" and e.text == "Thank you." for e in last)

    asyncio.run(go())
    assert session.tool_responses[0].name == "record_answer"
    item = store.get("P-1002")
    assert item.call.confirmed and [t.speaker for t in item.call.transcript] == ["agent", "payee", "agent"]


def test_payee_states_the_registered_account_and_the_payment_is_held():
    checked("P-1002")
    calls = Calls(connect_to(FakeSession([said("Hello."), *records(bank_name="Isana Bank", account_number="1234567")])))

    async def go():
        await start(calls, "P-1002")
        return done(await say(calls, "P-1002", text="Isana Bank, 1234567."))

    assert asyncio.run(go()).outcome == "mismatch"
    assert store.get("P-1002").status == "held"


def test_the_call_is_answered_then_audio_is_sent_between_activity_marks():
    checked("P-1002")
    session = FakeSession([said("Hello."), said("Could you say the amount?")])
    calls = Calls(connect_to(session))

    async def go():
        await start(calls, "P-1002")
        return await say(calls, "P-1002", audio=bytes(3200))

    assert done(asyncio.run(go())) is None
    assert session.sent[0] == {"text": ANSWERED}
    assert [next(iter(k)) for k in session.sent[1:]] == ["activity_start", "audio", "activity_end"]


def test_answer_counts_even_if_the_goodbye_never_comes(monkeypatch):
    from app.payguard import call as call_module

    monkeypatch.setattr(call_module, "FOLLOW_UP_TIMEOUT", 0.05)
    checked("P-1002")
    tool_turn = records(bank_name="Yuunagi Bank", account_number="8812345")[0]
    calls = Calls(connect_to(FakeSession([said("Hello."), tool_turn])))

    async def go():
        await start(calls, "P-1002")
        return done(await say(calls, "P-1002", text="Yuunagi Bank, 8812345."))

    assert asyncio.run(go()).outcome == "confirmed"


def test_hang_up_without_an_answer_leaves_the_call_to_a_person():
    checked("P-1002")
    calls = Calls(connect_to(FakeSession([said("Hello.")])))

    async def go():
        await start(calls, "P-1002")
        return await calls.hang_up("P-1002")

    event = asyncio.run(go())
    assert event.type == "done" and event.outcome == "incomplete"
    item = store.get("P-1002")
    assert item.call is None and item.status == "pending"


def test_a_session_that_drops_mid_call_confirms_nothing():
    checked("P-1002")

    class Dropping(FakeSession):
        async def receive(self):
            await self._queue().get()
            if not self.replies:
                raise ConnectionError("gone")
            for msg in self.replies.pop(0):
                yield msg

    calls = Calls(connect_to(Dropping([said("Hello.")])))

    async def go():
        await start(calls, "P-1002")
        return await say(calls, "P-1002", text="Isana Bank.")

    events = asyncio.run(go())
    assert [e.type for e in events] == ["error", "done"] and done(events).outcome == "incomplete"
    assert store.get("P-1002").call is None


def test_a_call_that_cannot_connect_says_so_before_streaming():
    checked("P-1002")

    @asynccontextmanager
    async def refuse(config):
        raise ConnectionError("quota")
        yield  # pragma: no cover

    calls = Calls(refuse)
    with pytest.raises(CallError):
        asyncio.run(calls.open("P-1002"))
    with pytest.raises(CallError):
        asyncio.run(calls.hang_up("P-1002"))  # nothing is in progress


def test_no_call_for_a_payment_that_does_not_need_one():
    checked("P-1001")
    with pytest.raises(CallError):
        asyncio.run(Calls(connect_to(FakeSession([]))).open("P-1001"))


def test_one_call_at_a_time():
    checked("P-1002")
    checked("P-1003")
    calls = Calls(connect_to(FakeSession([said("Hello.")])))

    async def go():
        await start(calls, "P-1002")
        with pytest.raises(CallError):
            await calls.open("P-1003")
        await calls.hang_up("P-1002")

    asyncio.run(go())


def test_agent_is_given_the_tool_push_to_talk_and_one_language():
    checked("P-1002")
    seen: list = []
    calls = Calls(connect_to(FakeSession([said("Hello.")]), seen))

    async def go():
        await start(calls, "P-1002")
        await calls.hang_up("P-1002")

    asyncio.run(go())
    config = seen[0]
    assert [d.name for t in config.tools for d in t.function_declarations] == ["record_answer"]
    assert config.realtime_input_config.automatic_activity_detection.disabled
    assert config.speech_config.language_code == "en-US"
    assert "never suggest one" in config.system_instruction.parts[0].text


def test_endpoints_stream_one_event_per_line(monkeypatch):
    import json

    from fastapi.testclient import TestClient

    from app.payguard import api
    from main import app

    checked("P-1002")
    session = FakeSession([said("Hello."), *records(bank_name="Yuunagi Bank", account_number="2345")])
    monkeypatch.setattr(api, "calls", Calls(connect_to(session)))
    with TestClient(app) as client:  # one event loop for the whole call, as in the server
        res = client.post("/demo/payments/P-1002/agent-call")
        assert res.headers["content-type"].startswith("application/x-ndjson")
        assert [json.loads(line)["type"] for line in res.text.splitlines()] == ["audio", "said"]
        assert client.post("/demo/payments/P-1002/agent-call/say", json={"audio": "not base64!"}).status_code == 422
        res = client.post("/demo/payments/P-1002/agent-call/say", json={"text": "Yuunagi Bank, ending 2345."})
        assert json.loads(res.text.splitlines()[-1]) == {"type": "done", "outcome": "confirmed"}
        assert client.post("/demo/payments/P-1002/agent-call/hang-up").status_code == 409  # already over
        assert client.post("/demo/payments/P-1001/agent-call").status_code == 409  # unchecked: no call to make
