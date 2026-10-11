import os

import uvicorn
from fastapi import HTTPException
from google.adk.cli.fast_api import get_fast_api_app
from pydantic import BaseModel

from app.payguard.pipeline import CheckResponse, run_check

AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))
ALLOW_ORIGINS = [o for o in os.getenv("ALLOW_ORIGINS", "").split(",") if o]

app = get_fast_api_app(
    agents_dir=AGENTS_DIR,
    allow_origins=ALLOW_ORIGINS or None,
    web=os.getenv("ADK_WEB_UI", "false").lower() == "true",
    auto_create_session=True,
)


@app.get("/health")  # Cloud Run reserves paths ending in "z"
def health() -> dict[str, str]:
    return {"status": "ok"}


class CheckRequest(BaseModel):
    payment_id: str


@app.post("/check")
async def check_payment(req: CheckRequest) -> CheckResponse:
    try:
        return await run_check(req.payment_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown payment") from None


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
