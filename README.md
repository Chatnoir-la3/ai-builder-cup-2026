# AI Builder Cup 2026 — prototype

Built for the Google Cloud AI Builder Cup 2026 (BFSI theme).

**Payment instruction check.** Just before a company approves a bank transfer, it compares the instruction (an email, a chat screenshot, an invoice) with the company's own records and, only when something differs from the usual pattern, tells the approver what to check and whom to call. It targets impersonation: a supplier whose account is "frozen during a tax audit", or a CEO who moves the conversation to LINE and asks for an urgent transfer.

> All companies, people and banks in the demo data are fictional. Email domains use the reserved `.example` domain.

- **Gemini reads, code decides.** The reader turns the originals into fields with evidence quotes and image boxes. Plain code grounds that reading against the originals and compares it with the ledger: unregistered or recently added accounts, holder name mismatch, amounts above history, lookalike or unregistered sender domains, unusual channels. Wording such as "urgent" is not a signal, since it is the easiest thing for a fraudster to change.
- **Gemini explains, code checks.** The explainer sees the findings only, never the originals. Its notice is shown only if it covers exactly those findings, quotes no number outside them and gives the callback number from the ledger; otherwise a fixed template is used.
- **People decide.** Nothing blocks the payment. The callback contact always comes from the ledger, never from the message. Originals are not stored, and audit rows keep metadata only.

All companies, banks and domains in the demo data are fictional.

## Architecture

```
Browser ──► web (Next.js, Cloud Run, public)
              │  ID token (service-to-service)
              ▼
            agent (Python, ADK, Cloud Run, private) ──► Gemini on Agent Platform (Vertex AI)
```

The agent runs one ADK `Workflow` per check (`POST /check {"payment_id": ...}`):

```
START ─► reader (Gemini) ─► check (code) ─┬─ "explain" ─► explainer (Gemini)
                                          └─ "quiet" ───► end (routine payments: one model call)
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

Guardrail and audit plugins turn on only when `MODEL_ARMOR_TEMPLATE` / `AUDIT_DATASET` are set, so local dev needs neither. Audit rows redact all content.

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

Tests that call Gemini are skipped by default. To run them (needs application default credentials):

```bash
cd agent
GOOGLE_GENAI_USE_VERTEXAI=TRUE GOOGLE_CLOUD_PROJECT=<id> GOOGLE_CLOUD_LOCATION=global \
  RUN_LIVE_GEMINI=1 PYTHONPATH=. uv run pytest tests/test_payguard_reader_live.py tests/test_payguard_pipeline_live.py
```

The synthetic image originals are rendered from HTML with `tools/render-originals.sh`.

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
