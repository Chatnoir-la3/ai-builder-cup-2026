import json

import pytest
from google.genai import types

from app.payguard import demo
from app.payguard.explain import Explanation, Reason, acceptable, notice, template_notice, top_findings
from app.payguard.models import Contact, Finding
from app.payguard.pipeline import check_node, respond
from app.payguard.reader import FIELDS, Evidence, Reading

TAX_AUDIT = "P-1002"
CALLBACK = Contact(name="ツバクロ建材 営業部 田中", phone="03-0000-2001")


def faithful_reading(payment_id: str) -> Reading:
    """A reading whose every value is backed by the first original, as a careful model would return it."""
    scenario = demo.scenario_for(payment_id)
    first = demo.originals(scenario)[0]
    values = scenario.instruction.model_dump()
    evidence = [
        Evidence(field=f, source=1, quote=first.text if first.is_text else str(values[f]))
        for f in FIELDS
        if values[f] is not None
    ]
    return Reading(instruction=scenario.instruction, evidence=evidence)


def ransom_findings() -> list[Finding]:
    s = demo.scenario_for(TAX_AUDIT)
    from app.payguard.rules import check

    return check(demo.ledger(), s.payment, s.instruction).findings


def good_explanation() -> Explanation:
    return Explanation(
        action="Before approving, call ツバクロ建材 営業部 田中 at 03-0000-2001 using the number in your own records.",
        reasons=[
            Reason(code="ACCOUNT_NOT_REGISTERED", text="Account 8812345 is not the one registered for ツバクロ建材株式会社."),
            Reason(code="SENDER_DOMAIN_LOOKALIKE", text="The email came from tsubakur0-kenzai.example, not tsubakuro-kenzai.example."),
        ],
    )


# --- check node -------------------------------------------------------------


@pytest.fixture(autouse=True)
def web_risk(monkeypatch):
    """Stand in for Web Risk: Google's test phishing page is listed, nothing else."""
    from app.payguard import lookups

    monkeypatch.setattr(lookups, "listed", lambda urls: [u for u in urls if "testsafebrowsing.appspot.com" in u])


@pytest.mark.parametrize(
    ("payment_id", "route", "codes"),
    [
        ("P-1001", "quiet", []),
        ("P-1002", "explain", ["ACCOUNT_NOT_REGISTERED", "HOLDER_MISMATCH", "SENDER_DOMAIN_LOOKALIKE"]),
        ("P-1003", "explain", ["NEW_PAYEE", "UNUSUAL_CHANNEL"]),
        ("P-1004", "explain", ["URL_LISTED"]),
    ],
)
def test_check_node_routes_by_findings(payment_id, route, codes):
    event = check_node(faithful_reading(payment_id).model_dump(), payment_id)
    assert event.actions.route == route
    assert [f["code"] for f in event.actions.state_delta["check"]["findings"]] == codes


def test_check_node_accepts_the_shapes_a_model_node_may_emit():
    reading = faithful_reading(TAX_AUDIT)
    as_content = types.Content(role="model", parts=[types.Part.from_text(text=reading.model_dump_json())])
    for node_input in (reading, reading.model_dump(), reading.model_dump_json(), as_content):
        assert check_node(node_input, TAX_AUDIT).actions.route == "explain"


def test_check_node_hands_the_explainer_findings_only():
    payload = check_node(faithful_reading(TAX_AUDIT).model_dump(), TAX_AUDIT).actions.state_delta["explain_input"]
    assert set(payload) == {"findings", "verify_with"}
    assert [f["code"] for f in payload["findings"]] == ["ACCOUNT_NOT_REGISTERED", "SENDER_DOMAIN_LOOKALIKE"]
    assert "税務調査" not in json.dumps(payload, ensure_ascii=False)


def test_misread_value_does_not_reach_the_rules():
    reading = faithful_reading("P-1001")
    # The model claims a different account but quotes nothing that says so.
    reading.instruction.account_number = "9999999"
    reading.evidence = [e for e in reading.evidence if e.field != "account_number"]
    reading.evidence.append(Evidence(field="account_number", source=1, quote="普通 9999999"))
    event = check_node(reading.model_dump(), "P-1001")
    assert event.actions.route == "quiet"
    assert event.actions.state_delta["grounded"]["unverified"] == ["account_number"]


# --- explainer checks -------------------------------------------------------


def test_top_findings_keep_the_two_most_telling():
    assert [f.code for f in top_findings(ransom_findings())] == ["ACCOUNT_NOT_REGISTERED", "SENDER_DOMAIN_LOOKALIKE"]


def test_good_explanation_is_used():
    n = notice(good_explanation(), ransom_findings(), CALLBACK)
    assert n is not None and n.source == "model"


@pytest.mark.parametrize(
    "broken",
    [
        {"action": "Before approving, check with the supplier."},  # no ledger phone number
        {"action": "Before approving, call 03-9999-0000 as the email asks."},  # a number from nowhere
        {"reasons": [Reason(code="ACCOUNT_NOT_REGISTERED", text="Account 8812345 is not registered.")]},  # one missing
        {
            "reasons": [
                Reason(code="ACCOUNT_NOT_REGISTERED", text="Account 8812345 is not registered."),
                Reason(code="HOLDER_MISMATCH", text="The holder differs."),  # not one of the top two
            ]
        },
        {
            "reasons": [
                Reason(code="ACCOUNT_NOT_REGISTERED", text="This is a scam account 8812345."),
                Reason(code="SENDER_DOMAIN_LOOKALIKE", text="The domain looks like the real one."),
            ]
        },
        {"action": "Before approving, call 03-0000-2001. " + "Please be careful. " * 15},
    ],
)
def test_bad_explanation_falls_back_to_template(broken):
    explanation = good_explanation().model_copy(update=broken)
    assert not acceptable(explanation, ransom_findings(), CALLBACK)
    n = notice(explanation, ransom_findings(), CALLBACK)
    assert n is not None and n.source == "template"


def test_template_notice_gives_ledger_number_and_top_reasons():
    n = template_notice(ransom_findings(), CALLBACK)
    assert "03-0000-2001" in n.action
    assert [r.code for r in n.reasons] == ["ACCOUNT_NOT_REGISTERED", "SENDER_DOMAIN_LOOKALIKE"]
    assert acceptable(Explanation(action=n.action, reasons=n.reasons), ransom_findings(), CALLBACK)


def test_template_notice_for_every_code_passes_its_own_checks():
    findings = [
        Finding(code="NEW_PAYEE", facts={"payee": "合同会社ルリカケ"}),
        Finding(code="ACCOUNT_RECENTLY_REGISTERED", facts={"vendor": "ツバクロ建材株式会社", "days_ago": 9}),
        Finding(code="AMOUNT_ABOVE_HISTORY", facts={"amount": 900000, "past_max": 517000, "past_count": 6}),
        Finding(code="SENDER_DOMAIN_UNREGISTERED", facts={"domain": "free.example", "registered": "tsubakuro-kenzai.example"}),
        Finding(code="UNUSUAL_CHANNEL", facts={"who": "佐藤 一郎 (代表取締役)", "channel": "LINE", "usual": "email"}),
        Finding(code="INSTRUCTION_MISMATCH", facts={"instruction_amount": 1, "payment_amount": 2}),
        Finding(code="ACCOUNT_UNVERIFIED", facts={"vendor": "ツバクロ建材株式会社"}),
        Finding(code="URL_LISTED", facts={"url": "https://invoice.example/login"}),
        Finding(code="COMPANY_NOT_FOUND", facts={"payee": "株式会社ミサゴ交易"}),
        Finding(code="NEW_COMPANY", facts={"payee": "ウトウ商事株式会社", "days": 30}),
        Finding(code="HOLDER_NOT_COMPANY", facts={"payee": "ヒタキ精機株式会社", "actual": "スズキ タロウ"}),
        Finding(code="NEW_DOMAIN", facts={"domain": "utou-shoji.example", "days": 5}),
    ]
    for f in findings:
        n = template_notice([f], None)
        assert n.reasons[0].text and "{" not in n.reasons[0].text
        assert acceptable(Explanation(action=n.action, reasons=n.reasons), [f], None)


def test_no_findings_no_notice():
    assert notice(None, [], None) is None


def test_official_number_is_named_as_official():
    official = Contact(name="ヨシキリ工業 代表", phone="03-0000-3001", source="official")
    n = template_notice([Finding(code="NEW_PAYEE", facts={"payee": "株式会社ヨシキリ工業"})], official)
    assert "official number" in n.action and "03-0000-3001" in n.action


@pytest.mark.parametrize(
    ("findings", "verify_with", "says"),
    [
        ([Finding(code="URL_LISTED", facts={"url": "https://invoice.example/login"})], CALLBACK, "unsafe"),
        ([Finding(code="COMPANY_NOT_FOUND", facts={"payee": "株式会社ミサゴ交易"})], CALLBACK, "registry"),
        ([Finding(code="NEW_PAYEE", facts={"payee": "ウトウ商事株式会社"})], None, "independent number"),
    ],
)
def test_blocked_payment_notice_says_it_cannot_be_approved(findings, verify_with, says):
    n = notice(None, findings, verify_with)
    assert n is not None and n.action.startswith("This payment cannot be approved") and says in n.action
    assert "call" not in n.action


# --- response ---------------------------------------------------------------


def test_respond_uses_template_when_explainer_did_not_answer():
    state = dict(check_node(faithful_reading(TAX_AUDIT).model_dump(), TAX_AUDIT).actions.state_delta)
    response = respond(demo.scenario_for(TAX_AUDIT), state)
    assert response.notice is not None and response.notice.source == "template"
    assert response.verify_with == CALLBACK
    assert response.payment.id == TAX_AUDIT


def test_check_endpoint_rejects_unknown_payment():
    from fastapi.testclient import TestClient

    from main import app

    res = TestClient(app).post("/check", json={"payment_id": "P-0000"})
    assert res.status_code == 404


def test_listed_link_blocks_an_otherwise_routine_payment():
    state = check_node(faithful_reading("P-1004").model_dump(), "P-1004").actions.state_delta
    response = respond(demo.scenario_for("P-1004"), dict(state))
    assert response.tier == "block"
    assert response.notice is not None and response.notice.action.startswith("This payment cannot be approved")
