[English](README.md) | [简体中文](README.zh-CN.md)

# AI-Assisted Email Triage & Human Review

**A human-in-the-loop workflow that turns a crowded sales or support inbox into organized,
reviewed reply drafts — without letting AI talk to customers on its own.**

In the reference workflow, emails arrive through n8n, are registered and deduplicated by FastAPI,
screened by deterministic risk rules, classified by an AI provider, and turned into drafts that
wait in a human review queue.
A reviewer can approve, reject, or take over each task. This is the part many AI inbox demos skip:
the human decision is a first-class state, not an afterthought.

> **Portfolio Demo, not production software.**
> The default `AI_PROVIDER=mock` is offline and deterministic: running this project does **not**
> call an external AI service. The optional DeepSeek provider is disabled by default.
> There is no email-sending capability at all — `approved` means a human approved the draft,
> not that an email was sent.

| Project snapshot | |
| --- | --- |
| **What it is** | AI-assisted email triage and human review workflow |
| **Stage** | Portfolio Demo — not production-ready |
| **AI by default** | Offline Mock provider; no automatic external AI calls |
| **Email sending** | Not implemented; no emails are sent automatically or manually |
| **Stack** | n8n · FastAPI · PostgreSQL · Streamlit |
| **Verification** | 257 passed · 1 warning · 0 failed · 0 skipped (isolated run) |
| **中文文档** | [简体中文详细技术文档](README.zh-CN.md) |

---

## The problem

A sales or support inbox is not one kind of work. It is product questions, pricing requests,
order changes, refunds, complaints, and occasional legal threats — all arriving in the same queue,
all expecting a fast answer.

Reading and sorting every message by hand is slow and easy to get wrong. Letting a language model
reply automatically is faster, but it is exactly the wrong trade for refunds, complaints, and
legal language. The expensive mistakes are not typos; they are commitments made without context.

This project takes the middle path:

1. **Automate the repetitive work** — retrieval, normalization, deduplication, classification,
   summarization, and draft generation.
2. **Never automate the judgment** — every customer-facing draft stops at a human review gate.
3. **Make risky messages skip the model entirely** — deterministic rules send refunds, complaints,
   legal language, order changes, and account/payment changes straight to human takeover.

## Core capabilities

- **Deduplicated email registration.** `mailbox_id + message_id` is a database-level unique key.
  A first submission returns `201` with `status=received`; a duplicate returns `200` with
  `duplicate=true` and the existing task instead of creating another one. This is registration-level
  deduplication, not an exactly-once guarantee for later processing.
- **Risk rules before AI.** Keyword rules for legal/complaint/compensation, refund/chargeback,
  order changes, and payment/account changes run first. A match goes to `human_takeover` without
  calling the AI provider. Empty bodies also require immediate human handling.
- **Pluggable AI provider.** The default `MockAIProvider` is deterministic and offline. The optional
  `DeepSeekProvider` is selected only through explicit configuration, and its output is validated
  against a strict schema. `requires_human` is forced to `true` by the application.
- **A real review state machine.** `approve`, `reject`, and `takeover` are only accepted for
  `awaiting_review` tasks. `approve` requires a non-empty draft; reviewers can save an edited
  `draft_body` as part of the review.
- **Two reference review interfaces.** A minimal same-origin page at `/ui`, and a bilingual
  Streamlit inbox (`frontend_app.py`) with an English / 中文 switch, pending list, detail view,
  editable draft, and review buttons.
- **A reproducible local demo.** PostgreSQL, FastAPI, and Streamlit run in an isolated Compose
  project with an offline Mock provider and no real email, n8n, or AI credentials.

---

## Architecture

```mermaid
flowchart TD
    A["Customer email<br/>(synthetic test mail)"] --> B["n8n Schedule Trigger"]
    B --> C["IMAP node"]
    C --> D["Code node<br/>clean + field mapping"]
    D --> E["FastAPI<br/>POST /api/v1/emails"]
    E --> F{"Duplicate / status route"}
    F -->|"new: received"| G["POST /api/v1/emails/{task_id}/process"]
    F -->|"existing task"| H["GET /api/v1/emails/{task_id}"]
    G --> I{"Deterministic risk rules"}
    I -->|"match"| J["human_takeover"]
    I -->|"no match"| K["AI provider<br/>Mock default / DeepSeek optional"]
    K --> L{"Valid result + draft?"}
    L -->|"normal email, valid draft"| M["awaiting_review"]
    L -->|"high risk / no usable draft"| J
    M --> N["Human reviewer<br/>approve / reject / takeover"]
    E --- P[("PostgreSQL<br/>tasks + unique dedupe key")]
    G --- P
    H --- P
    N --- P
```

### Who does what

| Layer | Responsibility | Why it is separate |
| --- | --- | --- |
| **n8n** | Scheduled trigger, IMAP retrieval, field cleaning, and routing to the API. | Inbox-specific orchestration stays outside the business API and can be swapped for another ingestion adapter. |
| **FastAPI** | Registration, deduplication, risk rules, triage orchestration, state machine, review persistence. | Owns the business rules and the audit-relevant state transitions. |
| **PostgreSQL** | Durable task state and the unique `(mailbox_id, message_id)` constraint. | Deduplication is enforced by the database, not by a best-effort application check. |
| **Streamlit** | The reviewer console: pending list, task detail, editable draft, approve/reject/takeover, English/中文 UI. | A reference client for the JSON API; it can be replaced by any existing frontend. |
| **AI provider** (inside FastAPI) | Classification, summary, risk explanation, and draft generation. | The vendor is a configuration detail; Mock remains the default and the offline baseline. |

The repository also contains a minimal same-origin review page at `/ui` and interactive API
documentation at `/docs`. The review page is a reference implementation, not a production frontend;
the API documentation is generated from the live schema.

## Human-in-the-loop by design

```text
received → processing → awaiting_review → approved / rejected / human_takeover
                     ↘ human_takeover / failed
```

- **Rules first.** Legal/complaint/compensation > refund/chargeback > order change >
  payment/account change. A rule hit goes to `human_takeover`; the AI provider is not called.
- **AI second.** Only messages that pass the rule gate reach the provider. A non-high-risk result
  with a non-empty draft becomes `awaiting_review`; high-risk categories or an unusable draft go to
  `human_takeover`.
- **Human last — and always.** The reviewer can approve, reject, or take over. `approve` requires
  a non-empty draft; an edited draft can be saved with the decision.
- **Failures are visible.** Provider or output-validation failures mark the task `failed` instead of
  producing a silent fallback. A duplicate `process` call on `awaiting_review` returns the existing
  result; `processing` and terminal states return `409`.
- **Approval is not delivery.** There is no `sent` or `sending` state and no SMTP/API sending path.
  `approved` is strictly a human review outcome.
- **Reviewer identity is demo-only.** `reviewed_by` is a required client-supplied string, not an
  authenticated identity. Production authentication is not implemented.

## Reproducible Docker demo

The demo runs PostgreSQL 16, FastAPI, and Streamlit in a dedicated Compose project named
`ai-support-demo`. It is intentionally isolated from the existing development database and n8n
services:

- its own database and volume (`ai-support-demo_demo_pgdata`);
- synthetic messages only;
- `AI_PROVIDER=mock`, with no DeepSeek key and no outbound AI calls;
- no n8n service, no real IMAP import, and no email sending;
- the database is not published to the host;
- no production authentication.

### Build and start

```bash
# Build images using the default PyPI index.
docker compose -p ai-support-demo -f docker-compose.demo.yml build

# Start the demo. The database stays internal to the Compose network.
docker compose -p ai-support-demo -f docker-compose.demo.yml up -d --no-build

# Check container health.
docker compose -p ai-support-demo -f docker-compose.demo.yml ps
```

The first build needs access to Docker Hub (`python:3.12-slim`) and a Python package index. Starting
the demo also pulls `postgres:16-alpine`.

### What you get

| Service | Address |
| --- | --- |
| FastAPI | http://127.0.0.1:8020 |
| OpenAPI docs | http://127.0.0.1:8020/docs |
| API health | http://127.0.0.1:8020/health |
| Streamlit review inbox | http://127.0.0.1:8503 |
| PostgreSQL | internal only (`demo-db:5432`) |

### Try one synthetic email

```bash
CREATE_RESPONSE=$(curl -sS -X POST http://127.0.0.1:8020/api/v1/emails \
  -H 'Content-Type: application/json' \
  -d '{"mailbox_id":"demo@example.com","message_id":"<quickstart-001@example.com>","subject":"Product feature question","body":"This is a synthetic demo message. What features are available?"}')

TASK_ID=$(printf '%s' "$CREATE_RESPONSE" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
echo "task_id=$TASK_ID"

curl -sS -X POST "http://127.0.0.1:8020/api/v1/emails/$TASK_ID/process"
```

The process response should return `status: "awaiting_review"` for this synthetic product question.
Open the Streamlit inbox and select the task under **Pending Review**. This walkthrough does not
submit a review, send email, import real IMAP mail, or call DeepSeek/n8n.

### Stop

```bash
docker compose -p ai-support-demo -f docker-compose.demo.yml down
```

This keeps the demo volume. Do not add `-v` unless you intend to delete the demo database, and do
not run this Compose project against the existing `ai-support-workflow` services.

### Troubleshooting

- **Port already in use:** change the host side of `8020` or `8503` in `docker-compose.demo.yml`;
  do not stop the existing service.
- **API container exits:** inspect
  `docker compose -p ai-support-demo -f docker-compose.demo.yml logs demo-api`. Migration failures
  stop the API by design.
- **Streamlit shows no tasks:** verify `API_BASE_URL=http://demo-api:8000` and that `demo-api` is
  healthy.
- **No AI key is needed:** the demo hard-codes `AI_PROVIDER=mock`, does not read the host `.env`,
  and does not receive `DEEPSEEK_API_KEY`.
- **PyPI is slow or unreachable (optional):** rebuild with an alternate index. The default command
  above uses the standard PyPI index; this override is only a network workaround.

  ```bash
  docker compose -p ai-support-demo -f docker-compose.demo.yml build \
    --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
  ```

- **Docker Hub is unreachable:** pull the same `python:3.12-slim` and `postgres:16-alpine` images
  from a reachable registry, tag them with the same names, then rebuild or start the demo.

## Verified results

| Scenario | Observed result |
| --- | --- |
| New synthetic product question | Reaches `awaiting_review` with a generated draft |
| Synthetic refund email | Risk rule matches, task becomes `human_takeover`, provider is not called |
| Historical / duplicate email | Registration returns `duplicate=true`; workflow uses the existing-task `GET` branch |
| Real mailbox read | n8n read 7 test emails from a dedicated 163 mailbox, including historical and new mail |
| Isolated full test run | **257 passed, 1 warning, 0 failed, 0 skipped** |
| DeepSeek synthetic validation (limited) | Ordinary inquiry and English pricing inquiry reached `awaiting_review`; category, risk level, summary, risk reason, and draft persisted |

The mailbox and DeepSeek rows above come from earlier limited end-to-end integrations; the isolated
test row is the pytest run described below.

### Isolated test run

The full pytest suite was executed against an isolated PostgreSQL container with
`AI_PROVIDER=mock` and a dedicated internal Docker network:

- **257 passed**
- **1 warning** — a Starlette/httpx deprecation notice
- **0 failed**
- **0 skipped**

The run used a temporary test copy and a separate `ai_support_test` database. It did not use the
existing `ai_support`, the existing `ai_support_test`, or the demo's `ai_support_demo` database.
The test container had no host `.env` mounted and no DeepSeek key, and outbound internet access was
blocked by the internal network. No real DeepSeek, n8n, or mailbox calls were made, and no browser
review submission was performed.

These results show that this isolated run passed. They do not demonstrate production stability,
cross-machine cold starts, multi-replica migrations, or full browser E2E coverage.

### DeepSeek validation scope

The DeepSeek provider was exercised with a small number of **synthetic** emails:

- a normal inquiry moved from `received` to `awaiting_review`;
- an English pricing inquiry produced English `summary`, `risk_reason`, and `draft_body` fields;
- the pricing draft asked for product version, purchase quantity, usage scale, and deployment model,
  without quoting price, stock, discount, delivery time, or assigned staff;
- `requires_human` remained `true`, and the task still required review.

**What these results prove:** the core flow works end-to-end in the tested scenarios, the offline
demo is reproducible, and the isolated suite passes. **What they do not prove:** production
stability, cross-machine cold starts, multi-replica migrations, full browser E2E coverage,
multi-language quality at scale, or production readiness. The DeepSeek results cover only limited
synthetic samples; latency, cost, and output quality at larger volume are not characterized.

## Current limitations

### Production readiness

- **No production-grade authentication or authorization** on the API, `/ui`, or Streamlit.
  `reviewed_by` is a self-reported demo value, not a verified identity.
- **No real email sending.** There is no SMTP client, no provider send API, and no `sent` or
  `sending` state. `approved` means human approval only.
- **No pagination and no multi-tenancy.** `GET /api/v1/emails` returns all tasks; status filtering
  happens in the client. The schema has no tenant field, so the demo must not be shared across
  customers or exposed as a multi-tenant service.
- **No production stability claim.** The app has no automatic retry, no `processing` timeout
  recovery, and no exactly-once guarantee. A database failure can leave task state uncertain (the
  API returns `503`).
- `/health` only confirms that the API process responds; it does not check database readiness.

### AI behavior

- The default Mock provider is keyword-based and deterministic. It demonstrates the pipeline and
  serves as the offline regression baseline, not a real model.
- **DeepSeek was validated only on a limited number of synthetic emails.** There is no systematic
  evaluation of quality, latency, cost, or failure behavior at scale. It is not
  production-validated.
- When DeepSeek is explicitly enabled, the email subject and body are sent to a third-party model.
  Use synthetic or redacted data only.
- Risk rules are exact keyword rules. They can miss synonyms, misspellings, and other languages, or
  match the wrong context. A rule miss does not mean an email is safe; every draft still needs
  review.

### Ingestion and data

- **The real IMAP workflow is configured in the n8n UI, not in this repository.** There is no
  verified IMAP workflow export here. `n8n/workflows/06_test_webhook_triage.json` is an early test
  Webhook draft, not the production IMAP flow.
- The real-mailbox validation used a dedicated 163 test mailbox and synthetic messages. It is a
  demo, not evidence of production mailbox compatibility or stability.
- The data model has no sender, recipient, attachment, thread, or draft-history fields. There is no
  sender filter and no draft revision history.
- The Streamlit UI supports list, detail, draft editing, and review. It does not have pagination,
  advanced filtering, or reviewer authentication.
- Dependency versions are range-pinned, not locked. Builds may drift over time.
- The demo API runs `alembic upgrade head` at startup as a single-instance simplification. It is
  not a multi-replica migration strategy.
- Slack integration is not implemented.

## Integrating with an existing frontend

FastAPI is the system of record and is UI-agnostic. Streamlit is a reference client that talks to
the same JSON API, so an existing React, Vue, server-rendered, or desktop frontend can replace it
without changing the backend.

### 1. Point your frontend at the API

Set your frontend's API base URL to the FastAPI service (for example `http://127.0.0.1:8020` in the
demo, or your own host). Interactive API documentation is available at `/docs`; the OpenAPI schema
is at `/openapi.json`.

### 2. Build the review screen on these endpoints

| Method and path | Use in your UI |
| --- | --- |
| `GET /api/v1/emails` | Inbox list: id, status, summary, risk level, ordered by last update. Filter to `awaiting_review` in your client. |
| `GET /api/v1/emails/{id}` | Detail: original subject/body, category, risk, draft, review fields, timestamps. |
| `POST /api/v1/emails/{id}/review` | Submit `approve`, `reject`, or `takeover`, optionally with an edited `draft_body`. |
| `POST /api/v1/emails` | Ingest a message from your own mail adapter (n8n or anything else). |
| `POST /api/v1/emails/{id}/process` | Run rules and AI triage for a newly registered task. |

Example review submission:

```json
{
  "action": "approve",
  "reviewed_by": "reviewer@your-company.example",
  "review_comment": "Checked the wording; no price or delivery commitment.",
  "draft_body": "Hi Alex, thanks for reaching out. ..."
}
```

`draft_body` is optional; when omitted, the stored draft is kept. `reviewed_by` is required by the
schema but is self-reported. In your integration, populate it from your authenticated session and
enforce authorization in your own gateway.

### 3. Handle state and errors explicitly

- Only `awaiting_review` tasks can be reviewed. `approve` fails with `409` if there is no non-empty
  draft.
- `process` only starts new work for `received`; a repeated call on `awaiting_review` returns the
  existing result (`200`), while `processing` and terminal states return `409`.
- Provider failure returns `502` and marks the task `failed`; database failure returns `503` with
  possibly uncertain state. Do not silently retry either case.
- Registration is deduplicated by `mailbox_id + message_id`; use the returned `duplicate` flag to
  avoid re-processing historical mail.
- Display `approved` as **Approved (not sent)** or **Review complete**, never as **Sent**.

### 4. Account for the demo's boundaries

- **CORS is not configured** in this repository. If your frontend runs on a different origin, serve
  the API and UI behind the same reverse proxy, or add CORS middleware in your own deployment.
- **Add authentication before exposure.** The repository has no auth layer; put the API behind your
  SSO, API gateway, or reverse proxy and restrict network access.
- **Add pagination and tenant scoping** before using this with a real, growing inbox or multiple
  customers. The current list endpoint returns everything and the schema has no tenant field.
- **Keep the human gate.** If you later add sending (not implemented here), make the send action a
  separate, explicitly authorized step and record its own idempotency key.

If you want to replace n8n, implement a small adapter that calls `POST /api/v1/emails` with exactly
`mailbox_id`, `message_id`, `subject`, and `body`, then calls `process` for new tasks. Your adapter
is responsible for mail retrieval, retries, and scheduling; the API deliberately does not contain
IMAP credentials or mailbox polling.

## Configuration

| Variable | Default | Notes |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+psycopg://demo:demo@localhost:5432/ai_support` | psycopg 3 DSN; override for your own database. |
| `AI_PROVIDER` | `mock` | `mock` is offline and deterministic; `deepseek` requires a key. |
| `DEEPSEEK_API_KEY` | unset | Only needed when `AI_PROVIDER=deepseek`; never commit it. |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | Must start with `http://` or `https://`. |
| `DEEPSEEK_MODEL` | `deepseek-flash` | Override according to the provider's current documentation. |
| `DEEPSEEK_TIMEOUT_SECONDS` | `30` | Positive number, maximum `120`. |
| `API_BASE_URL` | `http://127.0.0.1:8014` | Used by `frontend_app.py`; the Docker demo sets `http://demo-api:8000`. |

With `AI_PROVIDER=deepseek` and a valid key, email subject and body are sent to the third-party API.
The default configuration never makes that call.

## Run locally with Python

The Docker demo is the recommended path. This section runs the API and Streamlit as local Python
processes instead. Requirements: Python 3.10+, PostgreSQL 16 (the repository's
`docker-compose.yml` can provide the database), and a virtual environment.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # skip if .env exists; demo values only
docker compose up -d db       # PostgreSQL on localhost:5432
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8014
```

In a second shell:

```bash
API_BASE_URL=http://127.0.0.1:8014 streamlit run frontend_app.py
```

The API is then available at http://127.0.0.1:8014 and the review inbox at
http://127.0.0.1:8501.

## Project structure

```text
app/
  api/routes/emails.py       registration, list, detail, process, and review endpoints
  services/rules.py          deterministic risk rules
  services/triage.py         rule gate, provider orchestration, and state transitions
  services/review.py         approve / reject / takeover persistence
  providers/ai/              Mock provider and optional DeepSeek provider
  core/email_status.py       status values and allowed transitions
  db/models.py               EmailTask model and unique dedupe constraint
  static/review.html         minimal same-origin /ui review page
frontend_app.py              bilingual Streamlit review inbox
alembic/                     database migrations
docker-compose.demo.yml      isolated PostgreSQL + FastAPI + Streamlit demo
Dockerfile.api               API image
Dockerfile.ui                Streamlit image
n8n/                         early test workflow draft (not the real IMAP export)
tests/                       API, service, provider, UI, and concurrency tests
```

## Status reference

| Status | Meaning |
| --- | --- |
| `received` | Registered and waiting for processing. |
| `processing` | Risk rules and/or the AI provider are running. |
| `awaiting_review` | A usable draft exists; a human decision is required. |
| `approved` | A human approved the draft. **The email has not been sent.** |
| `rejected` | A human rejected the draft. |
| `human_takeover` | Rule match, high risk, or no usable draft; needs human handling. |
| `failed` | Processing or output validation failed. |

Terminal states are `approved`, `rejected`, `human_takeover`, and `failed`.

## Security notes

- Do not commit `.env`, IMAP authorization codes, or API keys.
- Use a dedicated test mailbox and synthetic messages for any public demo. Never connect a real
  customer inbox to this repository as-is.
- Detail responses return full email bodies and drafts, and the API has no production
  authentication. Treat this data as sensitive and keep the service off the public internet.
- Enabling DeepSeek sends message content to a third party. Use only synthetic or redacted data.
- Risk rules are a triage aid, not a security control. They can miss or misclassify content.
- `reviewed_by` and review comments are not tamper-proof; there is no separate audit log or identity
  verification.

## Roadmap

- **AI validation:** expand synthetic evaluation for quality, latency, cost, and failure modes;
  keep Mock as the offline regression baseline.
- **Review UI:** pagination, status/risk/keyword filters, sender metadata, review history, and
  authenticated reviewer identity.
- **Sending and reliability:** an explicit post-approval send step with its own states, idempotency
  boundaries, error triggers, controlled retries, and alerts.
- **Multi-tenancy:** tenant-scoped data and authorization, which the current schema does not have.

These are plans, not current capabilities.

## Documentation

- [简体中文详细技术文档 (Chinese README)](README.zh-CN.md) — architecture, API contract, IMAP
  integration notes, verification history, and limitations in Chinese.
- [n8n integration notes (Chinese)](docs/n8n-integration.md)
- [n8n workflow draft status (Chinese)](n8n/README.md)
- [Project roadmap (Chinese)](docs/PROJECT_ROADMAP.md)
- [Project walkthrough (Chinese)](docs/项目讲解.md)
- Interactive API reference: run the app and open `/docs`.

---

**Project status:** Portfolio Demo. The workflow demonstrates AI-assisted triage with a mandatory
human review gate; it is not a production email system. `approved` does not mean sent.
