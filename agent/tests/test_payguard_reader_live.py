"""Calls Gemini for real. Run with RUN_LIVE_GEMINI=1 and application default credentials."""

import asyncio
import json
import os

import pytest

from app.payguard import DATA_DIR, Instruction, Payment, check, load_demo_ledger
from app.payguard.reader import Original, Reading, build_content, ground, reader_agent

pytestmark = pytest.mark.skipif(os.getenv("RUN_LIVE_GEMINI") != "1", reason="set RUN_LIVE_GEMINI=1 to call Gemini")

SCENARIOS = json.loads((DATA_DIR / "scenarios.json").read_text(encoding="utf-8"))


async def _read(originals: list[Original]) -> Reading:
    from google.adk.runners import InMemoryRunner

    runner = InMemoryRunner(agent=reader_agent, app_name="live")
    session = await runner.session_service.create_session(app_name="live", user_id="t")
    async for _ in runner.run_async(user_id="t", session_id=session.id, new_message=build_content(originals)):
        pass
    session = await runner.session_service.get_session(app_name="live", user_id="t", session_id=session.id)
    return Reading.model_validate(session.state["reading"])


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_reader_matches_scenario(scenario):
    originals = [Original.from_path(DATA_DIR / "originals" / name) for name in scenario["originals"]]
    grounded = ground(asyncio.run(_read(originals)), originals)
    expected = Instruction.model_validate(scenario["instruction"])

    got = grounded.instruction
    assert grounded.unverified == []
    assert got.channel == expected.channel
    assert got.account_number == expected.account_number
    assert got.amount == expected.amount
    assert got.sender_address == expected.sender_address

    # What matters downstream: the rules reach the same findings as with the hand-written instruction.
    ledger, payment = load_demo_ledger(), Payment.model_validate(scenario["payment"])
    assert {f.code for f in check(ledger, payment, got).findings} == {
        f.code for f in check(ledger, payment, expected).findings
    }
