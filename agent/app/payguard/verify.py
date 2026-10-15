"""The verification call: what the payee stated on the call, compared with the transfer by code.

The call agent is told whom to call and what to ask, never the account or the amount being sent, so it
cannot lead the payee to them or leak them. It records what the payee states; code compares that with the
transfer. A "confirmed" outcome therefore needs the payee to have said the very digits the transfer uses:
the model does not know them, so it cannot make them up. Anything else is not a confirmation.
"""

import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, Field

from .models import Payment

Outcome = Literal["confirmed", "mismatch", "denied", "incomplete"]
# What the payee must state for a call to confirm a transfer.
REQUIRED = ("account_number", "amount")


class Statement(BaseModel):
    """What the person on the call stated, as recorded by the call agent."""

    bank_name: str | None = None
    branch_name: str | None = None
    account_number: str | None = Field(default=None, description="Digits as stated")
    account_holder: str | None = None
    amount: int | None = Field(default=None, description="Yen")
    refused: bool = Field(default=False, description="The person would not state the account or amount")
    denied: bool = Field(default=False, description="The person says they made no such request")


class Turn(BaseModel):
    speaker: Literal["agent", "payee"]
    text: str


class CallCheck(BaseModel):
    outcome: Outcome
    mismatched: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


def _digits(s: str) -> str:
    return re.sub(r"\D", "", unicodedata.normalize("NFKC", s))


def compare(statement: Statement, payment: Payment) -> CallCheck:
    if statement.denied:
        return CallCheck(outcome="denied")
    expected = {"account_number": _digits(payment.account.number), "amount": payment.amount}
    stated = {
        "account_number": _digits(statement.account_number) if statement.account_number else None,
        "amount": statement.amount,
    }
    missing = [f for f in REQUIRED if not stated[f]]
    mismatched = [f for f in REQUIRED if stated[f] and stated[f] != expected[f]]
    if mismatched:
        return CallCheck(outcome="mismatch", mismatched=mismatched, missing=missing)
    if missing or statement.refused:
        return CallCheck(outcome="incomplete", missing=missing)
    return CallCheck(outcome="confirmed")
