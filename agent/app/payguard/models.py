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
    verified_on: date | None = Field(default=None, description="When a callback to the ledger contact confirmed this account")


class Contact(BaseModel):
    name: str
    phone: str
    source: Literal["ledger", "official"] = Field(
        default="ledger",
        description="The company's own ledger, or a number the finder found on a public page (not proof it is the payee's)",
    )
    page: str | None = Field(default=None, description="For a number the finder found: the page that shows it")


class Vendor(BaseModel):
    id: str
    name: str
    holder_kana: str
    accounts: list[BankAccount]
    email_domains: list[str]
    usual_channels: list[Channel]
    contact: Contact
    accounts_contact: Contact | None = Field(
        default=None,
        description="Who handles their invoices and bank details (accounts receivable); verification calls go here when set",
    )


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


class Lookups(BaseModel):
    """Facts fetched before the check: by code (Web Risk, company registry, domain registration) and by the
    finder (the payee's official number). Unknown stays None, and the rules then say nothing about it,
    except that a Web Risk lookup that failed is a finding of its own."""

    listed_urls: list[str] = Field(default_factory=list, description="Links in the instruction that Web Risk lists")
    email_senders: list[str] = Field(default_factory=list, description="From address of each email among the originals, read from its header by code")
    domain_age_days: int | None = Field(default=None, description="Age of the sender's email domain")
    company_found: bool | None = Field(default=None, description="Whether a new payee is in the company registry")
    company_age_days: int | None = None
    official_contact: Contact | None = None
    failed: list[str] = Field(default_factory=list, description="Lookups that could not be made, such as web_risk")


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
    "ACCOUNT_UNVERIFIED",
    "URL_LISTED",
    "COMPANY_NOT_FOUND",
    "NEW_COMPANY",
    "HOLDER_NOT_COMPANY",
    "NEW_DOMAIN",
    "NOT_IN_ORIGINAL",
    "LOOKUP_FAILED",
]
Tier = Literal["pass", "verify", "block"]
BLOCKING: frozenset[str] = frozenset({"URL_LISTED", "COMPANY_NOT_FOUND"})


class Finding(BaseModel):
    code: FindingCode
    facts: dict[str, str | int]
    fields: list[str] = Field(default_factory=list, description="Instruction fields to highlight in the original")


class CheckResult(BaseModel):
    findings: list[Finding]
    verify_with: Contact | None = Field(
        description="Callback contact from the ledger, or the payee's official number; never from the instruction"
    )

    @property
    def show(self) -> bool:
        return bool(self.findings)

    @property
    def asks_amount(self) -> bool:
        """A finding concerns the amount, so the verification call asks for it."""
        return any("amount" in f.fields for f in self.findings)

    @property
    def tier(self) -> Tier:
        """pass: approve as usual. verify: call, log it, second approver. block: cannot be approved."""
        if not self.findings:
            return "pass"
        if BLOCKING & {f.code for f in self.findings} or self.verify_with is None:
            return "block"
        return "verify"
