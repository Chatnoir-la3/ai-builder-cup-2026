import os

import uvicorn
from google.adk.cli.fast_api import get_fast_api_app

AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))
ALLOW_ORIGINS = [o for o in os.getenv("ALLOW_ORIGINS", "").split(",") if o]

app = get_fast_api_app(
    agents_dir=AGENTS_DIR,
    allow_origins=ALLOW_ORIGINS or None,
    web=os.getenv("ADK_WEB_UI", "false").lower() == "true",
    auto_create_session=True,
)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
