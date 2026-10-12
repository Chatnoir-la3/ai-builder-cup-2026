"""Evaluation set: eighteen attacks (A) and ten genuine payments (L), from the desk simulation.

Each case gives a payment, what its instruction says, the ledger, and what the lookups would return
(Web Risk, company registry, domain age, the payee's official number). The lookups are given, not
fetched, so the result is the rules' alone and repeatable. `ledger`, `added` and `tier` are what we expect:
the findings from the ledger alone, the findings the lookups add, and the tier with them.
The reader (Gemini) is evaluated separately, on the demo originals (tests/test_payguard_reader_live.py).
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel

from . import demo
from .explain import _template_reason
from .models import BankAccount, Contact, Finding, Instruction, Ledger, Lookups, Payment, Tier
from .rules import check

TODAY = date(2026, 10, 10)
BASE = demo.ledger()
V1, V2, V3 = BASE.vendors  # ツバクロ建材 / ヒサゴ設備 / ノギク運送
CEO = BASE.people[0]
MULE = "オカノ タロウ"
TANAKA = V1.contact.name
OFFICIAL = {"name": "代表番号", "phone": "03-0000-3001"}


def acct(number: str, holder: str, days_ago: int | None = None, verified_days_ago: int | None = None) -> BankAccount:
    return BankAccount(
        bank_name="ゆうなぎ銀行",
        branch_name="中央支店",
        account_type="ordinary",
        number=number,
        holder_kana=holder,
        registered_on=TODAY - timedelta(days=days_ago) if days_ago is not None else None,
        verified_on=TODAY - timedelta(days=verified_days_ago) if verified_days_ago is not None else None,
    )


def with_account(vendor_id: str, account: BankAccount) -> Ledger:
    ledger = BASE.model_copy(deep=True)
    next(v for v in ledger.vendors if v.id == vendor_id).accounts.append(account)
    return ledger


def pay(vendor_id: str | None, payee: str, account: BankAccount, amount: int) -> Payment:
    return Payment(id="SIM", vendor_id=vendor_id, payee_name=payee, account=account, amount=amount, requested_on=TODAY)


def says(sender: str, address: str, account: BankAccount | None = None, amount: int | None = None, channel: str = "email") -> Instruction:
    return Instruction(
        channel=channel,
        sender_name=sender,
        sender_address=address,
        account_number=account.number if account else None,
        amount=amount,
    )


@dataclass
class Case:
    id: str
    title: str
    payment: Payment
    ins: Instruction
    ledger: set[str]
    ledger_number: bool  # the ledger has someone to call back
    tier: str
    added: set[str] = field(default_factory=set)
    lookups: dict = field(default_factory=dict)
    book: Ledger = field(default_factory=lambda: BASE)
    note: str = ""

    @property
    def kind(self) -> Literal["attack", "genuine"]:
        return "attack" if self.id.startswith("A") else "genuine"


ACCOUNT_CHANGE = pay(V1.id, V1.name, acct("8812345", MULE), 486000)
ACCOUNT_CHANGE_SAYS = says(TANAKA, "tanaka@tsubakuro-kenzai.example", acct("8812345", MULE), 486000)
LOOKALIKE_SAYS = says(TANAKA, "tanaka@tsubakur0-kenzai.example", acct("8812345", MULE), 486000)
POISONED = acct("8812345", V1.holder_kana, days_ago=45)

CASES = [
    Case("A01", "Account change from a look-alike domain (P-1002)", ACCOUNT_CHANGE, LOOKALIKE_SAYS,
         ledger={"ACCOUNT_NOT_REGISTERED", "HOLDER_MISMATCH", "SENDER_DOMAIN_LOOKALIKE"}, ledger_number=True,
         added={"NEW_DOMAIN"}, lookups={"domain_age_days": 6}, tier="verify"),
    Case("A02", "Account change replied from the supplier's hijacked mailbox", ACCOUNT_CHANGE, ACCOUNT_CHANGE_SAYS,
         ledger={"ACCOUNT_NOT_REGISTERED", "HOLDER_MISMATCH"}, ledger_number=True, tier="verify"),
    Case("A03", "Ledger changed 5 days earlier without a callback",
         pay(V1.id, V1.name, acct("8812345", V1.holder_kana, days_ago=5), 486000),
         says(TANAKA, "tanaka@tsubakuro-kenzai.example", POISONED, 486000),
         book=with_account(V1.id, acct("8812345", V1.holder_kana, days_ago=5)),
         ledger={"ACCOUNT_RECENTLY_REGISTERED"}, ledger_number=True, tier="verify"),
    Case("A04", "Ledger changed 45 days earlier without a callback, holder matches",
         pay(V1.id, V1.name, POISONED, 486000), says(TANAKA, "tanaka@tsubakuro-kenzai.example", POISONED, 486000),
         book=with_account(V1.id, POISONED),
         ledger={"ACCOUNT_UNVERIFIED"}, ledger_number=True, tier="verify"),
    Case("A05", "As A04, but the change was 'confirmed' on the number in the email",
         pay(V1.id, V1.name, POISONED, 486000), says(TANAKA, "tanaka@tsubakuro-kenzai.example", POISONED, 486000),
         book=with_account(V1.id, POISONED),
         ledger={"ACCOUNT_UNVERIFIED"}, ledger_number=True, tier="verify"),
    Case("A06", "The CEO on LINE, ¥3,000,000 to a new payee (P-1003)",
         pay(None, "合同会社ルリカケ", acct("5503921", "ド)ルリカケ"), 3000000), says(CEO.full_name, "佐藤一郎", channel="line"),
         ledger={"NEW_PAYEE", "UNUSUAL_CHANNEL"}, ledger_number=True,
         added={"NEW_COMPANY"}, lookups={"company_found": True, "company_age_days": 120}, tier="verify"),
    Case("A07", "The CEO by email from a look-alike of the company's domain, new payee",
         pay(None, "株式会社ミサゴ交易", acct("1112223", "カ)ミサゴコウエキ"), 2500000), says(CEO.full_name, "sato@miori-koumutan.example"),
         ledger={"NEW_PAYEE", "SENDER_DOMAIN_LOOKALIKE"}, ledger_number=True,
         added={"NEW_DOMAIN", "COMPANY_NOT_FOUND"}, lookups={"domain_age_days": 3, "company_found": False}, tier="block"),
    Case("A08", "A deepfake CEO on a video call, new overseas payee",
         pay(None, "Kestrelmoor Partners Ltd", acct("9090909", "ケストレルムーアパートナーズ"), 8000000),
         says(CEO.full_name, "web会議", channel="other"),
         ledger={"NEW_PAYEE", "UNUSUAL_CHANNEL"}, ledger_number=True,
         added={"COMPANY_NOT_FOUND"}, lookups={"company_found": False}, tier="block"),
    Case("A09", "Invoice from a shell company: incorporated a month ago, domain 5 days old",
         pay(None, "ウトウ商事株式会社", acct("3334445", "ウトウシヨウジ(カ"), 880000), says("ウトウ商事 経理部 山本", "billing@utou-shoji.example"),
         ledger={"NEW_PAYEE"}, ledger_number=False,
         added={"NEW_DOMAIN", "NEW_COMPANY"}, lookups={"domain_age_days": 5, "company_found": True, "company_age_days": 30}, tier="block"),
    Case("A10", "A new payee using a real company's name, paid to a personal account",
         pay(None, "ヒタキ精機株式会社", acct("4445556", "スズキ タロウ"), 640000), says("ヒタキ精機 営業 木村", "kimura@hitaki-seiki-jp.example"),
         ledger={"NEW_PAYEE", "HOLDER_NOT_COMPANY"}, ledger_number=False, added={"NEW_DOMAIN"},
         lookups={"domain_age_days": 12, "company_found": True, "company_age_days": 9000, "official_contact": OFFICIAL},
         tier="verify"),
    Case("A11", "An account another company has reported, new payee (no shared list: the callback catches it)",
         pay(None, "株式会社シギノ物産", acct("7778889", "カ)シギノブツサン"), 420000), says("シギノ物産 経理", "keiri@shigino-bussan.example"),
         ledger={"NEW_PAYEE"}, ledger_number=False,
         lookups={"domain_age_days": 400, "company_found": True, "company_age_days": 2000, "official_contact": OFFICIAL}, tier="verify"),
    Case("A12", "The instruction links to a page Web Risk lists as phishing",
         pay(None, "株式会社シギノ物産", acct("6667778", "カ)シギノブツサン"), 420000), says("シギノ物産 経理", "keiri@shigino-bussan.example"),
         ledger={"NEW_PAYEE"}, ledger_number=False, added={"URL_LISTED"},
         lookups={"listed_urls": ["https://shigino-bussan-invoice.example/login"], "domain_age_days": 400, "company_found": True, "company_age_days": 2000, "official_contact": OFFICIAL},
         tier="block"),
    Case("A13", "The email is right; only the attached invoice has a different account",
         pay(V1.id, V1.name, acct("8812345", MULE), 462000), says(TANAKA, "tanaka@tsubakuro-kenzai.example", V1.accounts[0], 462000),
         ledger={"ACCOUNT_NOT_REGISTERED", "HOLDER_MISMATCH", "INSTRUCTION_MISMATCH"}, ledger_number=True, tier="verify"),
    Case("A14", "Account change to another company with the same name",
         pay(V1.id, V1.name, acct("8812345", V1.holder_kana), 486000),
         says(TANAKA, "tanaka@tsubakuro-kenzai.example", acct("8812345", V1.holder_kana), 486000),
         ledger={"ACCOUNT_NOT_REGISTERED"}, ledger_number=True, tier="verify"),
    Case("A15", "Small amounts to a new account",
         pay(V3.id, V3.name, acct("2223334", V3.holder_kana), 48000),
         says(V3.contact.name, "unso@nogiku-unso.example", acct("2223334", V3.holder_kana), 48000),
         ledger={"ACCOUNT_NOT_REGISTERED"}, ledger_number=True, tier="verify"),
    Case("A16", "As A01, and the approver tries to approve without calling", ACCOUNT_CHANGE, LOOKALIKE_SAYS,
         ledger={"ACCOUNT_NOT_REGISTERED", "HOLDER_MISMATCH", "SENDER_DOMAIN_LOOKALIKE"}, ledger_number=True,
         added={"NEW_DOMAIN"}, lookups={"domain_age_days": 6}, tier="verify",
         note="The check flags it as in A01. The approval queue stops it: approving needs a recorded call and a second person."),
    Case("A17", "One person enters and approves, and does not call", ACCOUNT_CHANGE, ACCOUNT_CHANGE_SAYS,
         ledger={"ACCOUNT_NOT_REGISTERED", "HOLDER_MISMATCH"}, ledger_number=True, tier="verify",
         note="Known limit: with one person in accounts payable there is no second approver. The check still flags it."),
    Case("A18", "Insider: AP staff registered their own account as the supplier's 40 days ago",
         pay(V3.id, V3.name, acct("5556667", "スズキ ハナコ", days_ago=40), 97000), says(V3.contact.name, "unso@nogiku-unso.example"),
         book=with_account(V3.id, acct("5556667", "スズキ ハナコ", days_ago=40)),
         ledger={"HOLDER_MISMATCH", "ACCOUNT_UNVERIFIED"}, ledger_number=True, tier="verify"),
    Case("L01", "Routine payment", pay(V1.id, V1.name, V1.accounts[0], 462000),
         says(TANAKA, "tanaka@tsubakuro-kenzai.example", V1.accounts[0], 462000),
         ledger=set(), ledger_number=True, tier="pass"),
    Case("L02", "Account changed 60 days ago and confirmed on the ledger number, not paid yet",
         pay(V2.id, V2.name, acct("1212121", V2.holder_kana, days_ago=60, verified_days_ago=58), 1610000),
         says(V2.contact.name, "keiri@hisago-setsubi.example"),
         book=with_account(V2.id, acct("1212121", V2.holder_kana, days_ago=60, verified_days_ago=58)),
         ledger=set(), ledger_number=True, tier="pass"),
    Case("L03", "A genuine account change just arrived (bank merger)",
         pay(V1.id, V1.name, acct("3456789", V1.holder_kana), 462000),
         says(TANAKA, "tanaka@tsubakuro-kenzai.example", acct("3456789", V1.holder_kana), 462000),
         ledger={"ACCOUNT_NOT_REGISTERED"}, ledger_number=True, tier="verify"),
    Case("L04", "First payment to a genuine new supplier, 20 years old",
         pay(None, "株式会社ヨシキリ工業", acct("8887776", "カ)ヨシキリコウギヨウ"), 330000), says("ヨシキリ工業 営業 中村", "nakamura@yoshikiri-kogyo.example"),
         ledger={"NEW_PAYEE"}, ledger_number=False,
         lookups={"domain_age_days": 5000, "company_found": True, "company_age_days": 7300, "official_contact": OFFICIAL}, tier="verify"),
    Case("L05", "Seasonal large order, about twice the past maximum", pay(V2.id, V2.name, V2.accounts[0], 3700000),
         says(V2.contact.name, "keiri@hisago-setsubi.example", amount=3700000),
         ledger={"AMOUNT_ABOVE_HISTORY"}, ledger_number=True, tier="verify"),
    Case("L06", "The CEO really is travelling and asks on LINE (known supplier, registered account)",
         pay(V1.id, V1.name, V1.accounts[0], 462000), says(CEO.full_name, "佐藤一郎", channel="line"),
         ledger={"UNUSUAL_CHANNEL"}, ledger_number=True, tier="verify"),
    Case("L07", "The supplier renamed itself and changed its email domain", pay(V3.id, V3.name, V3.accounts[0], 97000),
         says(V3.contact.name, "unso@nogiku-logi.example"),
         ledger={"SENDER_DOMAIN_UNREGISTERED"}, ledger_number=True, added={"NEW_DOMAIN"}, lookups={"domain_age_days": 20}, tier="verify"),
    Case("L08", "The bank prints the holder in half-width kana",
         pay(V1.id, V1.name, V1.accounts[0].model_copy(update={"holder_kana": "ﾂﾊﾞｸﾛｹﾝｻﾞｲ(ｶ"}), 462000),
         says(TANAKA, "tanaka@tsubakuro-kenzai.example", V1.accounts[0], 462000),
         ledger=set(), ledger_number=True, tier="pass"),
    Case("L09", "Regular payment by EDI", pay(V2.id, V2.name, V2.accounts[0], 1610000), says(V2.contact.name, "EDI", channel="edi"),
         ledger=set(), ledger_number=True, tier="pass"),
    Case("L10", "A two-month-old startup becomes a supplier",
         pay(None, "株式会社ツグミラボ", acct("1357911", "カ)ツグミラボ"), 550000), says("ツグミラボ 代表 小林", "kobayashi@tsugumi-lab.example"),
         ledger={"NEW_PAYEE"}, ledger_number=False, added={"NEW_DOMAIN", "NEW_COMPANY"},
         lookups={"domain_age_days": 70, "company_found": True, "company_age_days": 60, "official_contact": OFFICIAL}, tier="verify"),
]



def check_with_lookups(c: Case):
    return check(c.book, c.payment, c.ins, Lookups.model_validate(c.lookups))


class CaseResult(BaseModel):
    id: str
    kind: Literal["attack", "genuine"]
    title: str
    note: str
    ledger_findings: list[str]
    ledger_tier: Tier
    findings: list[str]
    tier: Tier
    expected_tier: Tier
    as_expected: bool


class Reason(BaseModel):
    code: str
    text: str


class CaseDetail(CaseResult):
    payment: Payment
    instruction: Instruction
    lookups: Lookups
    reasons: list[Reason]
    verify_with: Contact | None


class Summary(BaseModel):
    """Counts with the lookups; `*_by_ledger` are the same counts from the ledger alone."""

    attacks: int
    attacks_stopped: int  # tier other than pass
    attacks_stopped_by_ledger: int
    attacks_blocked: int
    attacks_blocked_by_ledger: int
    genuine: int
    genuine_quiet: int
    genuine_calls: int
    genuine_blocked: int
    genuine_blocked_by_ledger: int
    as_expected: int


def _result(c: Case) -> tuple[CaseResult, list[Finding], Contact | None, Lookups]:
    lookups = Lookups.model_validate(c.lookups)
    alone = check(c.book, c.payment, c.ins)
    full = check_with_lookups(c)
    codes = [f.code for f in full.findings]
    result = CaseResult(
        id=c.id,
        kind=c.kind,
        title=c.title,
        note=c.note,
        ledger_findings=[f.code for f in alone.findings],
        ledger_tier=alone.tier,
        findings=codes,
        tier=full.tier,
        expected_tier=c.tier,  # type: ignore[arg-type]
        as_expected=set(codes) == c.ledger | c.added and full.tier == c.tier,
    )
    return result, full.findings, full.verify_with, lookups


def results() -> list[CaseResult]:
    return [_result(c)[0] for c in CASES]


def summary(rows: list[CaseResult]) -> Summary:
    attacks = [r for r in rows if r.kind == "attack"]
    genuine = [r for r in rows if r.kind == "genuine"]
    return Summary(
        attacks=len(attacks),
        attacks_stopped=sum(r.tier != "pass" for r in attacks),
        attacks_stopped_by_ledger=sum(r.ledger_tier != "pass" for r in attacks),
        attacks_blocked=sum(r.tier == "block" for r in attacks),
        attacks_blocked_by_ledger=sum(r.ledger_tier == "block" for r in attacks),
        genuine=len(genuine),
        genuine_quiet=sum(r.tier == "pass" for r in genuine),
        genuine_calls=sum(r.tier == "verify" for r in genuine),
        genuine_blocked=sum(r.tier == "block" for r in genuine),
        genuine_blocked_by_ledger=sum(r.ledger_tier == "block" for r in genuine),
        as_expected=sum(r.as_expected for r in rows),
    )


def detail(case_id: str) -> CaseDetail:
    c = next(c for c in CASES if c.id == case_id)
    result, findings, verify_with, lookups = _result(c)
    return CaseDetail(
        **result.model_dump(),
        payment=c.payment,
        instruction=c.ins,
        lookups=lookups,
        reasons=[Reason(code=f.code, text=_template_reason(f)) for f in findings],
        verify_with=verify_with,
    )
