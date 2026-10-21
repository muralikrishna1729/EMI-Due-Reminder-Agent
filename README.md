<div align="center">

# EMI Due Reminder Agent — Version 1

### A text-based EMI & loan collections agent with code-enforced compliance (Agent Persona: Maya Guard)

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LLM](https://img.shields.io/badge/LLM-Groq%20%2B%20Llama-F55036)](https://groq.com/)
[![Validation](https://img.shields.io/badge/Validation-Pydantic%20v2-E92063)](https://docs.pydantic.dev/)
[![ORM](https://img.shields.io/badge/ORM-SQLAlchemy%202-D71F00)](https://www.sqlalchemy.org/)
[![Tests](https://img.shields.io/badge/Tests-pytest-0A9EDC?logo=pytest&logoColor=white)](https://docs.pytest.org/)
[![Scope](https://img.shields.io/badge/Scope-Version%201%20%7C%20Text--only-2563EB)](#-overview)

**Use the LLM for language. Use application code for rules.**

</div>

---

## 📌 Contents

- [Overview](#-overview)
- [Problem and design principles](#-problem-and-design-principles)
- [System architecture](#-system-architecture)
- [Architecture image gallery](#-architecture-image-gallery)
- [Conversation state machine](#-conversation-state-machine)
- [Tool permissions and validation](#-tool-permissions-and-validation)
- [Safety and defence in depth](#-safety-and-defence-in-depth)
- [Data model and audit trail](#-data-model-and-audit-trail)
- [API overview](#-api-overview)
- [Technology stack](#-technology-stack)
- [Project structure](#-project-structure)
- [Run locally](#-run-locally)
- [Testing strategy](#-testing-strategy)
- [Metrics](#-metrics)
- [Version 1 limitations](#-version-1-limitations)
- [Roadmap](#-roadmap)
- [Security and deployment note](#-security-and-deployment-note)

## 🎯 Overview

The **EMI Due Reminder Agent** (featuring conversational agent persona **Maya**) is a **text-based collections and EMI reminder agent** for loan-payment conversations. An LLM helps understand and respond to customer messages, while Python application code controls identity verification, conversation state, permitted tools, business rules, and audit events.

The central safety rule is simple: **verify first, disclose second, always log the outcome**. Sensitive debt information must not be included in the prompt before identity verification succeeds, and an LLM request alone never grants permission to perform an action.

> **Version 1 is text-only.** It does not place phone calls, process audio, or record conversations. Voice is a possible later-version extension, not a current capability.

### ✨ At a glance

| Capability | What it means in Version 1 |
|---|---|
| 💬 Text conversation | A terminal client or HTTP client sends customer messages to the API. |
| 🧭 Explicit state machine | The conversation moves through `GREETING`, `VERIFYING`, `NEGOTIATING`, and `ENDED`. |
| 🔐 Verification gate | Only successful `verify_customer` permits entry into `NEGOTIATING`. |
| 🧰 Validated tool calls | Tool names, state permissions, arguments, and business rules are checked in code. |
| 🛡️ Layered guardrails | Prechecks, prompt data isolation, tool gating, and output filtering work together. |
| 🧾 Auditability | Conversation events are persisted in an append-only `call_events` table. |
| 🧪 Deterministic tests | A scripted fake LLM tests expected and adversarial behavior without calling a live model. |

## 🧩 Problem and design principles

Collections workflows are repetitive and compliance-sensitive. An LLM may generate convincing language, but prompt instructions alone are not a reliable enforcement boundary for privacy-sensitive actions.

The design separates **language generation** from **rule enforcement**:

1. **Precheck before the LLM** — silence, do-not-call requests, and abusive input are handled by code.
2. **Data isolation** — pre-verification prompts do not contain debt facts.
3. **State-based tool gating** — only tools permitted in the current state are offered and accepted.
4. **Output filtering** — unverified replies matching the forbidden-debt-word rules are replaced.
5. **Audit logging** — important events, including blocked tool attempts, are stored for traceability.

These controls reduce risk, but they are not a claim of perfect security or legal certification. See [Version 1 limitations](#-version-1-limitations).

## 🏗️ System architecture

![System Architecture — Version 1](assets/01-system-architecture.png)

The system is organized around five responsibilities:

| Layer | Main responsibility | Main components |
|---|---|---|
| **Client** | Collect a message and display the response | `chat_cli.py`, any HTTP client |
| **API** | Accept requests, validate payloads, route calls, expose health and metrics | `main.py` / FastAPI |
| **Orchestration** | Run prechecks, build prompts, coordinate the LLM/tool loop, finalize a turn | `engine.py` |
| **Domain modules** | Manage states, prompts, tool validation, guardrails, LLM calls, and security helpers | `state_machine.py`, `tools.py`, `guardrails.py`, `prompts.py`, `llm.py`, `security.py` |
| **Data** | Store customer records, live session state, and audit events | `models.py`, `db.py`, SQLAlchemy |

### 🔄 One customer turn

1. The client sends a message to the FastAPI endpoint.
2. The API validates the request and forwards it to the engine.
3. The engine runs code-side prechecks and reads the current state/context.
4. The engine builds a state-specific prompt and supplies only allowed tools to the LLM.
5. If the model requests a tool, `execute_tool()` validates and executes it.
6. The engine applies the output filter when required, persists state/history/events, and returns the final response.

The optional `graph.py` module provides a LangGraph-based alternative to the main `engine.py` turn pipeline; it is not required for the core flow.

## 🖼️ Architecture image gallery

The following images are included in the [`assets/`](assets/) folder as high-resolution PNGs. Image titles intentionally use descriptive technical names rather than the project name.

<details open>

<details>
<summary><strong>02 · Internal Architecture</strong></summary>

![Internal Architecture](assets/02-internal-architecture.png)

</details>

<details>
<summary><strong>03 · Codebase and Module Dependencies</strong></summary>

![Codebase and Module Dependencies](assets/03-codebase-module-dependencies.png)

</details>

<details>
<summary><strong>04 · Call State Machine</strong></summary>

![Call State Machine](assets/04-call-state-machine.png)

</details>

<details>
<summary><strong>05 · One-Turn Processing Flow</strong></summary>

![One-Turn Processing Flow](assets/05-one-turn-processing-flow.png)

</details>

<details>
<summary><strong>06 · Verification and Tool-Calling Sequence</strong></summary>

![Verification and Tool-Calling Sequence](assets/06-verification-tool-calling-sequence.png)

</details>

<details>
<summary><strong>07 · Defence in Depth</strong></summary>

![Defence in Depth](assets/07-defence-in-depth.png)

</details>

<details>
<summary><strong>08 · execute_tool() Validation Pipeline</strong></summary>

![execute_tool Validation Pipeline](assets/08-execute-tool-validation-pipeline.png)

</details>

<details>
<summary><strong>09 · State-Specific Prompts and Tools</strong></summary>

![State-Specific Prompts and Tools](assets/09-state-specific-prompts-and-tools.png)

</details>

<details>
<summary><strong>10 · Database Schema</strong></summary>

![Database Schema](assets/10-database-schema.png)

</details>

<details>
<summary><strong>11 · Testing Architecture</strong></summary>

![Testing Architecture](assets/11-testing-architecture.png)

</details>

<details>
<summary><strong>12 · End-to-End Customer Scenario</strong></summary>

![End-to-End Customer Scenario](assets/12-end-to-end-customer-scenario.png)

</details>

## 🔀 Conversation state machine

The system uses four states:

| State | Purpose | Debt facts in prompt? | Tool policy |
|---|---|---:|---|
| `GREETING` | Start the conversation and request identity verification | ❌ No | `verify_customer`, `mark_disposition` with limited statuses |
| `VERIFYING` | Collect and validate the required identity detail | ❌ No | `verify_customer`, `mark_disposition` with limited statuses |
| `NEGOTIATING` | Discuss the verified account and record a promise-to-pay if agreed | ✅ Yes, after verification | `log_promise_to_pay`, `escalate_to_agent`, `mark_disposition` |
| `ENDED` | Terminal state after completion or termination | ❌ No further account actions | No tools are allowed |

### Allowed state transitions

| From | Event | To |
|---|---|---|
| `GREETING` | `turn_done` | `VERIFYING` |
| `GREETING` or `VERIFYING` | successful verification | `NEGOTIATING` |
| `GREETING`, `VERIFYING`, or `NEGOTIATING` | `ended` | `ENDED` |

**Critical invariant:** the only permitted route into `NEGOTIATING` is successful execution of `verify_customer`. A prompt or model response cannot bypass that code-enforced transition.

## 🧰 Tool permissions and validation

The LLM can request only these four tools. Each request is checked server-side before execution.

| Tool | Allowed state(s) | Key server-side rule |
|---|---|---|
| `verify_customer` | `GREETING`, `VERIFYING` | Validate the four-digit input and compare against a salted hash; at most two attempts before `FAILED_AUTH`. |
| `log_promise_to_pay` | `NEGOTIATING` | Date must be today through 30 days ahead; amount must be 90%–100% of the overdue amount. |
| `escalate_to_agent` | `NEGOTIATING` | Creates an escalation ticket such as `ESC-####`. |
| `mark_disposition` | Every state except `ENDED` | Only limited statuses are available before verification; `PTP_AGREED` requires a logged promise-to-pay. |

### `execute_tool()` validation order

1. Confirm the tool name is registered.
2. Confirm the tool is permitted in the current state.
3. Validate arguments with the tool's Pydantic model.
4. Apply tool-specific business rules and current-session checks.
5. Execute the handler only when all checks pass.
6. Record the result or blocked attempt in the audit trail and return a result to the engine.

A rejected tool call should return a controlled error/result to the LLM; it must not silently perform a prohibited action.

## 🛡️ Safety and defence in depth

| Layer | Control | Intended protection |
|---|---|---|
| **Layer 0 — Precheck** | Code-side silence, DNC, and abuse checks before LLM invocation | Avoids invoking the model for known stop/termination conditions |
| **Layer 1 — Data isolation** | No debt facts in prompts before verification | Reduces exposure of account information to an unverified person |
| **Layer 2 — Tool gating** | State allowlist plus server-side argument and business-rule validation | Prevents unauthorized or malformed tool actions |
| **Layer 3 — Output filter** | Replace unverified replies matching forbidden debt-word rules | Adds a final defensive check on generated text |

### Important limitations

- Keyword-based DNC and abuse checks can miss paraphrases, misspellings, or context-dependent meaning.
- Keyword-based output filtering is not a complete semantic privacy guarantee.
- Four-digit verification is weak by nature and needs stronger controls before real-world deployment.
- Sensitive data must never be placed in logs or examples unnecessarily.

## 🗃️ Data model and audit trail

Version 1 uses **three tables**:

| Table | Purpose | Representative contents |
|---|---|---|
| `customers` | Customer/account facts | Account identifier, name, loan type, overdue amount, DPD, salted verification hashes, DNC flag |
| `call_sessions` | Current state of a single conversation | Customer FK, state, verification status/attempts, warnings, silence count, PTP flag, disposition, JSON history, timestamps |
| `call_events` | Append-only audit log | Verification, promise-to-pay, escalation, disposition, blocked tool, and other event details |

The relationship is `customers 1 → N call_sessions 1 → N call_events`. Event details are stored as JSON payloads where appropriate. There is no separate `tool_calls` table in the Version 1 schema described here; tool-call activity is represented through the event log.

**Database choice:** SQLite is used for development. PostgreSQL is planned for a later version; it should not be described as the current Version 1 database.

## 🌐 API overview

| Method | Endpoint | Purpose | Authentication note |
|---|---|---|---|
| `GET` | `/health` | Health check | Public health endpoint |
| `POST` | `/calls` | Start a conversation session | **No authentication in Version 1** |
| `POST` | `/calls/{id}/turn` | Submit a customer message and get a response | Follow the current implementation's configuration |
| `GET` | `/dispositions` | Query disposition outcomes | API key required |
| `GET` | `/metrics` | Read metrics | API key required |

The API table is an overview of the documented routes; request/response schemas should be checked against `main.py` before publishing a client SDK or integrating another application.

## 🧱 Technology stack

| Area | Technology | Role |
|---|---|---|
| Language | Python 3.10+ | Application logic and tool handlers |
| HTTP API | FastAPI, Uvicorn | Request routing and local server |
| LLM | Groq SDK with a hosted Llama model | Language generation and tool-call requests |
| Validation | Pydantic v2 | Validate tool arguments and structured inputs |
| ORM | SQLAlchemy 2 | Database models and sessions |
| Development database | SQLite | Local persistence |
| Planned database | PostgreSQL | Later-version persistence target |
| Optional orchestration | LangGraph | Alternative graph-based turn pipeline |
| Testing | pytest, httpx, scripted fake LLM | Deterministic unit and API tests |

## 📁 Project structure

The repository is structured with modular application code under `app/` and test suites under `tests/`:

```text
EMI-Due-Reminder-Agent/
├── app/
│   ├── __init__.py
│   ├── config.py          # Constants (limits, model name, keys)
│   ├── db.py              # Database connection & session factory
│   ├── engine.py          # Turn pipeline (start_call, handle_turn)
│   ├── guardrails.py      # Forbidden-word filter, DNC regex, abuse detector
│   ├── llm.py             # Groq LLM integration
│   ├── main.py            # FastAPI endpoints & metrics
│   ├── models.py          # SQLAlchemy tables (Customer, CallSession, CallEvent)
│   ├── prompts.py         # State-specific system prompts
│   ├── security.py        # Salted hashing and name masking
│   ├── seed.py            # Demo customer seeder
│   ├── state_machine.py   # States, tools, allowed-tools matrix, transitions
│   └── tools.py           # 5 tool handlers, Pydantic validation, execute_tool
├── tests/
│   ├── __init__.py
│   ├── conftest.py        # Pytest fixtures (db, customer, call)
│   ├── helpers.py         # Scripted fake LLM for deterministic tests
│   ├── test_guardrails.py # Leak and abuse filter tests
│   ├── test_scenarios.py  # End-to-end conversation scenario tests
│   ├── test_state_machine.py # State machine transition tests
│   └── test_tools.py      # Tool validation & boundary tests
├── assets/                # Architectural diagrams
├── chat_cli.py            # Terminal test client
├── pytest.ini             # Pytest configuration
├── requirements.txt       # Dependencies
├── .env.example           # Example environment variables
├── README.md              # Project documentation
├── CONCEPTS.md            # Deep architecture & theory guide
└── BUILD_AND_DEBUG.md     # Build order & debug guide
```

## 🚀 Run locally

### 1. Clone the repository & create a virtual environment

```bash
git clone https://github.com/muralikrishna1729/EMI-Due-Reminder-Agent.git
cd EMI-Due-Reminder-Agent
python -m venv .venv
```

**macOS / Linux**

```bash
source .venv/bin/activate
```

**Windows PowerShell**

```powershell
.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy the example environment file and configure your Groq API key:

```bash
cp .env.example .env
```

Set your `GROQ_API_KEY` in `.env`. Keep credentials in local environment configuration; **never commit `.env` files, API keys, verification codes, or real customer data**.

### 4. Initialize demo data and start the API

```bash
python -m app.seed
uvicorn app.main:app --reload
```

Use `chat_cli.py` or an HTTP client to submit text messages. The application is text-only in Version 1.

## 🧪 Testing strategy

Automated tests use a **scripted fake LLM** that returns predefined responses. This keeps tests deterministic and avoids depending on live-model output, network availability, or token limits.

The most important negative test is an **attempted pre-verification disclosure**: a misbehaving fake LLM tries to reveal the overdue amount before verification. The application should block or replace the response and must not move the session into `NEGOTIATING`.

Recommended test areas:

- State transitions and the verification gate.
- Tool allowlists by state.
- Invalid tool names and malformed arguments.
- Verification attempts and `FAILED_AUTH` behavior.
- Promise-to-pay date/amount boundaries.
- Payment-link requests before a logged promise.
- DNC, silence, abuse, and wrong-person handling.
- Output filtering and database event persistence.
- API request validation and protected endpoints.

Run the test suite from the repository root with:

```bash
pytest
```

The automated test suite does **not** replace a separately controlled evaluation against a real LLM.

## 📊 Metrics

Version 1 tracks:

- **PTP rate** — promise-to-pay outcomes.
- **Authentication failure rate** — calls ending in verification failure.
- **Containment rate** — computed over completed calls.

Metrics should be interpreted alongside call volume, test coverage, and event quality; they do not by themselves prove compliance or customer outcomes.

## ⚠️ Version 1 limitations

- Text-only; no audio, telephony, or call recording.
- Keyword-based DNC and abuse detection.
- `/calls` has no authentication in Version 1.
- Database initialization uses `create_all` rather than migrations.
- Four-digit verification is weak by nature.
- Typed verification codes remain in stored history in the current design.
- Automated tests use a scripted fake LLM rather than a real LLM.
- PostgreSQL and a voice interface are future-version items, not current features.

These limitations are important for an engineering prototype. Do not treat the current design as ready for unsupervised production collections without additional security, privacy, operational, and legal review.

## 🗺️ Roadmap

| Version | Planned scope | Status in this package |
|---|---|---|
| **Version 1** | Text agent, state machine, tool validation, guardrails, SQLite persistence, audit events, deterministic tests | **Current scope** |
| **Version 2** | More scenarios, improved metrics, PostgreSQL, migrations, stronger error handling, documentation hardening | Future plan |
| **Version 3** | Optional voice interface, such as browser microphone or Vapi web call | Future plan |

## 🔒 Security and deployment note

This repository describes an engineering prototype and does not constitute a legal compliance certification. Before handling real customer data, review applicable laws and contact rules, consent, privacy and retention, authentication, access control, audit integrity, secret management, verification strength, incident response, and human escalation procedures.

Use synthetic data for demos and tests. Never publish customer names, account identifiers, debt details, verification codes, API keys, or production logs.

---

<div align="center">

**Version 1 · Text-only · Code-enforced rules · Deterministic tests**


</div>
