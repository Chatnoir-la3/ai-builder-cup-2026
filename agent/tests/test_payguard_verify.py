from app.payguard import demo
from app.payguard.approvals import store
from app.payguard.verify import Ask, Statement, ask_for, compare

ROUTINE = demo.scenario_for("P-1001").payment  # いさな銀行 1234567, ¥462,000
CHANGED = demo.scenario_for("P-1002").payment  # the account the email asked for: ゆうなぎ銀行 8812345, ¥486,000
CEO = demo.scenario_for("P-1003").payment  # ゆうなぎ銀行 5503921, ¥3,000,000
REQUEST = Ask(request=True)


def test_supplier_states_the_bank_and_the_last_four_digits():
    result = compare(Statement(bank_name="Yuunagi Bank", account_number="2345"), CHANGED)
    assert result.outcome == "confirmed"
    assert result.mismatched == [] and result.missing == []


def test_the_whole_number_is_fine_too_and_digits_are_normalized():
    assert compare(Statement(bank_name="いさな銀行", account_number="１２３-４５６７"), ROUTINE).outcome == "confirmed"


def test_bank_names_are_recognized_in_either_script():
    for said in ("Yunagi", "ゆうなぎ", "ユウナギ銀行", "YUUNAGI BANK"):
        assert compare(Statement(bank_name=said, account_number="2345"), CHANGED).outcome == "confirmed", said


def test_supplier_states_its_registered_account_not_the_one_in_the_email():
    result = compare(Statement(bank_name="Isana Bank", account_number="1234567"), CHANGED)
    assert result.outcome == "mismatch"
    assert result.mismatched == ["bank_name", "account_number"]


def test_last_four_digits_that_differ_are_a_mismatch():
    result = compare(Statement(bank_name="Yuunagi Bank", account_number="4567"), CHANGED)
    assert result.outcome == "mismatch" and result.mismatched == ["account_number"]


def test_fewer_than_four_digits_confirm_nothing():
    result = compare(Statement(bank_name="Yuunagi Bank", account_number="345"), CHANGED)
    assert result.outcome == "incomplete" and result.missing == ["account_number"]


def test_a_bank_code_cannot_recognize_confirms_nothing():
    result = compare(Statement(bank_name="Younagi", account_number="2345"), CHANGED)
    assert result.outcome == "incomplete" and result.missing == ["bank_name"]


def test_supplier_amount_is_not_compared_unless_asked():
    stated = Statement(bank_name="Yuunagi Bank", account_number="8812345", amount=480000)
    assert compare(stated, CHANGED).outcome == "confirmed"
    result = compare(stated, CHANGED, Ask(amount=True))
    assert result.outcome == "mismatch" and result.mismatched == ["amount"]


def test_amount_asked_for_must_be_stated():
    result = compare(Statement(bank_name="Yuunagi Bank", account_number="2345"), CHANGED, Ask(amount=True))
    assert result.outcome == "incomplete" and result.missing == ["amount"]


def test_requester_confirms_the_request_and_the_amount():
    assert compare(Statement(requested=True, payee="Rurikake LLC", amount=3000000), CEO, REQUEST).outcome == "confirmed"


def test_requester_who_does_not_say_the_amount_confirms_nothing():
    result = compare(Statement(requested=True), CEO, REQUEST)
    assert result.outcome == "incomplete" and result.missing == ["amount"]


def test_requester_with_a_different_amount_or_account():
    assert compare(Statement(requested=True, amount=300000), CEO, REQUEST).mismatched == ["amount"]
    assert compare(Statement(requested=True, account_number="9999", amount=3000000), CEO, REQUEST).mismatched == ["account_number"]


def test_an_amount_alone_is_not_a_request():
    result = compare(Statement(amount=3000000), CEO, REQUEST)
    assert result.outcome == "incomplete" and result.missing == ["requested"]


def test_refusal_cannot_confirm():
    assert compare(Statement(refused=True, bank_name="Isana", account_number="4567"), ROUTINE).outcome == "incomplete"


def test_denial_is_its_own_outcome():
    assert compare(Statement(denied=True), CEO, REQUEST).outcome == "denied"


def test_mismatch_wins_over_missing():
    result = compare(Statement(account_number="9999999"), ROUTINE)
    assert result.outcome == "mismatch"
    assert result.mismatched == ["account_number"] and result.missing == ["bank_name"]


def test_whom_the_call_asks_follows_the_contact():
    store.reset()
    from app.payguard.rules import check

    for pid, request in (("P-1002", False), ("P-1003", True)):
        scenario = demo.scenario_for(pid)
        result = check(demo.ledger(), scenario.payment, scenario.instruction)
        assert ask_for(result.verify_with, result.asks_amount).request is request
