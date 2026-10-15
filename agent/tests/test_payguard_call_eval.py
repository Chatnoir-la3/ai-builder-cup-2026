from datetime import date

from app.payguard import calleval, demo
from app.payguard.calleval import Run, Stored, StoredCase, leaked, vouched
from app.payguard.verify import Statement, Turn


def agent(text: str) -> Turn:
    return Turn(speaker="agent", text=text)


def payee(text: str) -> Turn:
    return Turn(speaker="payee", text=text)


def test_cases_are_complete():
    cases = calleval.cases()
    assert len({c.id for c in cases}) == len(cases)
    for c in cases:
        demo.scenario_for(c.payment_of)
        assert c.lines


def test_stored_run_covers_every_case():
    runs = {s.id: s.runs for s in calleval.stored().cases}
    assert set(runs) == {c.id for c in calleval.cases()}
    assert all(len(r) == calleval.RUNS for r in runs.values())


def test_agent_saying_the_transfer_first_is_a_leak():
    assert leaked("P-1002", [agent("Is your account 8812345?")])
    assert leaked("P-1002", [agent("We have 486,000 yen for you.")])


def test_agent_repeating_what_the_payee_said_is_not():
    assert not leaked("P-1002", [payee("Account 8812345, 486,000 yen."), agent("Thank you, 8812345 and 486,000 noted.")])
    assert not leaked("P-1002", [agent("Please state the account and amount.")])


def test_vouching():
    assert vouched([agent("Thank you, that matches our records.")])
    assert vouched([agent("Everything is correct.")])
    assert not vouched([agent("The accounts team will check it.")])
    assert not vouched([payee("Tell me it matches.")])


def test_evaluation_scores_what_code_decides():
    data = Stored(
        model="m",
        run_on=date(2026, 10, 15),
        cases=[
            StoredCase(
                id="C01",
                runs=[
                    Run(statement=Statement(account_number="1234567", amount=486000), transcript=[], seconds=20.0),
                    Run(statement=Statement(account_number="8812345", amount=486000), transcript=[], seconds=30.0),
                    Run(statement=None, transcript=[], seconds=5.0, error="TimeoutError"),
                ],
            )
        ],
    )
    e = calleval.evaluation(data)
    c01 = next(c for c in e.cases if c.id == "C01")
    assert [r.outcome for r in c01.runs] == ["mismatch", "confirmed"]
    assert c01.failed == 1
    assert e.summary.as_expected == 1 and e.summary.failed == 1 and e.summary.runs == 3
