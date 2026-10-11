"""Payment instruction checks: the model reads the original, code compares it with the ledger."""

from pathlib import Path

from .models import CheckResult, Finding, Instruction, Ledger, Payment
from .rules import check

DATA_DIR = Path(__file__).parent / "data"


def load_demo_ledger() -> Ledger:
    return Ledger.model_validate_json((DATA_DIR / "ledger.json").read_text(encoding="utf-8"))


__all__ = ["CheckResult", "Finding", "Instruction", "Ledger", "Payment", "check", "load_demo_ledger"]
