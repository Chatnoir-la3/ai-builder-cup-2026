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
| Guardrail | Model Armor (prompt injection / jailbreak, responsible-AI filters) via ADK `ModelArmorPlugin` |
| Audit trail | BigQuery (`agent_audit.agent_events`) via ADK `BigQueryAgentAnalyticsPlugin` |
| CI/CD | GitHub Actions + Workload Identity Federation (no service-account keys) |

Guardrail and audit plugins turn on only when `MODEL_ARMOR_TEMPLATE` / `AUDIT_DATASET` are set, so local dev needs neither.

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

## Model availability (checked 2026-10-02)

| Model | `global` | `asia-southeast1` / `asia-northeast1` |
|---|---|---|
| gemini-3.8-flash, gemini-3.5-flash-lite, gemini-3.1-flash-lite, gemini-3.1-pro-preview | yes | no |
| gemini-3.5-flash | yes | yes |
| gemini-embedding-001, text-embedding-005, text-multilingual-embedding-002 | yes | yes (SG checked) |

Default is `gemini-3.8-flash` on `global`. If data must stay in-region, switch to `gemini-3.5-flash` with `MODEL_LOCATION=asia-southeast1`.

## Deploy

CI (`.github/workflows/ci.yml`) tests every PR and deploys `main` to Cloud Run using keyless Workload Identity Federation (`infra/bootstrap-ci.sh`, run once).

Manual:

```bash
PROJECT_ID=<id> BILLING_ACCOUNT=<id> infra/bootstrap.sh   # once: project, APIs, service accounts, budget
PROJECT_ID=<id> infra/bootstrap-platform.sh                # once: Model Armor template, audit dataset
PROJECT_ID=<id> GITHUB_REPO=<owner/repo> infra/bootstrap-ci.sh  # once: keyless CI deploy
PROJECT_ID=<id> infra/check-model.sh global                # model smoke test
PROJECT_ID=<id> infra/deploy.sh                            # agent + web
```
