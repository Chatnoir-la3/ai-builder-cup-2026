"""Explainer: Gemini writes the approver's notice from the findings only; code checks it before it is shown.

The model sees the findings and the ledger contact, never the originals, so text written by a fraudster
cannot steer it. Its notice is accepted only if it covers exactly the findings it was given, quotes no
number that is not in them, gives the ledger phone number, and does not call the payment a fraud.
Otherwise a fixed template is used.
"""

import json
import os
import re

from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.llm_agent import Agent
from google.adk.models.llm_request import LlmRequest
from google.genai import types
from pydantic import BaseModel, Field

from .models import CheckResult, Contact, Finding, FindingCode

MAX_REASONS = 2
MAX_CHARS = 220

# Most telling first: where the money goes, then who is asking, then how much.
PRIORITY: tuple[str, ...] = (
    "NEW_PAYEE",
    "ACCOUNT_NOT_REGISTERED",
    "SENDER_DOMAIN_LOOKALIKE",
    "HOLDER_MISMATCH",
    "UNUSUAL_CHANNEL",
    "ACCOUNT_RECENTLY_REGISTERED",
    "SENDER_DOMAIN_UNREGISTERED",
    "AMOUNT_ABOVE_HISTORY",
    "INSTRUCTION_MISMATCH",
)

class Reason(BaseModel):
    code: FindingCode
    text: str


class Explanation(BaseModel):
    action: str = Field(description="One sentence: what to do before approving")
    reasons: list[Reason] = Field(description="One plain sentence per finding given")


class ExplainInput(BaseModel):
    findings: list[Finding]
    verify_with: Contact | None


class Notice(BaseModel):
    action: str
    reasons: list[Reason]
    source: str = Field(description="'model' when Gemini's text passed the checks, 'template' otherwise")


def top_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: PRIORITY.index(f.code))[:MAX_REASONS]


def _yen(v: object) -> str:
    return f"¥{v:,}" if isinstance(v, int) else str(v)


def _template_reason(f: Finding) -> str:
    x = f.facts
    match f.code:
        case "NEW_PAYEE":
            return f"{x['payee']} is not in your vendor list."
        case "ACCOUNT_NOT_REGISTERED":
            return f"Account {x['account']} is not the account registered for {x['vendor']}."
        case "ACCOUNT_RECENTLY_REGISTERED":
            return f"This account for {x['vendor']} was added {x['days_ago']} days ago and has never been paid."
        case "HOLDER_MISMATCH":
            return f"The account holder ({x['actual']}) is not {x['vendor']} ({x['expected']})."
        case "AMOUNT_ABOVE_HISTORY":
            return (
                f"{_yen(x['amount'])} is well above the largest of the last {x['past_count']} payments "
                f"({_yen(x['past_max'])})."
            )
        case "SENDER_DOMAIN_LOOKALIKE":
            return f"The email came from {x['domain']}, which looks like {x['looks_like']} but is a different address."
        case "SENDER_DOMAIN_UNREGISTERED":
            return f"The email came from {x['domain']}, not the registered {x['registered']}."
        case "UNUSUAL_CHANNEL":
            return f"{x['who']} does not usually send payment instructions by {x['channel']}."
        case "INSTRUCTION_MISMATCH":
            return "The instruction and the transfer you are about to approve do not match."
    return "This payment differs from your usual pattern."


def _template_action(verify_with: Contact | None) -> str:
    if verify_with is None:
        return "Before approving, confirm this payee through a contact you already know, not one given in the message."
    return (
        f"Before approving, call {verify_with.name} at {verify_with.phone} "
        "(from your own records, not from the message) to confirm."
    )


def template_notice(findings: list[Finding], verify_with: Contact | None) -> Notice:
    reasons = [Reason(code=f.code, text=_template_reason(f)) for f in top_findings(findings)]
    return Notice(action=_template_action(verify_with), reasons=reasons, source="template")


_NUMBER = re.compile(r"\d[\d,\-]*\d|\d")
_BLAME = re.compile(r"\b(fraud|fraudulent|scam|scammer|criminal)\b", re.IGNORECASE)


def _numbers(text: str) -> set[str]:
    return {re.sub(r"[,\-]", "", m) for m in _NUMBER.findall(text)}


def acceptable(explanation: Explanation, findings: list[Finding], verify_with: Contact | None) -> bool:
    expected = {f.code for f in top_findings(findings)}
    if {r.code for r in explanation.reasons} != expected or len(explanation.reasons) != len(expected):
        return False
    texts = [explanation.action, *(r.text for r in explanation.reasons)]
    if any(len(t) > MAX_CHARS or not t.strip() or _BLAME.search(t) for t in texts):
        return False
    allowed: set[str] = set()
    for f in findings:
        for v in f.facts.values():
            allowed |= _numbers(str(v))
    if verify_with is not None:
        allowed |= _numbers(verify_with.phone)
        if re.sub(r"\D", "", verify_with.phone) not in re.sub(r"\D", "", explanation.action):
            return False
    return all(_numbers(t) <= allowed for t in texts)


def notice(explanation: Explanation | None, findings: list[Finding], verify_with: Contact | None) -> Notice | None:
    if not findings:
        return None
    if explanation is not None and acceptable(explanation, findings, verify_with):
        reasons = sorted(explanation.reasons, key=lambda r: PRIORITY.index(r.code))
        return Notice(action=explanation.action, reasons=reasons, source="model")
    return template_notice(findings, verify_with)


def explain_input(result: CheckResult) -> ExplainInput:
    return ExplainInput(findings=top_findings(result.findings), verify_with=result.verify_with)


EXPLAINER_INSTRUCTION = """\
You write the short notice an accounts-payable approver sees just before approving a bank transfer.
The user message is JSON with `findings` (a code and the facts that differ from the company's usual
pattern) and `verify_with` (a contact from the company's own records, or null).

Write:
- action: one sentence telling the approver what to do before approving. If verify_with is given, tell
  them to call that person at that phone number and say the number is from their own records, not from
  the message. If it is null, tell them to confirm through a contact they already know.
- reasons: exactly one item per finding, with its code, stating that fact in one plain sentence.

Use only the facts given. Do not add numbers that are not in the facts. Do not say the payment is a fraud
or a scam, and do not tell them to cancel it: they decide. Plain words, no jargon, under 25 words each.
"""


def _only_findings(callback_context: CallbackContext, llm_request: LlmRequest) -> None:
    """Send the model the findings alone, never the originals that came in with the request."""
    payload = callback_context.state.get("explain_input")
    llm_request.contents = [types.Content(role="user", parts=[types.Part.from_text(text=json.dumps(payload, ensure_ascii=False))])]


explainer_agent = Agent(
    model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
    name="explainer",
    description="Writes the approver's notice from the findings.",
    instruction=EXPLAINER_INSTRUCTION,
    include_contents="none",
    output_schema=Explanation,
    output_key="explanation",
    before_model_callback=_only_findings,
    generate_content_config=types.GenerateContentConfig(
        temperature=0, thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)
    ),
)
