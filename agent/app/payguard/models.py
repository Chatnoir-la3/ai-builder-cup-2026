from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Channel = Literal["email", "line", "sms", "phone", "in_person", "edi", "other"]
CHANNEL_NAMES: dict[str, str] = {
    "email": "email",
    "line": "LINE",
    "sms": "text message",
    "phone": "phone",
    "in_person": "in person",
    "edi": "EDI",
    "other": "another channel",
}


class BankAccount(BaseModel):
    bank_name: str
    branch_name: str
    account_type: Literal["ordinary", "current"]
    number: str
    holder_kana: str
    registered_on: date | None = None


class Contact(BaseModel):
    name: str
    phone: str


class Vendor(BaseModel):
    id: str
    name: str
    holder_kana: str
    accounts: list[BankAccount]
    email_domains: list[str]
    usual_channels: list[Channel]
    contact: Contact


class Person(BaseModel):
    """Someone inside the paying company who can instruct a payment."""

    family_name: str
    full_name: str
    role: str
    usual_channels: list[Channel]
    contact: Contact


class PastPayment(BaseModel):
    vendor_id: str
    account_number: str
    amount: int
    paid_on: date


class Ledger(BaseModel):
    company_domains: list[str]
    vendors: list[Vendor]
    people: list[Person]
    history: list[PastPayment]


class Payment(BaseModel):
    """A transfer waiting for approval in the bank's corporate internet banking."""

    id: str
    vendor_id: str | None = Field(description="Payee chosen from the vendor list; None for a payee not in the ledger")
    payee_name: str
    account: BankAccount
    amount: int
    requested_on: date


class Instruction(BaseModel):
    """What the payment instruction (email, chat screenshot, invoice) says, as read from the original."""

    channel: Channel
    sender_name: str | None = None
    sender_address: str | None = Field(default=None, description="Email address or chat account name as shown")
    payee_name: str | None = None
    account_number: str | None = None
    account_holder: str | None = None
    amount: int | None = None


FindingCode = Literal[
    "NEW_PAYEE",
    "ACCOUNT_NOT_REGISTERED",
    "ACCOUNT_RECENTLY_REGISTERED",
    "HOLDER_MISMATCH",
    "AMOUNT_ABOVE_HISTORY",
    "SENDER_DOMAIN_LOOKALIKE",
    "SENDER_DOMAIN_UNREGISTERED",
    "UNUSUAL_CHANNEL",
    "INSTRUCTION_MISMATCH",
]


class Finding(BaseModel):
    code: FindingCode
    facts: dict[str, str | int]
    fields: list[str] = Field(default_factory=list, description="Instruction fields to highlight in the original")


class CheckResult(BaseModel):
    findings: list[Finding]
    verify_with: Contact | None = Field(description="Callback contact taken from the ledger, never from the instruction")

    @property
    def show(self) -> bool:
        return bool(self.findings)
