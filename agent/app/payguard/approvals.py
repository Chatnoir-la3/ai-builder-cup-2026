"""Approval queue for the demo: status, call log and history per payment (see storage for where).

The tier from the rules decides what approval needs; code enforces it, the model never approves anything.
- pass: one person approves.
- verify: someone calls the number from the check (the ledger's, or one found by Google Search) and logs
  the result; a second person, not the caller, then approves. An unconfirmed call puts it on hold.
- block: it cannot be approved.
A call records the account and amount the payee was asked to confirm; if the transfer or the number to
call changes, the call no longer counts. Once a payment is decided, a later check does not change what
the decision was based on.
An approval is recorded in the ledger (see ledger). Decisions are logged as structured lines with
codes only, never the originals or names.
"""

import json
import logging
import threading
from datetime import datetime, time, timedelta, timezone
from typing import Literal

from pydantic import BaseModel

from . import demo, ledger
from .models import CHANNEL_NAMES, CheckResult, Contact, Payment, Tier
from .storage import QUEUE, backend

JST = timezone(timedelta(hours=9))
Status = Literal["pending", "approved", "held"]
Decision = Literal["approved", "held"]

logger = logging.getLogger("payguard.approvals")


class HistoryItem(BaseModel):
    at: datetime
    event: Literal["received", "checked", "called", "approved", "held"]
    detail: str = ""


class CallLog(BaseModel):
    by: str
    at: datetime
    contact: Contact  # always the contact from the check, never one typed in
    confirmed: bool
    # The transfer the payee was asked about; None on calls logged before this was recorded.
    account_number: str | None = None
    amount: int | None = None


class QueueItem(BaseModel):
    status: Status = "pending"
    findings: list[str] | None = None  # codes from the latest check; None until checked
    tier: Tier | None = None
    verify_with: Contact | None = None
    call: CallLog | None = None
    history: list[HistoryItem]


class DecisionError(Exception):
    pass


def approvers() -> list[str]:
    return [p.full_name for p in ledger.current().people]


def _received(scenario: demo.Scenario) -> HistoryItem:
    at = datetime.combine(scenario.payment.requested_on, time(9, 0), tzinfo=JST)
    channel = CHANNEL_NAMES[scenario.instruction.channel]
    return HistoryItem(at=at, event="received", detail=f"Payment request with an instruction by {channel}")


def _transfer(payment: Payment) -> str:
    return f"account {payment.account.number}, ¥{payment.amount:,}"


def _same_transfer(call: CallLog, payment: Payment) -> bool:
    return (call.account_number, call.amount) == (payment.account.number, payment.amount)


def _number_from(contact: Contact) -> str:
    return "the number found by Google Search" if contact.source == "official" else "the ledger number"


class ApprovalStore:
    """One lock per process; the agent runs as a single instance, so reads and writes do not interleave."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            backend().clear(QUEUE)
            ledger.reset()

    def _load(self, payment_id: str) -> QueueItem:
        raw = backend().get(QUEUE, payment_id)
        if raw is not None:
            return QueueItem.model_validate(raw)
        return QueueItem(history=[_received(demo.scenario_for(payment_id))])

    def _save(self, payment_id: str, item: QueueItem) -> None:
        backend().put(QUEUE, payment_id, item.model_dump(mode="json"))

    def get(self, payment_id: str) -> QueueItem:
        with self._lock:
            return self._load(payment_id)

    def checked(self, payment_id: str, result: CheckResult) -> None:
        codes = [f.code for f in result.findings]
        detail = f"{len(codes)} point(s) differ from the usual pattern" if codes else "Nothing differs from the usual pattern"
        if result.tier == "block":
            detail += "; cannot be approved"
        payment = demo.scenario_for(payment_id).payment
        with self._lock:
            item = self._load(payment_id)
            if item.status != "pending":
                return  # decided: keep the check the decision was based on
            if item.call and (item.call.contact != result.verify_with or not _same_transfer(item.call, payment)):
                item.call = None  # a call about a different number or transfer no longer counts
            item.findings, item.tier, item.verify_with = codes, result.tier, result.verify_with
            item.history.append(HistoryItem(at=datetime.now(JST), event="checked", detail=detail))
            self._save(payment_id, item)

    def log_call(self, payment_id: str, by: str, confirmed: bool) -> QueueItem:
        with self._lock:
            item = self._load(payment_id)
            if item.status != "pending":
                raise DecisionError("This payment has already been decided.")
            if item.tier != "verify" or item.verify_with is None:
                raise DecisionError("This payment has no call to log.")
            if by not in approvers():
                raise DecisionError("Choose who made the call.")
            contact = item.verify_with
            payment = demo.scenario_for(payment_id).payment
            now = datetime.now(JST)
            item.call = CallLog(
                by=by, at=now, contact=contact, confirmed=confirmed, account_number=payment.account.number, amount=payment.amount
            )
            result = "confirmed" if confirmed else "did not confirm"
            item.history.append(
                HistoryItem(
                    at=now,
                    event="called",
                    detail=f"{by} called {contact.name} on {_number_from(contact)}: {result} {_transfer(payment)}",
                )
            )
            if not confirmed:
                item.status = "held"
                item.history.append(HistoryItem(at=now, event="held", detail="The call did not confirm it; tell your bank"))
                self._log(payment_id, item, "held")
            self._save(payment_id, item)
            return item

    def decide(self, payment_id: str, decision: Decision, approver: str | None = None) -> QueueItem:
        with self._lock:
            item = self._load(payment_id)
            if item.status != "pending":
                raise DecisionError("This payment has already been decided.")
            detail = ""
            if decision == "approved":
                detail = self._approval(item, approver)
                confirmed_on = item.call.at.date() if item.tier == "verify" and item.call else None
                ledger.record(demo.scenario_for(payment_id).payment, confirmed_on)
                detail = "; ".join(d for d in (detail, "recorded in the ledger") if d)
            item.status = decision
            item.history.append(HistoryItem(at=datetime.now(JST), event=decision, detail=detail))
            self._save(payment_id, item)
            self._log(payment_id, item, decision)
            return item

    @staticmethod
    def _approval(item: QueueItem, approver: str | None) -> str:
        if item.findings is None:
            raise DecisionError("Run the check before approving.")
        if item.tier == "block":
            raise DecisionError("This payment cannot be approved under your rules.")
        if item.tier == "pass":
            return ""
        call = item.call
        if call is None or not call.confirmed:
            raise DecisionError("Log a confirmed call before approving.")
        if approver not in approvers():
            raise DecisionError("Choose the second approver.")
        if approver == call.by:
            raise DecisionError("The second approval must be by someone other than the caller.")
        return f"Second approval by {approver}, after {call.by}'s call to {_number_from(call.contact)}"

    @staticmethod
    def _log(payment_id: str, item: QueueItem, decision: Decision) -> None:
        logger.info(
            json.dumps(
                {
                    "message": "payment decision",
                    "payment_id": payment_id,
                    "decision": decision,
                    "tier": item.tier,
                    "findings": item.findings,
                    "call_confirmed": item.call.confirmed if item.call else None,
                    "call_to": item.call.contact.source if item.call else None,
                }
            )
        )


store = ApprovalStore()
