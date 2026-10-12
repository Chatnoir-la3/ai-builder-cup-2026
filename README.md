# Payment instruction check

Built for the Google Cloud AI Builder Cup 2026, BFSI theme.

Just before a company approves a bank transfer, this app compares the instruction (an email, a chat screenshot, an invoice) with the company's own records. When nothing differs, it stays quiet. When something differs, it tells the approver what differs and whom to call, and the company's rules decide what must happen before the money can leave.

**Live demo:** https://web-188931464687.asia-southeast1.run.app

> All companies, people and banks in the demo data are fictional. Email domains use the reserved `.example` domain.

## The problem

Payment fraud against companies rarely breaks into a bank account. It persuades an employee to send a transfer that the bank sees as normal: the right person, logged in, approving it.

- 79% of organizations were targets of attempted or actual payments fraud in 2024, and business email compromise was the most common avenue (63%). Only 22% recovered three quarters or more of the money. ([AFP Payments Fraud and Control Survey 2025](https://www.financialprofessionals.org/about/learn-more/press-releases/Details/survey-79-percent-of-organizations-were-victims-of-attempted-or-actual-payments-fraud-activity-in-2024))
- In Australia, payment redirection scams, in which a fraudster poses as a supplier and changes the account, cost A$166.8M in 2025. ([National Anti-Scam Centre, Targeting Scams Report 2025](https://www.nasc.gov.au/system/files/targeting-scams-report-2025.pdf))
- In Japan, the Tokyo Metropolitan Police warned in January 2026 of emails that pose as the CEO, ask staff to set up a LINE group, and then ask for a transfer right away. There are no official counts. ([INTERNET Watch](https://internet.watch.impress.co.jp/docs/news/2082376.html))

A bank's fraud screening sees only the transfer. The facts that expose these frauds are on the company's side: the supplier's registered account, its usual amounts, the domain it writes from, and a phone number that did not come from the message. This app checks the instruction against those facts at the moment of approval.

## Try it

Open the [live demo](https://web-188931464687.asia-southeast1.run.app). The approval queue holds four payments. Open one and the check runs, usually in a few seconds.

| Payment | What arrives | Result |
|---|---|---|
| P-1001 | A monthly invoice from a regular supplier | **Pass.** Nothing is shown; approve as usual. |
| P-1002 | The supplier says its account is frozen during a tax audit and gives a new one | **Verify.** The screen marks the account, the holder name and the look-alike domain, and gives the ledger's phone number. |
| P-1003 | The CEO, by email, moves the conversation to LINE and asks for an urgent transfer | **Verify.** Call the CEO on the number in the ledger. |
| P-1004 | A regular invoice whose portal link Google Web Risk lists as phishing | **Block.** Approve is disabled. |

For a Verify payment, choose who is calling, record whether the payee confirmed, then choose a second approver who is not the caller. Approve stays disabled until all three are done. An approved payment is added to the ledger's history, and a confirmed account counts as known from then on.

- **How it works** walks each scenario through the approval flow.
- **Evaluation** runs 28 cases through the same rules and explains each result.
- **Reset demo** on the queue page puts everything back.

## How it works

![Approval flow](docs/flow.svg)

- **Gemini reads, code decides.** The reader turns the originals into fields with evidence quotes and image boxes. Plain code checks that reading against the originals and compares it with the ledger: unregistered or recently added accounts, holder name mismatch, amounts above history, look-alike or unregistered sender domains, unusual channels. Wording such as "urgent" is not a signal, since it is the easiest thing for a fraudster to change.
- **Lookups add what the ledger cannot know.** Google Web Risk checks the links in the instruction, and RDAP gives the sender domain's age. For a new payee with nobody in the ledger to call, the finder asks Gemini with Google Search for the payee's official number. Gemini is given the payee's name only, never the instruction. Code uses the number only if a grounded page shows it with the payee's name, the page is not on the sender's domain, and the number is not in the instruction.
- **Gemini explains, code checks.** The explainer sees the findings only, never the originals. Its notice is shown only if it covers exactly those findings, quotes no number outside them, and gives the number to call from the ledger or the finder. Otherwise a fixed template is used.
- **The company's rules decide, and code enforces them.**

| Tier | When | What the approver must do |
|---|---|---|
| Pass | Nothing differs from the ledger | Approve as usual |
| Verify | Something differs, and there is an independent number to call | Call that number, record the answer, and have a second person approve |
| Block | Web Risk lists a link, or there is no independent number to call | Cannot be approved |

## Evaluation

28 cases, 18 attacks and 10 genuine payments, run through the same rules as the approval queue. They are in [`agent/app/payguard/evalset.py`](agent/app/payguard/evalset.py) and on the app's **Evaluation** page, where each case shows its findings and why it was stopped.

| | Ledger alone | With lookups |
|---|---|---|
| Attacks stopped (not approved as usual) | 18 / 18 | 18 / 18 |
| Attacks that cannot be approved at all | 4 | 4 |
| Genuine payments wrongly blocked | 2 / 10 | **0 / 10** |
| Genuine payments that need a call | 4 / 10 | 6 / 10 |
| Genuine payments approved as usual | 4 / 10 | 4 / 10 |

The ledger rules alone stop every attack. The lookups matter for genuine new suppliers: without an official number to call, a real first payment cannot be approved. In the evaluation, the lookup results are given per case, so the outcome depends on the rules alone and can be repeated. All 28 cases give the expected findings and tier, and the tests check this.

Known limits:

- With one person in accounts payable, there is no second approver. The check still flags the payment (case A17).
- The company registry lookup is designed and its rules are in place, but it is not connected: Japan's corporate number API needs an application ID. The demo leaves it out.
- The reader can misread an original. Fields it cannot match to the original are shown as "Not confirmed in the original".

## Architecture

![Architecture](docs/architecture.svg)

The agent runs one ADK `Workflow` per check (`POST /check {"payment_id": ...}`):

```
START ─► reader (Gemini) ─► check (code) ─┬─ "explain" ─► explainer (Gemini)
                                          └─ "quiet" ───► end (routine payments: one model call)
```

![Technology](docs/stack.svg)

Data handling:

- Originals are read for the check and are not stored by it.
- Audit rows in BigQuery keep metadata only, with all content redacted.
- Decision logs record the tier, the finding codes and the call outcome, not names or account numbers.
- Model Armor and the audit plugin turn on only when `MODEL_ARMOR_TEMPLATE` and `AUDIT_DATASET` are set, so local development needs neither.

## Running it for real

- **Where it sits.** At the approval step: inside the AP workflow of accounting software, or before approval in corporate internet banking. Both call one endpoint, `POST /check`, with the payment and its instruction.
- **The ledger.** It comes from the vendor master and payment history the company already keeps, and it grows by rule. An approval adds the payment to the history, and a confirmed call marks the account as verified.
- **Scale.** The agent is stateless on Cloud Run and scales with requests. A routine payment costs one model call. The ledger and the approval queue are in Firestore.
- **Data residency.** The default model runs on `global`. If data must stay in the region, switch to `gemini-3.5-flash` in `asia-southeast1` (see below).
- **What the demo leaves out.** Sign-in and per-company tenants, the company registry lookup, and integration with a real accounting system or bank.

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

Tests: `cd agent && PYTHONPATH=. uv run pytest`, `cd web && npm run lint && npm test && npm run build`.

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

The default is `gemini-3.8-flash` on `global`. If data must stay in the region, switch to `gemini-3.5-flash` with `MODEL_LOCATION=asia-southeast1`.

## Deploy

CI (`.github/workflows/ci.yml`) tests every PR and deploys `main` to Cloud Run using keyless Workload Identity Federation (`infra/bootstrap-ci.sh`, run once).

Manual:

```bash
PROJECT_ID=<id> BILLING_ACCOUNT=<id> infra/bootstrap.sh   # once: project, APIs, service accounts, budget
PROJECT_ID=<id> infra/bootstrap-platform.sh                # once: Model Armor template, audit dataset, Firestore, Web Risk
PROJECT_ID=<id> GITHUB_REPO=<owner/repo> infra/bootstrap-ci.sh  # once: keyless CI deploy
PROJECT_ID=<id> infra/check-model.sh global                # model smoke test
PROJECT_ID=<id> infra/deploy.sh                            # agent + web
```
