"""Approval queue for the demo: status and history per payment, kept in memory.

A flagged payment can be approved only after the approver confirms the callback to the ledger contact.
That is the company's rule, applied by code; the model never blocks or approves anything.
Decisions are logged as structured lines with codes only, never the originals.
"""

import json
import logging
import threading
from datetime import datetime, time, timedelta, timezone
from typing import Literal

from pydantic import BaseModel

from . import demo

JST = timezone(timedelta(hours=9))
Status = Literal["pending", "approved", "held"]
Decision = Literal["approved", "held"]

logger = logging.getLogger("payguard.approvals")


class HistoryItem(BaseModel):
    at: datetime
    event: Literal["received", "checked", "approved", "held"]
    detail: str = ""


class QueueItem(BaseModel):
    status: Status = "pending"
    findings: list[str] | None = None  # codes from the latest check; None until checked
    history: list[HistoryItem]


class DecisionError(Exception):
    pass


CHANNEL_NAMES = {"email": "email", "line": "LINE", "sms": "text message", "phone": "phone", "in_person": "in person"}


def _received(scenario: demo.Scenario) -> HistoryItem:
    at = datetime.combine(scenario.payment.requested_on, time(9, 0), tzinfo=JST)
    channel = CHANNEL_NAMES.get(scenario.instruction.channel, scenario.instruction.channel)
    return HistoryItem(at=at, event="received", detail=f"Payment request with an instruction by {channel}")


class ApprovalStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, QueueItem] = {}
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self._items = {s.payment.id: QueueItem(history=[_received(s)]) for s in demo.scenarios()}

    def get(self, payment_id: str) -> QueueItem:
        with self._lock:
            return self._items[payment_id].model_copy(deep=True)

    def checked(self, payment_id: str, codes: list[str]) -> None:
        detail = f"{len(codes)} point(s) differ from the usual pattern" if codes else "Nothing differs from the usual pattern"
        with self._lock:
            item = self._items[payment_id]
            item.findings = codes
            item.history.append(HistoryItem(at=datetime.now(JST), event="checked", detail=detail))

    def decide(self, payment_id: str, decision: Decision, callback_confirmed: bool) -> QueueItem:
        with self._lock:
            item = self._items[payment_id]
            if item.status != "pending":
                raise DecisionError("This payment has already been decided.")
            if decision == "approved":
                if item.findings is None:
                    raise DecisionError("Run the check before approving.")
                if item.findings and not callback_confirmed:
                    raise DecisionError("Confirm the callback before approving.")
            item.status = decision
            detail = "Callback to the ledger contact confirmed" if callback_confirmed else ""
            item.history.append(HistoryItem(at=datetime.now(JST), event=decision, detail=detail))
            logger.info(
                json.dumps(
                    {
                        "message": "payment decision",
                        "payment_id": payment_id,
                        "decision": decision,
                        "findings": item.findings,
                        "callback_confirmed": callback_confirmed,
                    }
                )
            )
            return item.model_copy(deep=True)


store = ApprovalStore()
