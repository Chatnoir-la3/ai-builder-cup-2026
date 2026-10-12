"""Deterministic checks: compare a payment and its instruction with the ledger.

The model only reads the original document into an `Instruction`; every decision is made here.
Checks rely on facts that are hard for a fraudster to change (account history, registered domains,
how a person usually instructs payments), not on wording such as "urgent" or "confidential".
Facts from outside the ledger (Web Risk, the company registry, domain age) arrive as `Lookups`,
fetched before the check, so the check itself stays deterministic.

A check that could not be made does not count as passed. A value the reader returned but the original
does not show is removed before the rules see it (`reader.ground`), and a Web Risk lookup can fail: each
is a finding of its own, so the approver is asked to call rather than shown nothing.
"""

import re
import unicodedata
from collections.abc import Sequence

from .models import CHANNEL_NAMES, BankAccount, CheckResult, Contact, Finding, Instruction, Ledger, Lookups, Payment, Person, Vendor

RECENT_DAYS = 30
AMOUNT_RATIO = 1.5
MIN_HISTORY = 3
LOOKALIKE_DISTANCE = 2
NEW_DOMAIN_DAYS = 90
NEW_COMPANY_DAYS = 365
# Instruction fields the rules compare; when the original does not show one the reader returned, the rule using it cannot run.
RULE_FIELDS: dict[str, str] = {
    "sender_name": "sender",
    "sender_address": "sender address",
    "account_number": "account number",
    "amount": "amount",
}

_LEGAL_FORMS = re.compile(r"[(（]?(?:カ|ユ|ド|ゴ|メ|シヤ|ザイ)[)）]|[(（](?:カ|ユ|ド|ゴ|メ)$")
_SMALL_KANA = str.maketrans("ァィゥェォッャュョヮ", "アイウエオツヤユヨワ")
_HOMOGLYPHS = (("rn", "m"), ("vv", "w"), ("0", "o"), ("1", "l"))
_COMPANY_NAME = re.compile(r"株式会社|有限会社|合同会社|合資会社|合名会社")
_HOLDER_LEGAL_FORM = re.compile(r"[(（)）](?:カ|ユ|ド|ゴ|メ|シヤ|ザイ)|(?:カ|ユ|ド|ゴ|メ|シヤ|ザイ)[)）]")


def normalize_holder(name: str) -> str:
    """Account holder names as banks print them: half-width kana, legal-form marks such as カ), no small kana."""
    s = unicodedata.normalize("NFKC", name).translate(_SMALL_KANA).replace("-", "ー")
    s = _LEGAL_FORMS.sub("", s)
    return re.sub(r"[\s.・]", "", s)


def _digits(s: str) -> str:
    return re.sub(r"\D", "", unicodedata.normalize("NFKC", s))


def edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _skeleton(domain: str) -> str:
    for src, dst in _HOMOGLYPHS:
        domain = domain.replace(src, dst)
    return domain


def looks_like(domain: str, known: str) -> bool:
    if domain == known:
        return False
    return _skeleton(domain) == _skeleton(known) or edit_distance(domain, known) <= LOOKALIKE_DISTANCE


def _email_domain(address: str | None) -> str | None:
    if not address or "@" not in address:
        return None
    return address.rsplit("@", 1)[1].strip().lower()


def _same_account(a: BankAccount, b: BankAccount) -> bool:
    return (a.bank_name, a.branch_name, _digits(a.number)) == (b.bank_name, b.branch_name, _digits(b.number))


def _sender_person(ledger: Ledger, ins: Instruction) -> Person | None:
    if not ins.sender_name:
        return None
    if _email_domain(ins.sender_address) in {d for v in ledger.vendors for d in v.email_domains}:
        return None  # a supplier's own address, even if the supplier's contact shares a family name
    name = re.sub(r"\s", "", ins.sender_name)
    return next((p for p in ledger.people if p.family_name in name), None)


def _account_findings(ledger: Ledger, payment: Payment, vendor: Vendor | None) -> list[Finding]:
    if vendor is None:
        return [Finding(code="NEW_PAYEE", facts={"payee": payment.payee_name}, fields=["payee_name", "account_number"])]
    registered = next((a for a in vendor.accounts if _same_account(a, payment.account)), None)
    if registered is None:
        return [
            Finding(
                code="ACCOUNT_NOT_REGISTERED",
                facts={"vendor": vendor.name, "account": payment.account.number},
                fields=["account_number"],
            )
        ]
    paid_before = any(
        h.vendor_id == vendor.id and _digits(h.account_number) == _digits(payment.account.number) for h in ledger.history
    )
    if paid_before or registered.verified_on is not None:
        return []  # confirmed by payment history or by a logged callback to the ledger contact
    if registered.registered_on:
        age = (payment.requested_on - registered.registered_on).days
        if age <= RECENT_DAYS:
            return [
                Finding(
                    code="ACCOUNT_RECENTLY_REGISTERED",
                    facts={"vendor": vendor.name, "days_ago": age},
                    fields=["account_number"],
                )
            ]
    # Never paid and never confirmed by a callback: however old the entry, it may have been planted.
    return [Finding(code="ACCOUNT_UNVERIFIED", facts={"vendor": vendor.name}, fields=["account_number"])]


def _holder_findings(payment: Payment, vendor: Vendor | None) -> list[Finding]:
    if vendor is None:
        holder = unicodedata.normalize("NFKC", payment.account.holder_kana)
        if _COMPANY_NAME.search(payment.payee_name) and not _HOLDER_LEGAL_FORM.search(holder):
            return [
                Finding(
                    code="HOLDER_NOT_COMPANY",
                    facts={"payee": payment.payee_name, "actual": payment.account.holder_kana},
                    fields=["account_holder"],
                )
            ]
        return []
    if normalize_holder(payment.account.holder_kana) == normalize_holder(vendor.holder_kana):
        return []
    return [
        Finding(
            code="HOLDER_MISMATCH",
            facts={"vendor": vendor.name, "expected": vendor.holder_kana, "actual": payment.account.holder_kana},
            fields=["account_holder"],
        )
    ]


def _amount_findings(ledger: Ledger, payment: Payment, vendor: Vendor | None) -> list[Finding]:
    if vendor is None:
        return []
    past = [h.amount for h in ledger.history if h.vendor_id == vendor.id]
    if len(past) < MIN_HISTORY or payment.amount <= max(past) * AMOUNT_RATIO:
        return []
    return [
        Finding(
            code="AMOUNT_ABOVE_HISTORY",
            facts={"amount": payment.amount, "past_max": max(past), "past_count": len(past)},
            fields=["amount"],
        )
    ]


def _domain_findings(ledger: Ledger, ins: Instruction, expected: list[str]) -> list[Finding]:
    domain = _email_domain(ins.sender_address)
    if ins.channel != "email" or domain is None:
        return []
    known = set(ledger.company_domains) | {d for v in ledger.vendors for d in v.email_domains}
    if domain in known and (not expected or domain in expected):
        return []
    similar = next((k for k in sorted(known) if looks_like(domain, k)), None)
    if similar:
        return [Finding(code="SENDER_DOMAIN_LOOKALIKE", facts={"domain": domain, "looks_like": similar}, fields=["sender_address"])]
    if expected:
        return [
            Finding(
                code="SENDER_DOMAIN_UNREGISTERED",
                facts={"domain": domain, "registered": ", ".join(expected)},
                fields=["sender_address"],
            )
        ]
    return []


def _channel_findings(ins: Instruction, who: str, usual: list[str]) -> list[Finding]:
    if ins.channel in usual:
        return []
    return [
        Finding(
            code="UNUSUAL_CHANNEL",
            facts={
                "who": who,
                "channel": CHANNEL_NAMES[ins.channel],
                "usual": ", ".join(CHANNEL_NAMES.get(c, c) for c in usual),
            },
            fields=["sender_name", "sender_address"],
        )
    ]


def _instruction_findings(payment: Payment, ins: Instruction) -> list[Finding]:
    diffs: dict[str, str | int] = {}
    fields: list[str] = []
    if ins.account_number and _digits(ins.account_number) != _digits(payment.account.number):
        diffs |= {"instruction_account": ins.account_number, "payment_account": payment.account.number}
        fields.append("account_number")
    if ins.amount is not None and ins.amount != payment.amount:
        diffs |= {"instruction_amount": ins.amount, "payment_amount": payment.amount}
        fields.append("amount")
    return [Finding(code="INSTRUCTION_MISMATCH", facts=diffs, fields=fields)] if diffs else []


def _unconfirmed_findings(unverified: Sequence[str]) -> list[Finding]:
    fields = [f for f in RULE_FIELDS if f in unverified]
    if not fields:
        return []
    return [Finding(code="NOT_IN_ORIGINAL", facts={"fields": ", ".join(RULE_FIELDS[f] for f in fields)}, fields=fields)]


def _lookup_findings(payment: Payment, ins: Instruction, vendor: Vendor | None, lookups: Lookups) -> list[Finding]:
    findings = [Finding(code="URL_LISTED", facts={"url": url}) for url in lookups.listed_urls]
    if "web_risk" in lookups.failed:
        findings.append(Finding(code="LOOKUP_FAILED", facts={"lookup": "Google Web Risk"}))
    domain = _email_domain(ins.sender_address)
    if ins.channel == "email" and domain and lookups.domain_age_days is not None and lookups.domain_age_days < NEW_DOMAIN_DAYS:
        findings.append(
            Finding(code="NEW_DOMAIN", facts={"domain": domain, "days": lookups.domain_age_days}, fields=["sender_address"])
        )
    if vendor is None:
        if lookups.company_found is False:
            findings.append(Finding(code="COMPANY_NOT_FOUND", facts={"payee": payment.payee_name}, fields=["payee_name"]))
        elif lookups.company_age_days is not None and lookups.company_age_days < NEW_COMPANY_DAYS:
            findings.append(
                Finding(
                    code="NEW_COMPANY",
                    facts={"payee": payment.payee_name, "days": lookups.company_age_days},
                    fields=["payee_name"],
                )
            )
    return findings


def check(
    ledger: Ledger, payment: Payment, ins: Instruction, lookups: Lookups | None = None, unverified: Sequence[str] = ()
) -> CheckResult:
    """`unverified`: instruction fields the reader returned but the original does not show (`reader.ground`)."""
    lookups = lookups or Lookups()
    vendor = next((v for v in ledger.vendors if v.id == payment.vendor_id), None)
    person = _sender_person(ledger, ins)

    findings = _account_findings(ledger, payment, vendor)
    findings += _holder_findings(payment, vendor)
    findings += _amount_findings(ledger, payment, vendor)

    verify_with: Contact | None = None
    if person is not None:
        findings += _domain_findings(ledger, ins, ledger.company_domains)
        findings += _channel_findings(ins, f"{person.full_name} ({person.role})", list(person.usual_channels))
        verify_with = person.contact
    elif vendor is not None:
        findings += _domain_findings(ledger, ins, vendor.email_domains)
        findings += _channel_findings(ins, vendor.name, list(vendor.usual_channels))
        verify_with = vendor.contact
    else:
        findings += _domain_findings(ledger, ins, [])
        if lookups.official_contact is not None:
            verify_with = lookups.official_contact.model_copy(update={"source": "official"})

    findings += _instruction_findings(payment, ins)
    findings += _unconfirmed_findings(unverified)
    findings += _lookup_findings(payment, ins, vendor, lookups)
    return CheckResult(findings=findings, verify_with=verify_with)
