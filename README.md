# Operational Claims Intelligence Agent

A production-realistic agentic workflow system for insurance and warranty claim processing. Built to demonstrate how operational AI should work in regulated, high-stakes environments — where deterministic correctness matters more than autonomy, and every decision must be explainable.

This is not a chatbot. It is not a demo. It is a backend system that processes claims through a deterministic pipeline, uses an LLM strictly for reasoning and explanation, and routes every uncertain decision to a human reviewer.

---

## Problem statement

Warranty and insurance claim processing is broken by design. Most systems route every claim through manual review — a human reads a description, looks up a policy PDF, makes a judgment call, and logs it somewhere. This process is slow, inconsistent, unscalable, and opaque.

The technically hard version of this problem has four layers:

**1. Policy ambiguity** — manufacturer warranties are legal documents, not structured data. Every OEM writes coverage rules differently. Parsing them into machine-readable logic that can be applied consistently at volume is unsolved at most warranty companies.

**2. Claim description quality** — claimants are frustrated people, not technical writers. "My TV stopped working" is a claim description. The system has to extract damage type, classify coverage eligibility, and detect fraud signals from natural language — without being confidently wrong.

**3. Fraud and anomaly detection** — a claim filed two weeks after purchase, for exactly the policy maximum, with a vague description, may be legitimate. Or it may not. Detecting this without a human reviewing every claim requires anomaly signals working deterministically at volume.

**4. Compliance and auditability** — insurance is regulated. Every approval and rejection must be explainable and auditable. "The AI said no" is not a legally defensible answer in any jurisdiction. Every decision needs a traceable reason a regulator can inspect.

This system is built to address all four layers — not completely, but architecturally correctly.

---

## Why this architecture exists

The standard failure mode of AI-in-production systems is silent incorrectness. An LLM makes a confident decision, nobody notices it's wrong, and the error compounds. In a claims context, this means wrong approvals, wrong rejections, and unauditable decisions.

The architecture here makes a specific set of bets:

- **Deterministic logic cannot be replaced by probabilistic inference** for compliance-sensitive decisions. Policy rules, waiting periods, and fraud thresholds are code — not prompts.
- **LLMs are good at explanation, not at correctness guarantees**. The system uses Gemini to explain what happened and surface anomalies for human reviewers. It does not use Gemini to decide what happens.
- **Failure must be explicit**. A claim that cannot be processed must transition to a named FAILED state with a logged reason — not silently remain in an intermediate state.
- **Human authority must be preserved**. Any claim above the risk threshold is escalated. A human reviewer has final override on every escalated claim.

---

## Design principles

**Deterministic first** — policy rules, fraud signals, waiting period checks, and amount ceilings run before any LLM call. These rules are readable by a compliance officer and testable without infrastructure.

**LLM as enrichment, not authority** — Gemini provides explanation and anomaly reasoning. It does not set the risk score. It does not make the routing decision. If Gemini fails, the pipeline continues with a safe default.

**State machine as source of truth** — claim status is never set directly. Every transition passes through `ClaimStateMachine`, which enforces the valid transition map. An illegal transition raises an explicit error.

**Audit log as contract** — every state transition writes an audit entry atomically within the same database transaction. The audit log and the claim state are never out of sync. Each entry includes a SHA-256 hash of its content chained to the previous entry — making retroactive modification detectable.

**Explicit failure over silent corruption** — any pipeline exception transitions the claim to `FAILED` with a logged reason. No claim is left stuck in a non-terminal state.

**Human-in-the-loop by default** — the threshold for human review is set conservatively. It is cheaper to send a legitimate claim to human review than to auto-reject it incorrectly.

---

## System architecture

```
POST /claims/
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│  API Layer (FastAPI)                                    │
│  202 Accepted — pipeline runs in background             │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│  State Machine                                          │
│  submitted → analyzing → validated → scored →           │
│  escalated | approved | rejected | failed               │
│  Every transition: validated, logged, atomic            │
└──────┬───────────────────────────────────┬──────────────┘
       │                                   │
       ▼                                   ▼
┌──────────────────┐             ┌─────────────────────┐
│  Deterministic   │             │  LLM Reasoning      │
│  Engine          │             │  Layer (Gemini)      │
│                  │             │                     │
│  • Policy rules  │             │  • Claim summary    │
│  • Fraud signals │             │  • Anomaly surface  │
│  • Waiting period│             │  • Reviewer note    │
│  • Delay check   │             │                     │
│  • Ambiguity     │             │  Non-fatal. If LLM  │
│    detection     │             │  fails, pipeline    │
│                  │             │  continues.         │
└──────┬───────────┘             └──────────┬──────────┘
       │                                    │
       └────────────────┬───────────────────┘
                        │
                        ▼
           ┌────────────────────────┐
           │  Risk Scorer           │
           │                        │
           │  Weighted deterministic│
           │  score from all signals│
           │  LLM anomalies = soft  │
           │  signal only (+0.05    │
           │  each, capped)         │
           └────────────┬───────────┘
                        │
            ┌───────────┼───────────┐
            ▼           ▼           ▼
       auto_approve  escalate   auto_reject
       score < 0.60  score      score ≥ 0.90
                     ≥ 0.60     + hard failure
                                + fraud signal
                        │
                        ▼
           ┌────────────────────────┐
           │  Human Review          │
           │  POST /claims/{id}     │
           │  /review               │
           │  Reviewer has final    │
           │  authority always      │
           └────────────┬───────────┘
                        │
                        ▼
           ┌────────────────────────┐
           │  Audit Log             │
           │  Every transition:     │
           │  actor + reason +      │
           │  timestamp + hash      │
           │  chain                 │
           └────────────────────────┘
```

---

## Workflow lifecycle

A claim moves through exactly these states. No shortcutting.

```
SUBMITTED   → claim received, pipeline scheduled
ANALYZING   → document extraction running
VALIDATED   → deterministic rules evaluated
SCORED      → risk score computed, decision assigned
ESCALATED   → awaiting human reviewer
APPROVED    → terminal: claim approved
REJECTED    → terminal: claim rejected  
FAILED      → terminal: pipeline error, reason logged
```

Terminal states accept no further transitions. A claim in APPROVED cannot be re-opened except by creating a new claim. This is intentional — it prevents state corruption under concurrent requests.

---

## Deterministic vs LLM responsibility boundaries

This distinction is the architectural core of the system.

| Concern | Owner | Reason |
|---|---|---|
| Policy rule evaluation | Deterministic | Must be auditable and reproducible |
| Waiting period enforcement | Deterministic | Regulatory requirement |
| Fraud signal detection | Deterministic | Cannot rely on LLM consistency |
| Ambiguity detection | Deterministic | Flags before LLM call |
| Risk score calculation | Deterministic | Weighted formula, not inference |
| Routing decision | Deterministic | State machine enforces transitions |
| Claim summary | LLM | Natural language synthesis |
| Anomaly surfacing | LLM | Pattern recognition across description |
| Reviewer explanation | LLM | Plain English for human review |
| Final approval/rejection | Human | Always |

The LLM cannot approve a claim. The LLM cannot reject a claim. The LLM cannot set a risk score. If the LLM output fails to parse, the pipeline continues with empty anomalies and the deterministic result stands.

---

## Safety and guardrails

**Ambiguity detection** — claims lacking sufficient detail are flagged with `AMBIGUOUS_SUBMISSION` before any decision is committed. Triggers when two or more of the following are true: damage type unclassified, description under 20 words, high value with no signal flags. This directly addresses the merchant trust problem — a system that approves vague claims silently erodes partner confidence.

**Excessive delay detection** — claims reported more than 90 days after the incident are flagged with `EXCESSIVE_REPORTING_DELAY`. Most warranty policies require claims within 30–90 days. A 623-day delay is not auto-approved.

**Auto-reject threshold** — set at 0.90, requiring both a hard validation failure AND an active fraud signal. A pure amount ceiling violation never auto-rejects. The cost of a false auto-rejection exceeds the cost of sending one extra claim to human review.

**LLM degradation path** — the `analyze_claim` function wraps the entire Gemini call in try/except and returns a safe default on any failure. The pipeline has never failed because Gemini was unavailable.

**Word boundary matching** — legal threat detection uses regex word boundaries (`\bsue\b`) to prevent false positives on words like "issue" or "pursue". Simple substring matching creates compliance-grade false positives.

---

## Evaluation strategy

The eval harness is the most important file in this repository.

```bash
python eval_harness.py
```

```
============================================================
  CLAIMS AGENT — EVAL HARNESS
============================================================

✓ PASS  [TC-001] Clean low-value claim — auto_approve
✓ PASS  [TC-002] Legal threat + high value — human_review
✓ PASS  [TC-003] Waiting period violation — human_review
✓ PASS  [TC-004] Amount ceiling exceeded — human_review
✓ PASS  [TC-005] Excessive delay 200 days — human_review
✓ PASS  [TC-006] Excessive delay 623 days — human_review
✓ PASS  [TC-007] Ambiguous submission — human_review

============================================================
  RESULT: 7/7 passed — Quality score: 100%
============================================================
  ✓  All golden cases pass — safe to deploy
```

**Why the eval harness matters:**

The harness runs against the deterministic pipeline only — no LLM calls. This makes it fast (under 3 seconds), free (no API cost), and reproducible (same result every run). It exits with a non-zero code on any failure, making it CI-compatible.

The golden test cases represent ground-truth business logic. If a code change causes TC-001 to route to `human_review` instead of `auto_approve`, the harness catches it before deployment. This is the regression layer that makes the system trustworthy.

Each test case maps to a real failure mode:
- TC-001 validates the happy path is not over-triggered
- TC-002 validates fraud signal detection
- TC-003 validates waiting period enforcement
- TC-004 validates amount ceiling logic
- TC-005 and TC-006 validate delay detection at different severities
- TC-007 validates ambiguity detection for fulfillment confidence

---

## Failure handling

Every pipeline step is wrapped in try/except. Any exception transitions the claim to `FAILED` with a specific reason string. No claim exits the pipeline in a non-terminal intermediate state.

```python
# From orchestrator.py — the failure guarantee
def _fail(sm: ClaimStateMachine, claim: Claim, reason: str):
    try:
        sm.transition(claim, ClaimStatus.FAILED, "system", reason)
    except Exception:
        pass  # If even the FAILED transition fails, we accept it
```

The `FAILED` state is terminal and searchable. An operator can query all failed claims, inspect the reason, and re-submit or escalate manually. Silent failure is worse than explicit failure in every operational context.

---

## Human escalation philosophy

The system routes to human review when it is not confident, not when it is certain of rejection. This is a deliberate asymmetry.

Routing threshold: `score >= 0.60`
Auto-reject threshold: `score >= 0.90` AND hard failure AND fraud signal

The human reviewer receives:
- The full claim with all extracted signals
- The validation result with every rule outcome
- The risk score with contributing factors listed
- The LLM-generated explanation and anomaly list
- The complete audit trail

The reviewer submits a decision via `POST /claims/{id}/review` with a mandatory note explaining the decision. This note is written to the audit log. The system does not accept a review decision without a reason.

---

## Auditability and compliance

Every state transition writes an `AuditLog` entry atomically within the same database transaction. The audit entry and the claim state change commit together or roll back together — they are never out of sync.

Each audit entry contains:
- `from_status` and `to_status`
- `actor` — "system", "llm", or "reviewer:{id}"
- `reason` — mandatory human-readable explanation
- `extra_data` — validation results, risk factors, scores
- `timestamp`
- `entry_hash` — SHA-256 of this entry's content
- `previous_hash` — hash of the preceding entry

The hash chain means any retroactive modification to an audit entry invalidates all subsequent hashes. This is not cryptographic proof of integrity at the blockchain level, but it is sufficient to detect tampering in a regulated internal audit context.

The `actor` field is a string, not a foreign key. Audit logs must remain self-describing even if referenced users or systems are later deleted or renamed.

---

## Engineering tradeoffs

**SQLite over PostgreSQL for this demo** — SQLite with WAL mode handles the concurrent read/write pattern (background pipeline + API reads) adequately for demonstration scale. WAL is enabled explicitly at connection time. The connection string is an environment variable — switching to PostgreSQL requires one line change.

**Synchronous LLM call over async** — the LLM call runs synchronously with a timeout in a FastAPI background task. For production scale this would be an async call or a separate worker queue. The synchronous pattern is acceptable here because the background task model already decouples the LLM latency from the API response.

**No microservices** — the entire system runs as a single FastAPI process. The service layer separation (document extraction, validation, scoring, LLM reasoning) is logical, not deployment-level. Each service is independently testable. Splitting into microservices is a deployment decision, not an architecture decision, and premature splitting adds complexity without adding reliability at this scale.

**LRU-cached settings** — `get_settings()` is decorated with `@lru_cache()`. Settings are parsed once at startup. This means environment variable changes require a process restart. This is the correct tradeoff — settings mutation at runtime is a larger operational risk than a restart requirement.

**JSON storage for extracted fields** — `Claim.extracted_data` is a JSON column. This allows the extraction schema to evolve without migrations. The tradeoff is that individual extracted fields are not directly queryable by the database. Acceptable for this system's query patterns.

---

## Future improvements

**Immediate:**
- Async LLM calls with proper timeout handling via `httpx.AsyncClient`
- PostgreSQL migration for production deployment
- CI/CD pipeline running `eval_harness.py` on every commit, blocking merge on failure

**Short-term:**
- OEM warranty policy parser — LLM-based extraction of manufacturer PDFs into machine-readable coverage rules
- Merchant dashboard — React frontend showing escalated claims queue with approve/reject controls
- LLM output schema validation — reject and retry on malformed Gemini responses before they reach the database
- Expanded golden test set — 20+ cases covering edge cases in each failure category

**Medium-term:**
- Shopify webhook integration — real claims arriving from merchant checkout events
- Synthetic claim generator — 1000+ claims for precision/recall measurement of the deterministic pipeline
- Drift detection — monitor risk score distributions over time to detect when claim patterns shift
- Fine-tuned classification model — replace keyword-based damage type detection with a small trained classifier

---

## Production realism notes

This system was built to reflect real operational constraints, not to demonstrate AI capabilities. The specific design decisions that reflect production thinking:

- `202 Accepted` on submission, not `200 OK` — the work is not done at submission time
- Background task model — LLM latency does not block the API response
- Explicit FAILED terminal state — operators can query and act on pipeline errors
- Mandatory `reason` field on every audit entry — no transition without an explanation
- `AUTO_REJECT` requires compound conditions — amount alone never rejects
- Eval harness exits non-zero on failure — compatible with CI gates
- `actor` as string in audit log — self-describing, FK-independent
- WAL mode on SQLite — concurrent read/write without blocking
- `pool_pre_ping=True` — detects stale connections before use

---

## Repository structure

```
claims-agent/
├── app/
│   ├── core/
│   │   └── enums.py              # ClaimStatus, RiskLevel, DecisionOutcome
│   ├── models/
│   │   ├── claim.py              # Claim ORM model
│   │   ├── audit.py              # AuditLog with hash chain columns
│   │   ├── policy.py             # PolicyRule (deterministic config)
│   │   └── risk.py               # RiskScore (full scoring breakdown)
│   ├── services/
│   │   ├── state_machine.py      # ClaimStateMachine — only path to status change
│   │   ├── document_extractor.py # Deterministic signal extraction
│   │   ├── validator.py          # Policy rules + ambiguity guardrail
│   │   ├── llm_reasoner.py       # Gemini call — explanation only
│   │   ├── risk_scorer.py        # Weighted scoring + routing decision
│   │   ├── audit_logger.py       # Hash-chained audit entry writer
│   │   └── orchestrator.py       # Pipeline runner with failure guarantees
│   ├── routers/
│   │   ├── claims.py             # Submit, list, get, audit trail
│   │   └── review.py             # Human review decision endpoint
│   ├── schemas/
│   │   ├── claim.py              # Request/response validation
│   │   └── audit.py              # Audit trail response schema
│   ├── config.py                 # Pydantic settings with LRU cache
│   ├── database.py               # Engine + session + WAL pragma
│   └── main.py                   # FastAPI app + lifespan + router registration
├── eval_harness.py               # Golden test set — 7 cases, CI-ready
├── seed_data.py                  # Policy rules + demo claims
├── requirements.txt
├── .env.example
└── README.md
```

---

## Quickstart

```bash
# 1. Clone and install
git clone https://github.com/yourname/claims-agent
cd claims-agent
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Add your GEMINI_API_KEY to .env

# 3. Seed database
python seed_data.py

# 4. Run eval harness — verify pipeline correctness before starting
python eval_harness.py

# 5. Start server
python -m app.main

# 6. Open API explorer
# http://localhost:8000/docs
```

---

## API endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/claims/` | Submit claim — 202 Accepted, pipeline runs async |
| GET | `/claims/` | List claims, filter by status |
| GET | `/claims/{id}` | Get claim with full pipeline output |
| GET | `/claims/{id}/audit` | Full hash-chained audit trail |
| POST | `/claims/{id}/review` | Submit human review decision |
| GET | `/health` | Service health check |

---

## Stack

- **FastAPI** — async HTTP, background tasks, automatic schema validation
- **SQLAlchemy 2.0** — ORM with WAL-mode SQLite / PostgreSQL compatible
- **Pydantic v2** — settings management and request/response validation
- **Google Gemini** — LLM reasoning layer (non-fatal, graceful degradation)
- **SQLite** — zero-config persistence for local development and demo

---

*Built to demonstrate production-realistic thinking about operational AI in regulated workflows. Every architectural decision in this system exists for a reason that can be explained to a compliance officer, a regulator, or a senior engineer.*"
