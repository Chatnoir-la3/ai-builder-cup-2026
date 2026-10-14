import json
from datetime import date

import pytest

from app.payguard import DATA_DIR, Instruction, Payment, check, load_demo_ledger
from app.payguard.rules import looks_like, normalize_holder

LEDGER = load_demo_ledger()
SCENARIOS = {s["id"]: s for s in json.loads((DATA_DIR / "scenarios.json").read_text(encoding="utf-8"))}


def scenario(sid: str) -> tuple[Payment, Instruction]:
    s = SCENARIOS[sid]
    return Payment.model_validate(s["payment"]), Instruction.model_validate(s["instruction"])


def codes(payment: Payment, ins: Instruction) -> set[str]:
    return {f.code for f in check(LEDGER, payment, ins).findings}


def test_routine_invoice_shows_nothing():
    result = check(LEDGER, *scenario("routine-invoice"))
    assert result.findings == []
    assert not result.show


def test_account_change_tax_audit():
    payment, ins = scenario("account-change-tax-audit")
    result = check(LEDGER, payment, ins)
    assert {f.code for f in result.findings} == {"ACCOUNT_NOT_REGISTERED", "HOLDER_MISMATCH", "SENDER_DOMAIN_LOOKALIKE"}
    lookalike = next(f for f in result.findings if f.code == "SENDER_DOMAIN_LOOKALIKE")
    assert lookalike.facts == {"domain": "tsubakur0-kenzai.example", "looks_like": "tsubakuro-kenzai.example"}


def test_callback_number_comes_from_ledger_not_instruction():
    payment, ins = scenario("account-change-tax-audit")
    result = check(LEDGER, payment, ins)
    assert result.verify_with is not None
    assert result.verify_with.phone == "03-0000-2001"


def test_ceo_chat_urgent_transfer():
    payment, ins = scenario("ceo-chat-urgent-transfer")
    result = check(LEDGER, payment, ins)
    assert {f.code for f in result.findings} == {"NEW_PAYEE", "UNUSUAL_CHANNEL"}
    assert result.verify_with is not None and result.verify_with.phone == "090-0000-1001"
    channel = next(f for f in result.findings if f.code == "UNUSUAL_CHANNEL")
    assert channel.facts["channel"] == "LINE"


def test_email_that_moved_the_request_to_a_chat_is_checked_too():
    from app.payguard.models import Lookups

    payment, ins = scenario("ceo-chat-urgent-transfer")
    seen = Lookups(email_senders=["sato.ichiro.office@freemail.example"])
    domain = next(f for f in check(LEDGER, payment, ins, seen).findings if f.code == "SENDER_DOMAIN_UNREGISTERED")
    assert domain.facts == {"domain": "freemail.example", "registered": ", ".join(LEDGER.company_domains)}
    # Sent from the company's own domain, the same email adds nothing.
    own = Lookups(email_senders=[f"sato@{LEDGER.company_domains[0]}"])
    assert {f.code for f in check(LEDGER, payment, ins, own).findings} == {"NEW_PAYEE", "UNUSUAL_CHANNEL"}


def test_colleague_forwarding_a_supplier_invoice_is_not_a_sender():
    from app.payguard.models import Lookups

    forwarded = Lookups(email_senders=[f"suzuki@{LEDGER.company_domains[0]}"])
    assert check(LEDGER, *scenario("routine-invoice"), forwarded).findings == []


def test_amount_above_history():
    payment, ins = scenario("routine-invoice")
    payment = payment.model_copy(update={"amount": 900_000})
    ins = ins.model_copy(update={"amount": 900_000})
    assert codes(payment, ins) == {"AMOUNT_ABOVE_HISTORY"}


def test_amount_within_history_is_quiet():
    payment, ins = scenario("routine-invoice")
    payment = payment.model_copy(update={"amount": 700_000})
    ins = ins.model_copy(update={"amount": 700_000})
    assert codes(payment, ins) == set()


def test_recently_registered_account_never_paid():
    payment, ins = scenario("routine-invoice")
    vendor = LEDGER.vendors[0]
    new_account = payment.account.model_copy(update={"number": "1111111", "registered_on": date(2026, 10, 1)})
    ledger = LEDGER.model_copy(
        update={"vendors": [vendor.model_copy(update={"accounts": [*vendor.accounts, new_account]}), *LEDGER.vendors[1:]]}
    )
    payment = payment.model_copy(update={"account": new_account})
    ins = ins.model_copy(update={"account_number": "1111111"})
    found = check(ledger, payment, ins).findings
    assert [f.code for f in found] == ["ACCOUNT_RECENTLY_REGISTERED"]
    assert found[0].facts["days_ago"] == 9


def test_recent_account_confirmed_by_callback_is_quiet():
    payment, ins = scenario("routine-invoice")
    vendor = LEDGER.vendors[0]
    new_account = payment.account.model_copy(
        update={"number": "1111111", "registered_on": date(2026, 10, 1), "verified_on": date(2026, 10, 1)}
    )
    ledger = LEDGER.model_copy(
        update={"vendors": [vendor.model_copy(update={"accounts": [*vendor.accounts, new_account]}), *LEDGER.vendors[1:]]}
    )
    payment = payment.model_copy(update={"account": new_account})
    ins = ins.model_copy(update={"account_number": "1111111"})
    assert check(ledger, payment, ins).findings == []


def test_instruction_and_payment_disagree():
    payment, ins = scenario("routine-invoice")
    ins = ins.model_copy(update={"account_number": "1234568", "amount": 426000})
    found = check(LEDGER, payment, ins).findings
    assert [f.code for f in found] == ["INSTRUCTION_MISMATCH"]
    assert found[0].fields == ["account_number", "amount"]


def test_unregistered_domain_from_known_supplier():
    payment, ins = scenario("routine-invoice")
    ins = ins.model_copy(update={"sender_address": "yamada.kenzai.sales@freemail.example"})
    assert codes(payment, ins) == {"SENDER_DOMAIN_UNREGISTERED"}


def test_supplier_contact_sharing_staff_family_name_is_not_staff():
    payment, ins = scenario("routine-invoice")
    ins = ins.model_copy(update={"sender_name": "ツバクロ建材 経理 鈴木"})
    assert codes(payment, ins) == set()


def test_wording_does_not_trigger_anything():
    # "Urgent" or "keep this quiet" is easy for a fraudster to drop, so it is not a signal on its own.
    payment, ins = scenario("routine-invoice")
    ins = ins.model_copy(update={"sender_name": "【至急・内密に】ツバクロ建材 営業部 田中"})
    assert codes(payment, ins) == set()


@pytest.mark.parametrize(
    ("printed", "registered"),
    [
        ("ﾂﾊﾞｸﾛｹﾝｻﾞｲ(ｶ", "ツバクロケンザイ(カ"),
        ("カ)ツバクロケンザイ", "ツバクロケンザイ（カ"),
        ("ヒサゴセツビ(カ", "カ)ヒサゴセツビ"),
        ("ショウワコウギョウ(カ", "シヨウワコウギヨウ(カ"),
    ],
)
def test_holder_names_match_across_bank_notation(printed, registered):
    assert normalize_holder(printed) == normalize_holder(registered)


@pytest.mark.parametrize(
    ("domain", "expected"),
    [
        ("tsubakur0-kenzai.example", True),
        ("tsubakuro-kenzal.example", True),
        ("tsubakuro-kenzai.example", False),
        ("nogiku-unso.example", False),
    ],
)
def test_lookalike_domains(domain, expected):
    assert looks_like(domain, "tsubakuro-kenzai.example") is expected


@pytest.mark.parametrize("fields", [["amount"], ["sender_address", "account_number"], ["sender_name"]])
def test_value_not_in_original_asks_for_a_call(fields):
    payment, ins = scenario("routine-invoice")
    result = check(LEDGER, payment, ins.model_copy(update={f: None for f in fields}), unverified=fields)
    assert [f.code for f in result.findings] == ["NOT_IN_ORIGINAL"]
    assert result.findings[0].fields == fields
    assert result.tier == "verify" and result.verify_with is not None


def test_unverified_field_the_rules_do_not_use_is_not_a_finding():
    result = check(LEDGER, *scenario("routine-invoice"), unverified=["payee_name", "account_holder"])
    assert result.findings == []


def test_failed_web_risk_lookup_asks_for_a_call():
    from app.payguard.models import Lookups

    result = check(LEDGER, *scenario("routine-invoice"), Lookups(failed=["web_risk"]))
    assert [f.code for f in result.findings] == ["LOOKUP_FAILED"]
    assert result.tier == "verify"


def test_failed_domain_age_lookup_alone_is_not_a_finding():
    from app.payguard.models import Lookups

    assert check(LEDGER, *scenario("routine-invoice"), Lookups(failed=["rdap"])).findings == []
