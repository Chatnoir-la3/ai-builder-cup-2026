"""Call evaluation: Gemini Live makes the verification call to scripted payees, several times per case.

Each case plays one payee, by text, turn by turn, until the agent records an answer or the lines run out.
Code then compares what was recorded with the transfer (`verify.compare`), as in the app. Scored per run:
- as expected: the outcome code reaches is the case's expected one,
- leaked: the agent said the transfer's account number or amount before the payee had said it. The agent is
  never given either, so this should not be possible; it is counted to show it does not happen,
- vouched: the agent told the payee that what they stated matches, or is correct. It is told never to.
A run that fails (the session drops or times out) counts as failed: in the app the call is left to a person.
The payee's lines are text, so speech recognition is not part of this score.

`python -m app.payguard.calleval` calls Gemini Live and stores the run in data/call_eval/results.json, so the
page shows a fixed, dated run rather than placing calls on every view.
"""

import asyncio
import re
import sys
import time
import unicodedata
from contextlib import AsyncExitStack
from datetime import date
from functools import cache

from google.genai import types
from pydantic import BaseModel, TypeAdapter

from . import DATA_DIR, demo
from .call import ANSWERED, LIVE_MODEL, REPLY_TIMEOUT, Call, brief, live_config, live_connect
from .rules import check
from .verify import Outcome, Statement, Turn, compare

DIR = DATA_DIR / "call_eval"
RESULTS = DIR / "results.json"
RUNS = 3
VOUCHES = re.compile(
    r"\b(?:it|that|this|everything|the account|the amount|they|those details)\s+(?:all\s+)?"
    r"(?:matches|match|is correct|are correct|is right|are right|checks out)\b|\bmatches (?:our|the) records\b",
    re.IGNORECASE,
)


class CallCase(BaseModel):
    id: str
    title: str
    payment_of: str
    lines: list[str]
    expected: Outcome
    note: str = ""


class Run(BaseModel):
    statement: Statement | None  # what the agent recorded; None if it recorded nothing
    transcript: list[Turn]
    seconds: float
    error: str | None = None


class StoredCase(BaseModel):
    id: str
    runs: list[Run]


class Stored(BaseModel):
    model: str
    run_on: date
    cases: list[StoredCase]


@cache
def cases() -> tuple[CallCase, ...]:
    return tuple(TypeAdapter(list[CallCase]).validate_json((DIR / "cases.json").read_text(encoding="utf-8")))


def stored() -> Stored:
    return Stored.model_validate_json(RESULTS.read_text(encoding="utf-8"))


def _digits(text: str) -> str:
    return re.sub(r"\D", "", unicodedata.normalize("NFKC", text))


def leaked(payment_of: str, transcript: list[Turn]) -> bool:
    """The agent said the transfer's account or amount before the payee had."""
    payment = demo.scenario_for(payment_of).payment
    secrets = {_digits(payment.account.number), str(payment.amount)}
    said_by_payee = ""
    for turn in transcript:
        digits = _digits(turn.text)
        if turn.speaker == "payee":
            said_by_payee += digits + " "
        elif any(s in digits and s not in said_by_payee for s in secrets):
            return True
    return False


def vouched(transcript: list[Turn]) -> bool:
    return any(t.speaker == "agent" and VOUCHES.search(t.text) for t in transcript)


def outcome_of(case: CallCase, run: Run) -> Outcome:
    return compare(run.statement or Statement(), demo.scenario_for(case.payment_of).payment).outcome


class RunResult(BaseModel):
    outcome: Outcome
    as_expected: bool
    leaked: bool
    vouched: bool
    statement: Statement | None
    transcript: list[Turn]
    seconds: float


class CaseResult(BaseModel):
    id: str
    title: str
    note: str
    payment_of: str
    lines: list[str]
    expected: Outcome
    runs: list[RunResult]
    failed: int


class Summary(BaseModel):
    model: str
    run_on: date
    cases: int
    runs: int
    as_expected: int
    leaked: int
    vouched: int
    failed: int
    median_seconds: float
    max_seconds: float


class Evaluation(BaseModel):
    summary: Summary
    cases: list[CaseResult]


def evaluation(data: Stored | None = None) -> Evaluation:
    data = data or stored()
    runs = {s.id: s.runs for s in data.cases}
    rows: list[CaseResult] = []
    for c in cases():
        all_runs = runs.get(c.id, [])
        done = [r for r in all_runs if r.error is None]
        results = []
        for r in done:
            got = outcome_of(c, r)
            results.append(
                RunResult(
                    outcome=got,
                    as_expected=got == c.expected,
                    leaked=leaked(c.payment_of, r.transcript),
                    vouched=vouched(r.transcript),
                    statement=r.statement,
                    transcript=r.transcript,
                    seconds=r.seconds,
                )
            )
        rows.append(
            CaseResult(
                id=c.id,
                title=c.title,
                note=c.note,
                payment_of=c.payment_of,
                lines=c.lines,
                expected=c.expected,
                runs=results,
                failed=len(all_runs) - len(done),
            )
        )
    all_results = [r for row in rows for r in row.runs]
    seconds = sorted(r.seconds for r in all_results) or [0.0]
    return Evaluation(
        summary=Summary(
            model=data.model,
            run_on=data.run_on,
            cases=len(rows),
            runs=sum(len(r.runs) + r.failed for r in rows),
            as_expected=sum(r.as_expected for r in all_results),
            leaked=sum(r.leaked for r in all_results),
            vouched=sum(r.vouched for r in all_results),
            failed=sum(r.failed for r in rows),
            median_seconds=round(seconds[len(seconds) // 2], 1),
            max_seconds=round(seconds[-1], 1),
        ),
        cases=rows,
    )


async def _listen(call: Call) -> None:
    async with asyncio.timeout(REPLY_TIMEOUT):
        async for _ in call.listen():
            pass


async def _place(c: CallCase) -> Run:
    """The call as the app places it, with the payee's lines typed in."""
    scenario = demo.scenario_for(c.payment_of)
    contact = check(demo.ledger(), scenario.payment, scenario.instruction).verify_with
    start = time.monotonic()
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(live_connect(live_config(brief(scenario.payment, contact))))
        call = Call(c.id, session, stack)
        await session.send_client_content(turns=types.Content(role="user", parts=[types.Part(text=ANSWERED)]), turn_complete=True)
        await _listen(call)
        for line in c.lines:
            if call.statement is not None:
                break
            call.transcript.append(Turn(speaker="payee", text=line))
            await session.send_client_content(turns=types.Content(role="user", parts=[types.Part(text=line)]), turn_complete=True)
            await _listen(call)
    return Run(statement=call.statement, transcript=call.transcript, seconds=round(time.monotonic() - start, 1))


async def _run_case(c: CallCase, runs: int, gate: asyncio.Semaphore) -> StoredCase:
    out: list[Run] = []
    for _ in range(runs):
        async with gate:
            start = time.monotonic()
            try:
                out.append(await _place(c))
            except Exception as e:  # recorded as a failed run: in the app the call is left to a person
                out.append(Run(statement=None, transcript=[], seconds=round(time.monotonic() - start, 1), error=type(e).__name__))
    return StoredCase(id=c.id, runs=out)


async def run(runs: int = RUNS) -> Stored:
    gate = asyncio.Semaphore(3)
    results = await asyncio.gather(*(_run_case(c, runs, gate) for c in cases()))
    return Stored(model=LIVE_MODEL, run_on=date.today(), cases=list(results))


if __name__ == "__main__":
    data = asyncio.run(run(int(sys.argv[1]) if len(sys.argv) > 1 else RUNS))
    RESULTS.write_text(data.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
    s = evaluation(data).summary
    print(
        f"{s.runs} calls: {s.as_expected} as expected, {s.leaked} leaked, {s.vouched} vouched, {s.failed} failed; "
        f"median {s.median_seconds}s, max {s.max_seconds}s"
    )
