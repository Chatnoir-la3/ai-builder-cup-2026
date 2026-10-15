import pytest

from app.payguard import demo
from app.payguard.approvals import AGENT, DecisionError, store
from app.payguard.rules import check
from app.payguard.verify import Statement, Turn

SESSION = "approver-session-0001"
TRANSCRIPT = [Turn(speaker="agent", text="This is an automated call."), Turn(speaker="payee", text="Account 8812345.")]


@pytest.fixture(autouse=True)
def fresh_store():
    store.reset()
    yield
    store.reset()


def checked(payment_id: str) -> None:
    s = demo.scenario_for(payment_id)
    store.checked(payment_id, check(demo.ledger(), s.payment, s.instruction))


def approver() -> str:
    return demo.ledger().people[0].full_name


def test_confirmed_agent_call_needs_one_person_to_approve():
    checked("P-1002")
    item = store.log_agent_call("P-1002", Statement(account_number="8812345", amount=486000), TRANSCRIPT)
    assert item.status == "pending"
    assert item.call is not None and item.call.by == AGENT and item.call.confirmed
    assert item.call.outcome == "confirmed" and item.call.transcript == TRANSCRIPT
    with pytest.raises(DecisionError):
        store.decide("P-1002", "approved", None, SESSION)  # still a person must approve
    done = store.decide("P-1002", "approved", approver(), SESSION)
    assert done.status == "approved"
    assert done.history[-1].detail.startswith(f"Approved by {approver()} after the verification call")


def test_payee_states_another_account_puts_payment_on_hold():
    checked("P-1002")
    item = store.log_agent_call("P-1002", Statement(account_number="1234567", amount=486000), TRANSCRIPT)
    assert item.status == "held" and not item.call.confirmed
    assert item.call.outcome == "mismatch" and item.call.mismatched == ["account_number"]
    assert "account number" in item.history[-2].detail


def test_person_denies_the_request_puts_payment_on_hold():
    checked("P-1003")
    item = store.log_agent_call("P-1003", Statement(denied=True), TRANSCRIPT)
    assert item.status == "held" and item.call.outcome == "denied"


def test_incomplete_agent_call_leaves_the_call_to_a_person():
    checked("P-1002")
    item = store.log_agent_call("P-1002", Statement(account_number="8812345"), TRANSCRIPT)
    assert item.status == "pending" and item.call is None
    assert item.history[-1].event == "called" and "call the number yourself" in item.history[-1].detail


def test_agent_call_only_for_a_payment_that_needs_one():
    checked("P-1001")
    with pytest.raises(DecisionError):
        store.log_agent_call("P-1001", Statement(account_number="1234567", amount=462000), TRANSCRIPT)
    checked("P-1004")
    with pytest.raises(DecisionError):
        store.log_agent_call("P-1004", Statement(account_number="1234567", amount=462000), TRANSCRIPT)
