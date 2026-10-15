import asyncio
from contextlib import asynccontextmanager

import pytest
from google.genai import types

from app.payguard import demo
from app.payguard.approvals import store
from app.payguard.call import CallError, Calls, Event, brief
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
    """Plays the agent's side: one scripted reply per turn the payee takes."""

    def __init__(self, replies: list[list[types.LiveServerMessage]]) -> None:
        self.replies = replies
        self.sent: list = []
        self.tool_responses: list = []

    async def send_client_content(self, turns, turn_complete):
        self.sent.append(turns.parts[0].text)

    async def send_realtime_input(self, **kwargs):
        self.sent.append(kwargs)

    async def send_tool_response(self, function_responses):
        self.tool_responses += function_responses

    async def receive(self):
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


def start(calls: Calls, payment_id: str) -> list[Event]:
    async def go():
        await calls.open(payment_id)
        return [e async for e in calls.stream(payment_id)]

    return asyncio.run(go())


def say(calls: Calls, payment_id: str, **kwargs) -> list[Event]:
    async def go():
        await calls.send(payment_id, **kwargs)
        return [e async for e in calls.stream(payment_id)]

    return asyncio.run(go())


def done(events: list[Event]) -> Event | None:
    return next((e for e in events if e.type == "done"), None)


def test_brief_never_carries_the_account_or_the_amount():
    for pid in ("P-1002", "P-1003"):
        checked(pid)
        payment = demo.scenario_for(pid).payment
        text = brief(payment, store.get(pid).verify_with)
        assert payment.account.number not in text
        assert str(payment.amount) not in text and f"{payment.amount:,}" not in text
        assert "automated" in text


def test_brief_names_people_in_english():
    checked("P-1003")
    text = brief(demo.scenario_for("P-1003").payment, store.get("P-1003").verify_with)
    assert "Ichiro Sato" in text and "佐藤" not in text


def test_agent_voice_streams_and_code_confirms_the_answer():
    checked("P-1002")
    session = FakeSession([said("This is an automated call."), *records(account_number="8812345", amount=486000)])
    calls = Calls(connect_to(session))
    first = start(calls, "P-1002")
    assert [e.type for e in first] == ["said", "audio"] and done(first) is None
    last = say(calls, "P-1002", text="Yuunagi Bank, 8812345, 486,000 yen.")
    assert done(last).outcome == "confirmed" and last[-1].type == "done"
    assert any(e.type == "said" and e.text == "Thank you." for e in last)
    assert session.tool_responses[0].name == "record_answer"
    item = store.get("P-1002")
    assert item.call.confirmed and [t.speaker for t in item.call.transcript] == ["agent", "payee", "agent"]


def test_payee_states_the_registered_account_and_the_payment_is_held():
    checked("P-1002")
    calls = Calls(connect_to(FakeSession([said("Hello."), *records(account_number="1234567", amount=486000)])))
    start(calls, "P-1002")
    assert done(say(calls, "P-1002", text="Isana Bank, 1234567.")).outcome == "mismatch"
    assert store.get("P-1002").status == "held"


def test_audio_is_sent_between_activity_marks():
    checked("P-1002")
    session = FakeSession([said("Hello."), said("Could you say the amount?")])
    calls = Calls(connect_to(session))
    start(calls, "P-1002")
    events = say(calls, "P-1002", audio=bytes(3200))
    assert done(events) is None
    kinds = [next(iter(k)) for k in session.sent[1:]]
    assert kinds == ["activity_start", "audio", "activity_end"]


def test_answer_counts_even_if_the_goodbye_never_comes(monkeypatch):
    from app.payguard import call as call_module

    monkeypatch.setattr(call_module, "FOLLOW_UP_TIMEOUT", 0.05)
    checked("P-1002")

    class Silent(FakeSession):
        async def receive(self):
            if not self.replies:
                await asyncio.sleep(1)
            for msg in self.replies.pop(0) if self.replies else []:
                yield msg

    tool_turn = records(account_number="8812345", amount=486000)[0]
    calls = Calls(connect_to(Silent([said("Hello."), tool_turn])))
    start(calls, "P-1002")
    assert done(say(calls, "P-1002", text="8812345, 486,000 yen.")).outcome == "confirmed"


def test_hang_up_without_an_answer_leaves_the_call_to_a_person():
    checked("P-1002")
    calls = Calls(connect_to(FakeSession([said("Hello.")])))
    start(calls, "P-1002")
    event = asyncio.run(calls.hang_up("P-1002"))
    assert event.type == "done" and event.outcome == "incomplete"
    item = store.get("P-1002")
    assert item.call is None and item.status == "pending"


def test_a_dropped_session_confirms_nothing():
    checked("P-1002")

    class Dropping(FakeSession):
        async def receive(self):
            raise ConnectionError("gone")
            yield  # pragma: no cover

    events = start(Calls(connect_to(Dropping([]))), "P-1002")
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
    start(calls, "P-1002")
    with pytest.raises(CallError):
        asyncio.run(calls.open("P-1003"))


def test_agent_is_given_the_tool_push_to_talk_and_one_language():
    checked("P-1002")
    seen: list = []
    start(Calls(connect_to(FakeSession([said("Hello.")]), seen)), "P-1002")
    config = seen[0]
    assert config.tools[0].function_declarations[0].name == "record_answer"
    assert config.realtime_input_config.automatic_activity_detection.disabled
    assert config.speech_config.language_code == "en-US"


def test_endpoints_stream_one_event_per_line(monkeypatch):
    import json

    from fastapi.testclient import TestClient

    from app.payguard import api
    from main import app

    checked("P-1002")
    session = FakeSession([said("Hello."), *records(account_number="8812345", amount=486000)])
    monkeypatch.setattr(api, "calls", Calls(connect_to(session)))
    client = TestClient(app)
    res = client.post("/demo/payments/P-1002/agent-call")
    assert res.headers["content-type"].startswith("application/x-ndjson")
    assert [json.loads(line)["type"] for line in res.text.splitlines()] == ["said", "audio"]
    assert client.post("/demo/payments/P-1002/agent-call/say", json={"audio": "not base64!"}).status_code == 422
    res = client.post("/demo/payments/P-1002/agent-call/say", json={"text": "8812345, 486,000 yen."})
    assert json.loads(res.text.splitlines()[-1]) == {"type": "done", "outcome": "confirmed"}
    assert client.post("/demo/payments/P-1002/agent-call/hang-up").status_code == 409  # already over
    assert client.post("/demo/payments/P-1001/agent-call").status_code == 409  # unchecked: no call to make
