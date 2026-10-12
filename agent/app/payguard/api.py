"""HTTP endpoints the web calls (through its own server, with an ID token)."""

from datetime import date

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from . import demo
from .approvals import CallLog, Decision, DecisionError, HistoryItem, Status, approvers, store
from .models import CheckResult, Channel, Contact, Payment, Tier
from .pipeline import CheckResponse, run_check

router = APIRouter()


class PaymentSummary(BaseModel):
    id: str
    payee_name: str
    amount: int
    requested_on: date
    channel: Channel
    status: Status
    findings: int | None


class OriginalInfo(BaseModel):
    name: str
    mime_type: str
    text: str | None


class PaymentDetail(BaseModel):
    payment: Payment
    vendor_name: str | None
    channel: Channel
    originals: list[OriginalInfo]
    status: Status
    findings: list[str] | None
    tier: Tier | None
    verify_with: Contact | None
    call: CallLog | None
    approvers: list[str]
    history: list[HistoryItem]


class CheckRequest(BaseModel):
    payment_id: str


class CallRequest(BaseModel):
    by: str
    confirmed: bool


class DecisionRequest(BaseModel):
    decision: Decision
    approver: str | None = None  # the second approver, for a payment that needed a call


def _scenario(payment_id: str) -> demo.Scenario:
    try:
        return demo.scenario_for(payment_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown payment") from None


def _detail(scenario: demo.Scenario) -> PaymentDetail:
    item = store.get(scenario.payment.id)
    vendor = next((v for v in demo.ledger().vendors if v.id == scenario.payment.vendor_id), None)
    return PaymentDetail(
        payment=scenario.payment,
        vendor_name=vendor.name if vendor else None,
        channel=scenario.instruction.channel,
        originals=[
            OriginalInfo(name=o.name, mime_type=o.mime_type, text=o.text if o.is_text else None)
            for o in demo.originals(scenario)
        ],
        status=item.status,
        findings=item.findings,
        tier=item.tier,
        verify_with=item.verify_with,
        call=item.call,
        approvers=approvers(),
        history=item.history,
    )


@router.get("/demo/payments")
def list_payments() -> list[PaymentSummary]:
    out = []
    for s in demo.scenarios():
        item = store.get(s.payment.id)
        out.append(
            PaymentSummary(
                id=s.payment.id,
                payee_name=s.payment.payee_name,
                amount=s.payment.amount,
                requested_on=s.payment.requested_on,
                channel=s.instruction.channel,
                status=item.status,
                findings=None if item.findings is None else len(item.findings),
            )
        )
    return out


@router.get("/demo/payments/{payment_id}")
def get_payment(payment_id: str) -> PaymentDetail:
    return _detail(_scenario(payment_id))


@router.get("/demo/originals/{name}")
def get_original(name: str) -> Response:
    for s in demo.scenarios():
        for o in demo.originals(s):
            if o.name == name:
                return Response(content=o.data, media_type=o.mime_type, headers={"Cache-Control": "private, max-age=300"})
    raise HTTPException(status_code=404, detail="unknown original")


@router.post("/check")
async def check_payment(req: CheckRequest) -> CheckResponse:
    _scenario(req.payment_id)
    response = await run_check(req.payment_id)
    store.checked(req.payment_id, CheckResult(findings=response.findings, verify_with=response.verify_with))
    return response


@router.post("/demo/payments/{payment_id}/call")
def log_call(payment_id: str, req: CallRequest) -> PaymentDetail:
    scenario = _scenario(payment_id)
    try:
        store.log_call(payment_id, req.by, req.confirmed)
    except DecisionError as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    return _detail(scenario)


@router.post("/demo/payments/{payment_id}/decision")
def decide(payment_id: str, req: DecisionRequest) -> PaymentDetail:
    scenario = _scenario(payment_id)
    try:
        store.decide(payment_id, req.decision, req.approver)
    except DecisionError as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    return _detail(scenario)


@router.post("/demo/reset")
def reset() -> dict[str, str]:
    store.reset()
    return {"status": "ok"}
