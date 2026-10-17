"""The verification call: what the person on the call stated, compared with the transfer by code.

The call agent is told whom to call and what to ask, never the account or the amount being sent, so it
cannot lead the person to them or leak them. It records what they state; code compares that with the
transfer. A "confirmed" outcome therefore needs them to have said what the transfer uses: the model does
not know it, so it cannot make it up. Anything else is not a confirmation.

What is asked depends on whom the call reaches (`Ask`), so that the person can answer it:
- A supplier states the bank and the last four digits of the account (the whole number is fine too).
  The call goes to the ledger's number, so the person answering is the real supplier, who does not know the
  fraudster's account: a bank and four digits that both match the transfer are not a coincidence.
  The amount is asked only when a finding concerns it; otherwise a supplier's figure can differ for
  harmless reasons (fees deducted, invoices combined) and is not compared.
- Someone inside the paying company (a CEO named in a request) says whether they asked for it, and the
  amount. People rarely know an account number by heart; "I never asked" is what stops this fraud.
"""

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Literal

from pydantic import BaseModel, Field

from . import ledger
from .models import Contact, Payment

Outcome = Literal["confirmed", "mismatch", "denied", "incomplete"]
MIN_DIGITS = 4  # the last four digits of the account, or more
# The banks code can recognize, with how they are said in English. A bank it cannot recognize confirms
# nothing; one it recognizes as a different bank is a mismatch. In production: the Zengin bank list.
BANKS: dict[str, tuple[str, ...]] = {
    "いさな銀行": ("Isana",),
    "ゆうなぎ銀行": ("Yuunagi", "Yunagi"),
    "ほしみ信用金庫": ("Hoshimi",),
}
_BANK_WORDS = re.compile(r"shinkin|bank|銀行|信用金庫|しんきん|信金")
# Speech recognition bends unfamiliar bank names ("Isana" heard as "Iisan", "Yuunagi" as "You nagi"). A name this
# close to exactly one bank's is taken as that bank. The digits must still match, so a near name alone confirms
# nothing.
NEAR_BANK = 0.75


class Ask(BaseModel):
    """What the call asks for, and so what a confirmation needs.

    request: the call goes to someone inside the paying company: did they ask for it, and how much.
    amount: a finding concerns the amount, so a supplier states it too.
    """

    request: bool = False
    amount: bool = False

    def required(self) -> tuple[str, ...]:
        if self.request:
            return ("requested", "amount")
        return ("bank_name", "account_number", *(("amount",) if self.amount else ()))


def ask_for(contact: Contact | None, amount_flagged: bool) -> Ask:
    people = {p.contact.phone for p in ledger.current().people}
    return Ask(request=contact is not None and contact.phone in people, amount=amount_flagged)


class Statement(BaseModel):
    """What the person on the call stated, as recorded by the call agent."""

    bank_name: str | None = None
    branch_name: str | None = None
    account_number: str | None = Field(default=None, description="Digits as stated: the last four, or all")
    account_holder: str | None = None
    payee: str | None = Field(default=None, description="For a request: whom they asked to pay")
    amount: int | None = Field(default=None, description="Yen")
    requested: bool = Field(default=False, description="They say they asked for this transfer")
    refused: bool = Field(default=False, description="They would not state it")
    denied: bool = Field(default=False, description="They say they made no such request")
    refer_to: str | None = Field(default=None, description="Who they said can confirm it: a name or department")


class Turn(BaseModel):
    speaker: Literal["agent", "payee"]
    text: str


class CallCheck(BaseModel):
    outcome: Outcome
    mismatched: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


def _digits(s: str) -> str:
    return re.sub(r"\D", "", unicodedata.normalize("NFKC", s))


def _bank_key(name: str) -> str:
    s = unicodedata.normalize("NFKC", name).lower()
    s = "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)  # katakana to hiragana
    return _BANK_WORDS.sub("", re.sub(r"[\W_]", "", s))


def _bank_of(name: str, expected: str) -> str | None:
    """The bank a stated name refers to, if code recognizes it: by its name, or a name close to only one bank's."""
    key = _bank_key(name)
    if not key:
        return None
    keys = {bank: {_bank_key(bank), *(_bank_key(s) for s in said)} for bank, said in {**BANKS, expected: BANKS.get(expected, ())}.items()}
    for bank, known in keys.items():
        if key in known:
            return bank
    near = {bank for bank, known in keys.items() if any(SequenceMatcher(None, key, k).ratio() >= NEAR_BANK for k in known)}
    return near.pop() if len(near) == 1 else None


def _account(stated: str | None, expected: str) -> bool | None:
    digits = _digits(stated or "")
    if len(digits) < MIN_DIGITS:
        return None
    return _digits(expected).endswith(digits)


def _bank(stated: str | None, expected: str) -> bool | None:
    bank = _bank_of(stated, expected) if stated else None
    return None if bank is None else bank == expected


def compare(statement: Statement, payment: Payment, ask: Ask | None = None) -> CallCheck:
    ask = ask or Ask()
    if statement.denied:
        return CallCheck(outcome="denied")
    found: dict[str, bool | None] = {
        "requested": True if statement.requested else None,
        "bank_name": _bank(statement.bank_name, payment.account.bank_name),
        "account_number": _account(statement.account_number, payment.account.number),
        # A supplier's figure is compared only when it was asked for (see the module docstring).
        "amount": None if statement.amount is None or "amount" not in ask.required() else statement.amount == payment.amount,
    }
    mismatched = [f for f, ok in found.items() if ok is False]
    missing = [f for f in ask.required() if found[f] is None]
    if mismatched:
        return CallCheck(outcome="mismatch", mismatched=mismatched, missing=missing)
    if missing or statement.refused:
        return CallCheck(outcome="incomplete", missing=missing)
    return CallCheck(outcome="confirmed")
