import pytest
from fastapi.testclient import TestClient

from app.payguard import api
from app.payguard.approvals import store
from app.payguard.pipeline import CheckResponse
from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_store():
    store.reset()
    yield
    store.reset()


@pytest.fixture
def fake_check(monkeypatch):
    """Stand in for the Gemini workflow: return the findings the rules give for the hand-written instruction."""
    from app.payguard import demo
    from app.payguard.reader import GroundedReading
    from app.payguard.rules import check

    async def run(payment_id: str) -> CheckResponse:
        s = demo.scenario_for(payment_id)
        result = check(demo.ledger(), s.payment, s.instruction)
        return CheckResponse(
            payment=s.payment,
            reading=GroundedReading(instruction=s.instruction, evidence=[], unverified=[]),
            findings=result.findings,
            verify_with=result.verify_with,
            tier=result.tier,
            notice=None,
        )

    monkeypatch.setattr(api, "run_check", run)


def test_list_starts_pending_and_unchecked():
    rows = client.get("/demo/payments").json()
    assert [r["id"] for r in rows] == ["P-1001", "P-1002", "P-1003", "P-1004"]
    assert {r["status"] for r in rows} == {"pending"}
    assert {r["findings"] for r in rows} == {None}
    assert [r["channel"] for r in rows] == ["email", "email", "line", "email"]


def test_detail_includes_text_originals_inline_and_images_by_name():
    d = client.get("/demo/payments/P-1001").json()
    assert d["vendor_name"] == "ツバクロ建材株式会社"
    names = {o["name"]: o for o in d["originals"]}
    assert "462,000円" in names["routine-invoice.email.txt"]["text"]
    assert names["routine-invoice.invoice.png"]["text"] is None
    assert [h["event"] for h in d["history"]] == ["received"]


def test_checks_stop_at_the_hourly_cap(fake_check, monkeypatch):
    monkeypatch.setattr(api, "CHECKS_PER_HOUR", 2)
    monkeypatch.setattr(api, "_hour", {"start": None, "count": 0})
    assert client.post("/check", json={"payment_id": "P-1001"}).status_code == 200
    assert client.post("/check", json={"payment_id": "P-1002"}).status_code == 200
    assert client.post("/check", json={"payment_id": "P-1001"}).status_code == 429
    # An unknown id is turned away before it counts.
    assert client.post("/check", json={"payment_id": "P-0000"}).status_code == 404


def test_unknown_payment_and_original_are_404():
    assert client.get("/demo/payments/P-0000").status_code == 404
    assert client.post("/check", json={"payment_id": "P-0000"}).status_code == 404
    assert client.get("/demo/originals/ledger.json").status_code == 404
    assert client.get("/demo/originals/..%2Fledger.json").status_code == 404


def test_original_image_is_served():
    res = client.get("/demo/originals/ceo-chat.line.png")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert res.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_cannot_approve_before_check():
    res = client.post("/demo/payments/P-1001/decision", json={"decision": "approved"})
    assert res.status_code == 409


def test_routine_payment_approves_after_check(fake_check):
    assert client.post("/check", json={"payment_id": "P-1001"}).status_code == 200
    d = client.post("/demo/payments/P-1001/decision", json={"decision": "approved"}).json()
    assert d["status"] == "approved"
    assert [h["event"] for h in d["history"]] == ["received", "checked", "approved"]


AP, CEO = "鈴木 花子", "佐藤 一郎"


CALLER_SESSION, APPROVER_SESSION = "caller-session-0001", "approver-session-0002"


def approve(payment_id: str, approver: str | None = None, session: str = APPROVER_SESSION):
    body = {"decision": "approved", "approver": approver, "session": session}
    return client.post(f"/demo/payments/{payment_id}/decision", json=body)


def call(payment_id: str, by: str, confirmed: bool, session: str = CALLER_SESSION):
    return client.post(f"/demo/payments/{payment_id}/call", json={"by": by, "confirmed": confirmed, "session": session})


def test_flagged_payment_needs_a_confirmed_call_and_a_second_person(fake_check):
    client.post("/check", json={"payment_id": "P-1002"})
    assert approve("P-1002", CEO).status_code == 409  # no call logged
    d = call("P-1002", AP, True).json()
    assert d["call"]["contact"]["phone"] == "03-0000-2001" and d["status"] == "pending"
    assert approve("P-1002").status_code == 409  # no second approver
    assert approve("P-1002", AP).status_code == 409  # the caller cannot also approve
    ok = approve("P-1002", CEO).json()
    assert ok["status"] == "approved"
    assert [h["event"] for h in ok["history"]] == ["received", "checked", "called", "approved"]
    assert ok["history"][-1]["detail"] == (
        f"Second approval by {CEO}, after {AP}'s call to the ledger number; recorded in the ledger"
    )


def test_approval_is_recorded_in_the_ledger_and_reset_forgets_it(fake_check):
    from app.payguard import demo, ledger
    from app.payguard.rules import check

    s = demo.scenario_for("P-1002")
    before = len(ledger.current().history)
    client.post("/check", json={"payment_id": "P-1002"})
    call("P-1002", AP, True)
    approve("P-1002", CEO)
    after = ledger.current()
    account = next(a for a in after.vendors[0].accounts if a.number == "8812345")
    assert account.verified_on is not None and len(after.history) == before + 1
    codes = {f.code for f in check(after, s.payment, s.instruction).findings}
    assert "ACCOUNT_NOT_REGISTERED" not in codes  # the confirmed account is now known
    client.post("/demo/reset")
    assert len(ledger.current().history) == before
    assert all(a.number != "8812345" for a in ledger.current().vendors[0].accounts)


def test_routine_approval_adds_to_history_only(fake_check):
    from app.payguard import ledger

    accounts = ledger.current().vendors[0].accounts
    client.post("/check", json={"payment_id": "P-1001"})
    approve("P-1001")
    assert ledger.current().vendors[0].accounts == accounts
    assert ledger.current().history[-1].amount == 462000


def test_unconfirmed_call_puts_payment_on_hold(fake_check):
    client.post("/check", json={"payment_id": "P-1003"})
    d = call("P-1003", AP, False).json()
    assert d["status"] == "held"
    assert approve("P-1003", CEO).status_code == 409


def test_call_must_be_by_staff_and_only_when_needed(fake_check):
    client.post("/check", json={"payment_id": "P-1001"})
    assert call("P-1001", AP, True).status_code == 409  # routine: nothing to call about
    client.post("/check", json={"payment_id": "P-1002"})
    assert call("P-1002", "someone else", True).status_code == 409


def test_blocked_payment_cannot_be_approved():
    from app.payguard.models import CheckResult, Finding

    store.checked("P-1003", CheckResult(findings=[Finding(code="NEW_PAYEE", facts={"payee": "x"})], verify_with=None))
    assert approve("P-1003", CEO).status_code == 409
    assert call("P-1003", AP, True).status_code == 409
    assert client.post("/demo/payments/P-1003/decision", json={"decision": "held"}).json()["status"] == "held"


def test_detail_carries_tier_and_approvers(fake_check):
    client.post("/check", json={"payment_id": "P-1002"})
    d = client.get("/demo/payments/P-1002").json()
    assert d["tier"] == "verify" and d["verify_with"]["source"] == "ledger" and d["call"] is None
    assert d["approvers"] == [CEO, AP]


def test_hold_needs_no_check_and_decisions_are_final():
    assert client.post("/demo/payments/P-1003/decision", json={"decision": "held"}).json()["status"] == "held"
    assert client.post("/demo/payments/P-1003/decision", json={"decision": "approved"}).status_code == 409


def test_decision_log_has_codes_only(fake_check, caplog):
    client.post("/check", json={"payment_id": "P-1002"})
    with caplog.at_level("INFO", logger="payguard.approvals"):
        client.post("/demo/payments/P-1002/decision", json={"decision": "held"})
    logged = caplog.records[-1].getMessage()
    assert "ACCOUNT_NOT_REGISTERED" in logged and '"tier": "verify"' in logged
    assert "8812345" not in logged and "tsubakur0" not in logged and "03-0000" not in logged


def test_reset_clears_decisions(fake_check):
    client.post("/demo/payments/P-1003/decision", json={"decision": "held"})
    client.post("/demo/reset")
    assert client.get("/demo/payments/P-1003").json()["status"] == "pending"


def test_list_reports_finding_counts_after_check(fake_check):
    client.post("/check", json={"payment_id": "P-1002"})
    rows = {r["id"]: r for r in client.get("/demo/payments").json()}
    assert rows["P-1002"]["findings"] == 3
    assert rows["P-1001"]["findings"] is None



def test_evaluation_lists_every_case_with_summary():
    d = client.get("/demo/eval").json()
    assert len(d["cases"]) == 28 and d["summary"]["as_expected"] == 28
    a12 = next(c for c in d["cases"] if c["id"] == "A12")
    assert a12["tier"] == "block" and a12["ledger_tier"] == "block" and a12["kind"] == "attack"


def test_evaluation_case_detail_and_404():
    d = client.get("/demo/eval/L04").json()
    assert d["ledger_tier"] == "block" and d["tier"] == "verify"
    assert d["verify_with"]["source"] == "official"
    assert client.get("/demo/eval/X99").status_code == 404


def test_reading_evaluation():
    d = client.get("/demo/eval/reading").json()
    assert d["summary"]["cases"] == 10 and len(d["cases"]) == 10
    assert {f["field"] for f in d["cases"][0]["fields"]} == {"channel", "sender_name", "sender_address", "account_number", "amount"}


def test_call_records_the_transfer_the_payee_confirmed(fake_check):
    client.post("/check", json={"payment_id": "P-1002"})
    d = call("P-1002", AP, True).json()
    assert (d["call"]["account_number"], d["call"]["amount"]) == ("8812345", 486000)
    assert d["history"][-1]["detail"].endswith("confirmed account 8812345, ¥486,000")


def test_call_about_a_different_transfer_no_longer_counts(fake_check):
    client.post("/check", json={"payment_id": "P-1002"})
    call("P-1002", AP, True)
    item = store.get("P-1002")
    item.call.amount = 100000  # as if the transfer had changed since the call
    store._save("P-1002", item)
    client.post("/check", json={"payment_id": "P-1002"})
    assert store.get("P-1002").call is None
    assert approve("P-1002", CEO).status_code == 409


def test_a_decided_payment_keeps_the_check_it_was_decided_on(fake_check):
    from app.payguard.models import CheckResult, Finding

    client.post("/check", json={"payment_id": "P-1001"})
    approve("P-1001")
    before = store.get("P-1001")
    store.checked("P-1001", CheckResult(findings=[Finding(code="NEW_PAYEE", facts={"payee": "x"})], verify_with=None))
    after = store.get("P-1001")
    assert after == before and after.tier == "pass" and after.findings == []


def test_second_approval_must_come_from_another_session(fake_check):
    client.post("/check", json={"payment_id": "P-1002"})
    call("P-1002", AP, True)
    res = approve("P-1002", CEO, session=CALLER_SESSION)  # another name, same browser
    assert res.status_code == 409 and "another browser" in res.json()["detail"]
    assert approve("P-1002", CEO).json()["status"] == "approved"


def test_session_is_required_and_never_shown(fake_check):
    client.post("/check", json={"payment_id": "P-1002"})
    no_session = client.post("/demo/payments/P-1002/call", json={"by": AP, "confirmed": True})
    assert no_session.status_code == 422
    d = call("P-1002", AP, True).json()
    assert CALLER_SESSION not in str(d) and "caller_session" not in str(d)
    assert client.post("/demo/payments/P-1002/decision", json={"decision": "approved", "approver": CEO}).status_code == 409


def test_a_check_after_a_call_cannot_lower_the_tier(fake_check):
    from app.payguard.models import CheckResult

    client.post("/check", json={"payment_id": "P-1002"})
    call("P-1002", AP, True)
    store.checked("P-1002", CheckResult(findings=[], verify_with=None))  # a later reading that finds nothing
    item = store.get("P-1002")
    assert item.tier == "verify" and item.call is not None and item.findings
    assert item.history[-1].detail.endswith("the earlier check stands, since a call is logged")
    assert approve("P-1002", CEO).json()["status"] == "approved"  # still needs the second approval it had
