"""Read → check → explain, as an ADK workflow.

The reader and explainer are Gemini; the check between them is plain code and decides whether the
explainer runs at all. A routine payment never reaches the explainer, so it costs one model call and
shows nothing.
"""

import json

from google.adk import Event, Workflow
from google.adk.apps import App
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel

from . import demo
from .explain import Explanation, Notice, explain_input, explainer_agent, notice
from .models import CheckResult, Contact, Finding, Payment
from .reader import GroundedReading, Reading, build_content, ground, reader_agent
from .rules import check

APP_NAME = "payguard"
USER_ID = "demo"


def _as_reading(value: object) -> Reading:
    if isinstance(value, Reading):
        return value
    if isinstance(value, types.Content):
        value = json.loads("".join(p.text or "" for p in value.parts or []))
    if isinstance(value, str):
        value = json.loads(value)
    if isinstance(value, BaseModel):
        value = value.model_dump()
    return Reading.model_validate(value)


def check_node(node_input: object, payment_id: str):
    scenario = demo.scenario_for(payment_id)
    grounded = ground(_as_reading(node_input), demo.originals(scenario))
    result = check(demo.ledger(), scenario.payment, grounded.instruction)
    return Event(
        state={
            "grounded": grounded.model_dump(mode="json"),
            "check": result.model_dump(mode="json"),
            "explain_input": explain_input(result).model_dump(mode="json"),
        },
        route="explain" if result.show else "quiet",
    )


def quiet_node():
    """Nothing differs from the usual pattern: end without a model call."""
    return None


pipeline = Workflow(
    name="payguard",
    edges=[
        ("START", reader_agent, check_node),
        (check_node, {"explain": explainer_agent, "quiet": quiet_node}),
    ],
)


class CheckResponse(BaseModel):
    payment: Payment
    reading: GroundedReading
    findings: list[Finding]
    verify_with: Contact | None
    notice: Notice | None


_runner: Runner | None = None


def runner() -> Runner:
    global _runner
    if _runner is None:
        from app.agent import _plugins

        _runner = Runner(app=App(name=APP_NAME, root_agent=pipeline, plugins=_plugins()), session_service=InMemorySessionService())
    return _runner


def respond(scenario: demo.Scenario, state: dict) -> CheckResponse:
    result = CheckResult.model_validate(state["check"])
    raw = state.get("explanation")
    explanation = Explanation.model_validate(raw) if raw else None
    return CheckResponse(
        payment=scenario.payment,
        reading=GroundedReading.model_validate(state["grounded"]),
        findings=result.findings,
        verify_with=result.verify_with,
        notice=notice(explanation, result.findings, result.verify_with),
    )


async def run_check(payment_id: str) -> CheckResponse:
    scenario = demo.scenario_for(payment_id)
    r = runner()
    session = await r.session_service.create_session(app_name=APP_NAME, user_id=USER_ID, state={"payment_id": payment_id})
    try:
        message = build_content(demo.originals(scenario))
        async for _ in r.run_async(user_id=USER_ID, session_id=session.id, new_message=message):
            pass
        done = await r.session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session.id)
        return respond(scenario, dict(done.state))
    finally:
        # The originals passed through this session; do not keep them.
        await r.session_service.delete_session(app_name=APP_NAME, user_id=USER_ID, session_id=session.id)
