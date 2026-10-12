import pytest

from app.payguard import DATA_DIR, demo, readereval
from app.payguard.models import Instruction
from app.payguard.readereval import Run, outcome

EXPECTED = Instruction(channel="email", sender_address="tanaka@tsubakur0-kenzai.example", account_number="8812345", amount=486000)


def run(grounded: Instruction | None, unverified: list[str] = ()) -> Run:
    return Run(read=grounded, grounded=grounded, unverified=list(unverified), seconds=1.0)


def test_cases_are_complete():
    cases = readereval.cases()
    assert len({c.id for c in cases}) == len(cases) == 10
    for c in cases:
        demo.scenario_for(c.payment_of)
        assert all((DATA_DIR / o).exists() for o in c.originals), c.id


def test_stored_run_covers_every_case():
    data = readereval.stored()
    runs = {s.id: s.runs for s in data.cases}
    assert set(runs) == {c.id for c in readereval.cases()}
    assert all(len(r) == readereval.RUNS for r in runs.values())


@pytest.mark.parametrize(
    ("grounded", "unverified", "field", "want"),
    [
        (EXPECTED.model_copy(update={"account_number": "８８１ ２３４５"}), [], "account_number", "correct"),
        (EXPECTED.model_copy(update={"account_number": "1234567"}), [], "account_number", "wrong"),
        (EXPECTED.model_copy(update={"amount": None}), ["amount"], "amount", "cleared"),
        (EXPECTED.model_copy(update={"amount": None}), [], "amount", "missed"),
        (EXPECTED.model_copy(update={"sender_name": "田中"}), [], "sender_name", "wrong"),  # expected empty
        (EXPECTED, [], "sender_name", "correct"),
    ],
)
def test_outcome(grounded, unverified, field, want):
    assert outcome(field, EXPECTED, run(grounded, unverified)) == want


def test_failed_runs_are_counted_not_scored():
    case = readereval.cases()[0]
    data = readereval.Stored(
        model="m",
        run_on="2026-10-12",
        cases=[
            readereval.StoredCase(
                id=case.id,
                runs=[run(case.expected), Run(read=None, grounded=None, seconds=25.0, error="TimeoutError")],
            )
        ],
    )
    s = readereval.evaluation(data).summary
    assert (s.runs, s.failed, s.values, s.correct, s.same_findings) == (2, 1, len(readereval.FIELDS), len(readereval.FIELDS), 1)
    assert s.max_seconds == 25.0


def test_summary_adds_up():
    s = readereval.evaluation().summary
    assert s.values == (s.runs - s.failed) * len(readereval.FIELDS)
    assert s.correct + s.cleared + s.missed + s.wrong == s.values
