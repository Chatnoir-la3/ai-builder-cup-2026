"""Reader evaluation: Gemini reads each case's originals several times; code scores what reaches the rules.

Only the fields the rules use are scored. After the code check (`reader.ground`), a field is
- correct: the value equals the expected one (empty when nothing is shown counts too),
- cleared: Gemini returned a value its quote or the original did not support, so the code check removed
  it; the rules see nothing and the approver is told the field was not confirmed,
- missed: Gemini returned nothing although the original shows it,
- wrong: a value different from the expected one reached the rules. This is the one that matters.
Each run also counts as same-findings when the rules reach the findings they reach on the expected reading.
A cleared value adds a "not confirmed in the original" finding of its own, which asks for a call; that one
is not counted against the run, but a finding the cleared value made the rules miss is.
A run that fails (the model call times out after its retry) is counted as failed: in the app the check
then says it could not run, and nothing is approved on it. Every run records how long the reading took.

`python -m app.payguard.readereval` calls Gemini and stores the run in data/reader_eval/results.json, so
the page shows a fixed, dated run rather than calling the model on every view.
"""

import asyncio
import os
import re
import sys
import time
import unicodedata
from datetime import date
from functools import cache
from typing import Literal

from pydantic import BaseModel, TypeAdapter

from . import DATA_DIR, demo
from .models import Instruction
from .reader import Original, Reading, build_content, ground, reader_agent
from .rules import check

DIR = DATA_DIR / "reader_eval"
RESULTS = DIR / "results.json"
FIELDS = ("channel", "sender_name", "sender_address", "account_number", "amount")
RUNS = 3

Outcome = Literal["correct", "cleared", "missed", "wrong"]


class ReaderCase(BaseModel):
    id: str
    title: str
    payment_of: str
    originals: list[str]
    expected: Instruction
    note: str = ""


class Run(BaseModel):
    read: Instruction | None  # what Gemini returned
    grounded: Instruction | None  # what reached the rules
    unverified: list[str] = []
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
def cases() -> tuple[ReaderCase, ...]:
    raw = (DIR / "cases.json").read_text(encoding="utf-8")
    return tuple(TypeAdapter(list[ReaderCase]).validate_json(raw))


def stored() -> Stored:
    return Stored.model_validate_json(RESULTS.read_text(encoding="utf-8"))


def _norm(field: str, value: object) -> str | None:
    if value is None:
        return None
    s = unicodedata.normalize("NFKC", str(value))
    return re.sub(r"\D", "", s) if field in ("account_number", "amount") else re.sub(r"\s", "", s)


def outcome(field: str, expected: Instruction, run: Run) -> Outcome:
    want, got = _norm(field, getattr(expected, field)), _norm(field, getattr(run.grounded, field))
    if got == want:
        return "correct"
    if got is not None:
        return "wrong"
    return "cleared" if field in run.unverified else "missed"


def same_findings(case: ReaderCase, run: Run) -> bool:
    ledger, payment = demo.ledger(), demo.scenario_for(case.payment_of).payment

    def codes(ins: Instruction, unverified: list[str]) -> set[str]:
        return {f.code for f in check(ledger, payment, ins, unverified=unverified).findings} - {"NOT_IN_ORIGINAL"}

    return codes(run.grounded, run.unverified) == codes(case.expected, [])


class FieldResult(BaseModel):
    field: str
    expected: str | int | None
    outcomes: list[Outcome]  # one per completed run
    read: list[str | int | None]  # what reached the rules, per completed run


class CaseResult(BaseModel):
    id: str
    title: str
    note: str
    originals: list[str]
    fields: list[FieldResult]
    same_findings: int
    runs: int
    failed: int
    seconds: list[float]


class Summary(BaseModel):
    model: str
    run_on: date
    cases: int
    runs: int
    values: int
    correct: int
    cleared: int
    missed: int
    wrong: int
    same_findings: int
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
        rs = [r for r in all_runs if r.grounded is not None]
        rows.append(
            CaseResult(
                id=c.id,
                title=c.title,
                note=c.note,
                originals=[o.split("/")[-1] for o in c.originals],
                fields=[
                    FieldResult(
                        field=f,
                        expected=getattr(c.expected, f),
                        outcomes=[outcome(f, c.expected, r) for r in rs],
                        read=[getattr(r.grounded, f) for r in rs],
                    )
                    for f in FIELDS
                ],
                same_findings=sum(same_findings(c, r) for r in rs),
                runs=len(all_runs),
                failed=len(all_runs) - len(rs),
                seconds=[r.seconds for r in all_runs],
            )
        )
    tally = [o for r in rows for f in r.fields for o in f.outcomes]
    seconds = sorted(t for r in rows for t in r.seconds) or [0.0]
    return Evaluation(
        summary=Summary(
            model=data.model,
            run_on=data.run_on,
            cases=len(rows),
            runs=sum(r.runs for r in rows),
            values=len(tally),
            correct=tally.count("correct"),
            cleared=tally.count("cleared"),
            missed=tally.count("missed"),
            wrong=tally.count("wrong"),
            same_findings=sum(r.same_findings for r in rows),
            failed=sum(r.failed for r in rows),
            median_seconds=round(seconds[len(seconds) // 2], 1),
            max_seconds=round(seconds[-1], 1),
        ),
        cases=rows,
    )


async def _read(originals: list[Original]) -> Reading:
    from google.adk.runners import InMemoryRunner

    runner = InMemoryRunner(agent=reader_agent, app_name="reader-eval")
    session = await runner.session_service.create_session(app_name="reader-eval", user_id="eval")
    async for _ in runner.run_async(user_id="eval", session_id=session.id, new_message=build_content(originals)):
        pass
    session = await runner.session_service.get_session(app_name="reader-eval", user_id="eval", session_id=session.id)
    return Reading.model_validate(session.state["reading"])


async def _run_case(c: ReaderCase, runs: int, gate: asyncio.Semaphore) -> StoredCase:
    originals = [Original.from_path(DATA_DIR / o) for o in c.originals]
    out: list[Run] = []
    for _ in range(runs):
        async with gate:
            start = time.monotonic()
            try:
                reading = await _read(originals)
            except Exception as e:  # recorded as a failed run, as the app would report it
                out.append(Run(read=None, grounded=None, seconds=round(time.monotonic() - start, 1), error=type(e).__name__))
                continue
            seconds = round(time.monotonic() - start, 1)
        g = ground(reading, originals)
        out.append(Run(read=reading.instruction, grounded=g.instruction, unverified=list(g.unverified), seconds=seconds))
    return StoredCase(id=c.id, runs=out)


async def run(runs: int = RUNS) -> Stored:
    gate = asyncio.Semaphore(2)  # more at once makes replies slow enough to hit the timeout
    results = await asyncio.gather(*(_run_case(c, runs, gate) for c in cases()))
    return Stored(model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"), run_on=date.today(), cases=list(results))


if __name__ == "__main__":
    data = asyncio.run(run(int(sys.argv[1]) if len(sys.argv) > 1 else RUNS))
    RESULTS.write_text(data.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
    s = evaluation(data).summary
    print(f"{s.values} values: {s.correct} correct, {s.cleared} cleared, {s.missed} missed, {s.wrong} wrong; "
          f"same findings {s.same_findings}/{s.runs - s.failed}; failed {s.failed}; "
          f"median {s.median_seconds}s, max {s.max_seconds}s")
