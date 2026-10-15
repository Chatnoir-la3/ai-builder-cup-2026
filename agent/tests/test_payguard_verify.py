from app.payguard import demo
from app.payguard.verify import Statement, compare

ROUTINE = demo.scenario_for("P-1001").payment  # いさな銀行 1234567, ¥462,000
CHANGED = demo.scenario_for("P-1002").payment  # the account the email asked for: 8812345, ¥486,000


def test_payee_states_the_same_account_and_amount():
    result = compare(Statement(account_number="1234567", amount=462000), ROUTINE)
    assert result.outcome == "confirmed"
    assert result.mismatched == [] and result.missing == []


def test_digits_are_compared_after_normalizing():
    result = compare(Statement(account_number="１２３-４５６７", amount=462000), ROUTINE)
    assert result.outcome == "confirmed"


def test_payee_states_its_registered_account_not_the_one_in_the_email():
    result = compare(Statement(account_number="1234567", amount=486000), CHANGED)
    assert result.outcome == "mismatch"
    assert result.mismatched == ["account_number"]


def test_amount_differs():
    result = compare(Statement(account_number="8812345", amount=480000), CHANGED)
    assert result.outcome == "mismatch"
    assert result.mismatched == ["amount"]


def test_a_value_not_stated_cannot_confirm():
    result = compare(Statement(account_number="1234567"), ROUTINE)
    assert result.outcome == "incomplete"
    assert result.missing == ["amount"]


def test_refusal_cannot_confirm():
    result = compare(Statement(refused=True, account_number="1234567", amount=462000), ROUTINE)
    assert result.outcome == "incomplete"


def test_denial_is_its_own_outcome():
    result = compare(Statement(denied=True), ROUTINE)
    assert result.outcome == "denied"


def test_mismatch_wins_over_missing():
    result = compare(Statement(account_number="9999999"), ROUTINE)
    assert result.outcome == "mismatch"
    assert result.mismatched == ["account_number"] and result.missing == ["amount"]
