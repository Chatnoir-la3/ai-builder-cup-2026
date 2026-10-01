# AI Builder Cup 2026 — prototype

Built for the Google Cloud AI Builder Cup 2026 (BFSI theme). The problem statement is not fixed yet; this repository currently holds the deployable skeleton.

## Architecture

```
Browser ──► web (Next.js, Cloud Run, public)
              │  ID token (service-to-service)
              ▼
            agent (Python, ADK, Cloud Run, private) ──► Gemini on Agent Platform (Vertex AI)
```

| Layer | Choice |
|---|---|
| Model | Gemini 3.8 Flash via Gemini Enterprise Agent Platform |
| Agent framework | Agent Development Kit (ADK) 2.x, FastAPI server |
| Frontend | Next.js 16 (App Router), Tailwind CSS |
| Hosting | Cloud Run (`asia-southeast1`) |

## Local development

```bash
# agent (needs `gcloud auth application-default login`)
cd agent
cp .env.example app/.env   # set GOOGLE_CLOUD_PROJECT
uv sync
uv run python main.py      # http://127.0.0.1:8080, or `uv run adk web` for the dev UI

# web
cd web
npm install
npm run dev                # http://localhost:3000, talks to AGENT_URL (default http://127.0.0.1:8080)
```

Tests: `cd agent && PYTHONPATH=. uv run pytest`, `cd web && npm run lint && npm run build`.

## Deploy

```bash
PROJECT_ID=<id> BILLING_ACCOUNT=<id> infra/bootstrap.sh   # once
PROJECT_ID=<id> infra/check-model.sh global                # model smoke test
PROJECT_ID=<id> infra/deploy.sh                            # agent + web
```
