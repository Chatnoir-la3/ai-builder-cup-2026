"""Runs the whole workflow against Gemini. Run with RUN_LIVE_GEMINI=1 and application default credentials."""

import asyncio
import os

import pytest

from app.payguard import demo
from app.payguard.explain import top_findings
from app.payguard.pipeline import run_check
from app.payguard.rules import check

pytestmark = pytest.mark.skipif(os.getenv("RUN_LIVE_GEMINI") != "1", reason="set RUN_LIVE_GEMINI=1 to call Gemini")


@pytest.mark.parametrize("scenario", demo.scenarios(), ids=[s.id for s in demo.scenarios()])
def test_pipeline(scenario):
    response = asyncio.run(run_check(scenario.payment.id))
    expected = check(demo.ledger(), scenario.payment, scenario.instruction)

    assert [f.code for f in response.findings] == [f.code for f in expected.findings]
    if not expected.findings:
        assert response.notice is None
        return
    assert response.notice is not None
    assert response.notice.source == "model", response.notice  # Gemini's notice passed the checks
    assert [r.code for r in response.notice.reasons] == [f.code for f in top_findings(expected.findings)]
    assert expected.verify_with is not None and expected.verify_with.phone in response.notice.action
