"""The ledger the checks compare against, and what it records after an approval.

It starts as the demo ledger and grows by rule, never by the model: an approved payment joins the
payment history, and an account confirmed by a logged call is marked verified (added first if new),
so the next payment to it goes through quietly. A reset returns to the demo ledger.
"""

from datetime import date

from . import demo
from .models import Ledger, Payment, PastPayment
from .rules import _same_account
from .storage import LEDGER, backend

KEY = "demo"


def current() -> Ledger:
    raw = backend().get(LEDGER, KEY)
    return Ledger.model_validate(raw) if raw else demo.ledger().model_copy(deep=True)


def reset() -> None:
    backend().clear(LEDGER)


def record(payment: Payment, confirmed_on: date | None) -> Ledger:
    """`confirmed_on`: the day a call to the ledger contact confirmed this payment, if it needed one."""
    ledger = current()
    vendor = next((v for v in ledger.vendors if v.id == payment.vendor_id), None)
    if vendor is None:
        return ledger  # a new payee is not added without a vendor record of its own
    account = next((a for a in vendor.accounts if _same_account(a, payment.account)), None)
    if confirmed_on is not None:
        if account is None:
            vendor.accounts.append(payment.account.model_copy(update={"registered_on": confirmed_on, "verified_on": confirmed_on}))
        elif account.verified_on is None:
            account.verified_on = confirmed_on
    ledger.history.append(
        PastPayment(vendor_id=vendor.id, account_number=payment.account.number, amount=payment.amount, paid_on=payment.requested_on)
    )
    backend().put(LEDGER, KEY, ledger.model_dump(mode="json"))
    return ledger
