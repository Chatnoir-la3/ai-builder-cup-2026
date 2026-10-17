"""Check results, kept so a payment opened again shows its check at once instead of asking Gemini again.

A result is reused only for the same payment, ledger and deployed revision: an approval changes the
ledger and a deploy may change the rules, and either runs the check again. A reset returns to the demo
ledger, so the checks stored for it are used again. A check that failed is not stored.
"""

import hashlib
import os

from . import ledger
from .pipeline import CheckResponse
from .storage import CHECKS, backend


def key(payment_id: str) -> str:
    revision = os.environ.get("K_REVISION", "local")  # set by Cloud Run for each deploy
    digest = hashlib.sha256(f"{revision}\n{ledger.current().model_dump_json()}".encode()).hexdigest()[:32]
    return f"{payment_id}-{digest}"


def get(key: str) -> CheckResponse | None:
    raw = backend().get(CHECKS, key)
    return CheckResponse.model_validate(raw) if raw else None


def put(key: str, response: CheckResponse) -> None:
    backend().put(CHECKS, key, response.model_dump(mode="json"))
