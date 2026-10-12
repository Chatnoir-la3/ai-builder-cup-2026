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
            notice=None,
        )

    monkeypatch.setattr(api, "run_check", run)


def test_list_starts_pending_and_unchecked():
    rows = client.get("/demo/payments").json()
    assert [r["id"] for r in rows] == ["P-1001", "P-1002", "P-1003"]
    assert {r["status"] for r in rows} == {"pending"}
    assert {r["findings"] for r in rows} == {None}
    assert [r["channel"] for r in rows] == ["email", "email", "line"]


def test_detail_includes_text_originals_inline_and_images_by_name():
    d = client.get("/demo/payments/P-1001").json()
    assert d["vendor_name"] == "ツバクロ建材株式会社"
    names = {o["name"]: o for o in d["originals"]}
    assert "462,000円" in names["routine-invoice.email.txt"]["text"]
    assert names["routine-invoice.invoice.png"]["text"] is None
    assert [h["event"] for h in d["history"]] == ["received"]


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


def test_flagged_payment_needs_callback_confirmation(fake_check):
    client.post("/check", json={"payment_id": "P-1002"})
    blocked = client.post("/demo/payments/P-1002/decision", json={"decision": "approved"})
    assert blocked.status_code == 409
    ok = client.post("/demo/payments/P-1002/decision", json={"decision": "approved", "callback_confirmed": True})
    assert ok.json()["status"] == "approved"
    assert ok.json()["history"][-1]["detail"] == "Callback to the ledger contact confirmed"


def test_hold_needs_no_check_and_decisions_are_final():
    assert client.post("/demo/payments/P-1003/decision", json={"decision": "held"}).json()["status"] == "held"
    assert client.post("/demo/payments/P-1003/decision", json={"decision": "approved"}).status_code == 409


def test_decision_log_has_codes_only(fake_check, caplog):
    client.post("/check", json={"payment_id": "P-1002"})
    with caplog.at_level("INFO", logger="payguard.approvals"):
        client.post("/demo/payments/P-1002/decision", json={"decision": "held"})
    logged = caplog.records[-1].getMessage()
    assert "ACCOUNT_NOT_REGISTERED" in logged
    assert "8812345" not in logged and "yarnada" not in logged


def test_reset_clears_decisions(fake_check):
    client.post("/demo/payments/P-1003/decision", json={"decision": "held"})
    client.post("/demo/reset")
    assert client.get("/demo/payments/P-1003").json()["status"] == "pending"


def test_list_reports_finding_counts_after_check(fake_check):
    client.post("/check", json={"payment_id": "P-1002"})
    rows = {r["id"]: r for r in client.get("/demo/payments").json()}
    assert rows["P-1002"]["findings"] == 3
    assert rows["P-1001"]["findings"] is None

