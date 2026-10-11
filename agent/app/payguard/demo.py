"""Demo data: a fictional company's ledger and the payments waiting for approval, with their originals."""

import json
from functools import cache

from pydantic import BaseModel

from . import DATA_DIR
from .models import Instruction, Ledger, Payment
from .reader import Original


class Scenario(BaseModel):
    id: str
    title: str
    originals: list[str]
    payment: Payment
    instruction: Instruction  # what a careful human reads from the originals; used to test the reader


@cache
def ledger() -> Ledger:
    return Ledger.model_validate_json((DATA_DIR / "ledger.json").read_text(encoding="utf-8"))


@cache
def scenarios() -> tuple[Scenario, ...]:
    raw = json.loads((DATA_DIR / "scenarios.json").read_text(encoding="utf-8"))
    return tuple(Scenario.model_validate(s) for s in raw)


def scenario_for(payment_id: str) -> Scenario:
    for s in scenarios():
        if s.payment.id == payment_id:
            return s
    raise KeyError(payment_id)


def originals(scenario: Scenario) -> list[Original]:
    return [Original.from_path(DATA_DIR / "originals" / name) for name in scenario.originals]
