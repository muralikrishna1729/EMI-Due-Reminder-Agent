# EMI Due Reminder Agent: Concepts Guide (Understand the Project)

**Purpose of this file:** help you *understand* how the project works: the vocabulary, the ideas, the architecture, and how data flows through it (agent persona: Maya Guard). Read it before coding and re-read it when you review the project.

**Companion file:** `BUILD_AND_DEBUG.md` is the doing guide (build order, tests, debugging, glitches, checklists).

> **Reading level assumed:** you know basic Python, you've built FastAPI and ML projects, and you are **new to**: AI agents, state machines, tool calling, and real-time conversation systems.
>
> **Scope:** Version 1 is **text only**. No audio, no phone, no recording. This guide explains how real voice systems work so you understand the field, and always says what *our* code does.
>
> **Honest note:** the Version 1 code was designed and traced by hand, not executed. Expect to fix small errors on your first run.

---

## Table of contents

1. Big picture
2. What is real in Version 1
3. Architecture map
4. Vocabulary (Python, Enums, state machines, database, API, LLM, business)
5. The state machine in this project
6. How an LLM behaves
7. Tool calling in depth
8. Three layers of defence
9. State management
10. Database schema, line by line
11. Call processing, recordings, agent management
12. One turn, end to end
13. Annotated code
13A–13G Extra explanations (regex, Pydantic, prompts, routes, hashing, LangGraph, helpers)
14. Data journeys
15. Worked scenarios
16. Recap card

**Suggested reading path:** 1, 2, 3, then 5, 7, 8, then 9, 10, then 12, 14, 15. Use section 4 as a dictionary whenever a word is unfamiliar. Section 13 is best read with the code open beside it.

---

# 1. Big picture

**What the project does.** An AI agent called Maya "phones" a customer who is late on a loan payment. She must:

1. Confirm she is talking to the right person.
2. **Verify identity before saying anything about the debt.**
3. Discuss the overdue amount and try to get a promise to pay.
4. End **every** call with a recorded outcome.

**Why it is hard.** The "brain" is an LLM. An LLM is helpful but unreliable: it can forget rules, be pushed by the customer, or make things up. In debt collection, one wrong sentence to the wrong person is a legal problem.

**The core idea:** *don't trust the prompt alone, enforce the rules in code.*

**Mental model: the new employee**

| Protection | Real-life version | In our code |
|---|---|---|
| Rulebook | Training manual | `prompts.py` |
| Locked cabinet | Employee isn't given files they aren't cleared for | Debt facts are **not in the prompt** until verified |
| Limited buttons | The phone only has the buttons needed right now | `ALLOWED_TOOLS` per state |
| Supervisor listening | Blocks forbidden words before they are spoken | `guardrails.py` output filter |
| Logbook | Every action written down | `call_events` table |
| Floor manager | Handles obvious cases without asking the employee | `precheck()` in `engine.py` |

---

# 2. What is real in Version 1

| Topic | In Version 1? | Notes |
|---|---|---|
| Conversation logic, states, tools, DB, tests | Yes | The real learning |
| LLM calls (Groq) | Yes | Needs a free API key |
| Voice (STT/TTS) | No | Optional Version 3 |
| Phone calls | No | Costs money, adds little learning |
| Call recording (audio) | No | Only text history and events are stored |
| Call scheduler (who to call when) | No | Out of scope |
| Real loan system | No | The `customers` table stands in |
| Authentication on `/calls` | No | Only `/metrics` and `/dispositions` need an API key |

---

# 3. Architecture map

```text
┌───────────────────────────────────────────────────────────────────────┐
│ CLIENT:  chat_cli.py (terminal)  or later a web page / voice platform │
└───────────────────────────────────────┬───────────────────────────────┘
                                        │ HTTP (JSON)
┌───────────────────────────────────────▼───────────────────────────────┐
│ API LAYER           app/main.py   (FastAPI routes, request validation) │
└───────────────────────────────────────┬───────────────────────────────┘
                                        │ function calls
┌───────────────────────────────────────▼───────────────────────────────┐
│ ORCHESTRATION       app/engine.py  (runs one turn; the "conductor")    │
└───┬───────────────┬───────────────────┬───────────────────┬───────────┘
    │               │                   │                   │
┌───▼────────┐ ┌────▼─────────┐ ┌───────▼────────┐ ┌────────▼─────────┐
│ prompts.py │ │ guardrails.py│ │ tools.py       │ │ llm.py           │
│ (what the  │ │ (word filter,│ │ (actions +     │ │ (talks to Groq)  │
│  LLM sees) │ │  DNC, abuse) │ │  business rules)│ │                  │
└────────────┘ └──────────────┘ └───────┬────────┘ └──────────────────┘
                                        │
        state_machine.py (rules of movement) · config.py · security.py
                                        │
┌───────────────────────────────────────▼───────────────────────────────┐
│ DATA LAYER   db.py + models.py   →  SQLite file (later PostgreSQL)     │
│              customers · call_sessions · call_events                   │
└───────────────────────────────────────────────────────────────────────┘
```

**Separation of concerns:** each layer has one job. The API layer doesn't know about prompts. Tools don't know about HTTP. That is why you can test tools with no server and no LLM.

**Dependency injection in one line:** `handle_turn(db, session, text, llm=chat)` receives the LLM as a parameter. In tests you pass a fake. In production you pass the real one. Same code, different helper.

---

# 4. Vocabulary

## 4.1 Python features used in this project

| Feature | Plain meaning | Example in the project |
|---|---|---|
| **Type hints** | Labels saying what type something should be. Python doesn't enforce them, but editors, Pydantic and SQLAlchemy read them | `def mask_name(name: str) -> str` |
| **`str \| None`** | "A string or nothing." Needs Python 3.10+ | `disposition: Mapped[str \| None]` |
| **Enum** | A fixed set of named choices (see 4.2) | `class State(str, Enum)` |
| **dict / set / tuple** | Lookup table / unique collection / fixed pair | `ALLOWED_TOOLS` is a dict of sets. `TRANSITIONS` uses tuples as keys |
| **`.get(key, default)`** | Dict lookup that returns a default instead of crashing | `TRANSITIONS.get((state, event), state)` |
| **Dataclass** | A class that mostly holds data, with less boilerplate | `TurnResult` |
| **Decorator** (`@something`) | A line above a function that wraps or registers it | `@app.post("/calls")` registers a route. `@pytest.fixture` marks a test helper |
| **Generator / `yield`** | A function that pauses. Code before `yield` is setup, after is cleanup | `get_db()` opens a DB session, yields it, closes it in `finally` |
| **Context manager / `with`** | Auto-cleanup block | `with SessionLocal() as db:` |
| **f-string** | Text with values inside braces | `f"PTP-{n}"` |
| **Slicing** | Part of a list. `[-20:]` means the last 20 | `list(s.history)[-20:]` |
| **`**` unpacking** | Spread a dict into keyword arguments | `kwargs = dict(...)` then `create(**kwargs)` |
| **`lambda`** | A tiny anonymous function | `default=lambda: str(uuid.uuid4())`, so each row gets a **new** id |
| **Functions as values** | You can pass a function as an argument | `llm=chat` |
| **Regex** | A pattern language for matching text | `re.compile(...)` in `guardrails.py` |
| **`try / except`** | Catch errors instead of crashing | Wrapping the LLM call |
| **`isinstance`** | Check a value's type | Make sure parsed JSON is a dict |
| **`global`** | Lets a function change a module-level variable | Lazy Groq client in `llm.py` |
| **`SimpleNamespace`** | Quick fake object with attributes | Fake LLM responses in tests (`NS`) |
| **`secrets` vs `random`** | `secrets` is for unpredictable values | PTP ids and salts |
| **`hmac.compare_digest`** | Compare two strings in constant time | Hash comparison in `_verify` |
| **`@pytest.mark.parametrize`** | Run one test with many inputs | `test_leaks_are_detected` |

## 4.2 Enums: the project's most important Python feature

**What is an Enum?** A fixed list of named values. Instead of writing the string `"NEGOTIATING"` in 20 places (and risking `"NEGOTIATNG"`), you define it once.

```python
class State(str, Enum):
    GREETING = "GREETING"
    VERIFYING = "VERIFYING"
    NEGOTIATING = "NEGOTIATING"
    ENDED = "ENDED"
```

| Expression | Result | Meaning |
|---|---|---|
| `State.GREETING` | the member | The named choice |
| `State.GREETING.value` | `"GREETING"` | The plain string inside |
| `State("GREETING")` | `State.GREETING` | Turn a string back into a member |
| `State("typo")` | **ValueError** | Invalid values are rejected |
| `State.GREETING == "GREETING"` | `True` | Because of `(str, Enum)` |

**Why `(str, Enum)`?** The `str` part makes members behave like strings, so they compare, print and convert to JSON easily.

**Why the code mixes `.value` and enums:** the database stores a plain string (`s.state = "NEGOTIATING"`), but the logic wants members (`State(s.state)`).

```python
s.state = State.NEGOTIATING.value   # member → string for the DB
State(s.state)                       # string from DB → member for logic
s.state == State.ENDED.value         # comparing two strings
```

**Enums in this project**

| Name | Where | Values |
|---|---|---|
| `State` | `state_machine.py` | `GREETING`, `VERIFYING`, `NEGOTIATING`, `ENDED` |
| `Tool` | `state_machine.py` | `verify_customer`, `log_promise_to_pay`, `escalate_to_agent`, `mark_disposition` |

**`Literal` is a lighter cousin of Enum.** `status: Literal["PTP_AGREED", ...]` in Pydantic models means "only these strings are accepted." Dispositions, channels and escalation reasons use `Literal`. They are **not** Enums, so they aren't a single source of truth. Converting them to Enums is a possible later improvement.

**Beginner trap:** if you add a value to an Enum, check every place that lists all values (`ALLOWED_TOOLS`, prompts). The checklists in `BUILD_AND_DEBUG.md` section 8 cover this.

## 4.3 State machine terms (and where each lives in code)

A **finite state machine (FSM)** is a system that is in **exactly one state at a time** and moves only along **allowed transitions**. Traffic light: green, then yellow, then red. Green can't jump to flashing blue.

| Term | Plain meaning | In our project |
|---|---|---|
| **State** | Where the call currently is | `GREETING`, `VERIFYING`, `NEGOTIATING`, `ENDED` |
| **Initial state** | Where it starts | `GREETING`, set in `start_call()` |
| **Terminal / final state** | No way out | `ENDED` |
| **Event** | Something that happens and may cause a move | Strings: `"turn_done"`, `"verified"`, `"ended"` |
| **Transition** | A move from one state to another because of an event | `(VERIFYING, "verified")` leads to `NEGOTIATING` |
| **Transition table** | The list of allowed transitions | `TRANSITIONS` dict in `state_machine.py` |
| **Guard** | A condition that must be true for a move | "Only move to `NEGOTIATING` if the code matches", `if ok:` in `_verify` |
| **Action / side effect** | Work done during a move | Writing the event, committing, setting `ended_at` |
| **Illegal transition** | A move the table doesn't allow | `(GREETING, "negotiate")`. `next_state` just returns the same state |
| **Self-loop / no-op** | Event received, state unchanged | Unknown pairs fall back to the current state |
| **Reachable state** | Can you get there from the start? | `NEGOTIATING` is reachable only via `"verified"` |
| **Invariant** | A fact that must always be true | "State is `NEGOTIATING` implies verified is true" |
| **Extended state** | Extra variables stored beside the state | `verified`, `verify_attempts`, `ptp_logged`, counters |
| **Deterministic** | Same input leads to the same result | Our code. The LLM is **not** deterministic |
| **Happy path** | Everything goes right | Verify, promise, link, `PTP_AGREED` |
| **Unhappy path** | Failures and edge cases | Wrong code, DNC, abuse, silence |
| **Fail-closed** | When unsure, deny | Output filter replaces suspicious replies |
| **Fail-open** | When unsure, allow (dangerous) | The default branch in `build_system_prompt` (see glitch 16 in `BUILD_AND_DEBUG.md`) |

**Why "state plus flags" (extended state)?** `state` answers "which stage?". Flags answer detail questions ("how many wrong tries?", "was a PTP logged?"). Making a separate state for every combination would explode in number. Flags keep the diagram small.

## 4.4 Database and ORM terms

| Term | Plain meaning | In our code |
|---|---|---|
| **Database** | Organised storage that survives restarts | `maya.db` (SQLite) |
| **Table** | A grid. Each row is one record | `customers`, `call_sessions`, `call_events` |
| **Row / record** | One entry | One customer, or one call |
| **Column / field** | One attribute | `overdue_amount` |
| **Schema** | The structure: tables, columns, types | `models.py` defines it |
| **Primary key (PK)** | Column that uniquely identifies a row | `id` |
| **Foreign key (FK)** | Column that points to another table's row | `customer_id` points to `customers.id` |
| **Unique** | No duplicates allowed | `account_id` |
| **Index** | A lookup shortcut that speeds up searches | `index=True` on `account_id`, `session_id` |
| **Nullable** | Whether the column may be empty | `str \| None` means nullable |
| **Default** | Value used if none is given | `default=False` |
| **ORM** | Lets you use Python classes instead of SQL | SQLAlchemy |
| **Engine** | The connection factory to the database | `create_engine(...)` |
| **Session (DB)** | A workspace for reading and writing. Collects changes, then saves | `db` in our code |
| **sessionmaker** | A factory that creates DB sessions | `SessionLocal` |
| **Transaction** | A group of changes saved all-or-nothing | Everything until `commit()` |
| **`add()`** | Queue a new object for saving | `db.add(CallEvent(...))` |
| **`commit()`** | Save queued changes permanently | After each action |
| **`rollback()`** | Throw away unsaved changes | Automatic on error or close |
| **`flush`** | Send queued changes to the DB without finishing the transaction | Happens inside commit |
| **`expire_on_commit=False`** | Keep Python objects loaded after commit instead of re-fetching | Our setting |
| **`autoflush=False`** | Don't auto-send pending changes before queries | Our setting |
| **Relationship** | Python-level link between two tables | `CallSession.customer` |
| **Lazy loading** | Related object is fetched when first accessed | `s.customer` |
| **JSON column** | Column storing a list or dict | `history`, `payload` |
| **`create_all`** | Create tables that don't exist yet | Does **not** modify existing tables |
| **Migration** | A controlled schema change (tool: Alembic) | Skipped in Version 1 |
| **Append-only log** | Rows only added, never edited | `call_events` |
| **Audit trail** | A trustworthy history of what happened | `call_events` |

**Name collision warning:** the word **session** appears in three meanings.

| You see | It means |
|---|---|
| `db`, `SessionLocal`, `Session` (SQLAlchemy) | A **database workspace** |
| `CallSession`, `session`, `s` | **One phone call** (a row in `call_sessions`) |
| `session_id` | The call's id string |

When reading the code, translate: *"db is the notebook, session is the call."*

## 4.5 API, Pydantic and FastAPI terms

| Term | Plain meaning | In our code |
|---|---|---|
| **API** | A way for programs to talk | Our HTTP endpoints |
| **Endpoint / route** | One URL plus method | `POST /calls` |
| **HTTP methods** | `GET` reads, `POST` sends data | `GET /health`, `POST /calls/{id}/turn` |
| **Path parameter** | A variable in the URL | `{session_id}` |
| **Request body** | JSON the client sends | `{"text": "1234"}` |
| **Status code** | Result category: 200 OK, 401 unauthorized, 403 forbidden, 404 not found | `HTTPException(404, ...)` |
| **Header** | Extra info with a request | `X-API-Key` |
| **Dependency injection (FastAPI)** | FastAPI calls a helper and hands you the result | `db: Session = Depends(get_db)` |
| **Lifespan** | Code that runs on startup and shutdown | Creates tables at startup |
| **uvicorn** | The server program that runs FastAPI | `uvicorn app.main:app --reload` |
| **`/docs`** | Automatic interactive API page | Open `http://127.0.0.1:8000/docs` |
| **Pydantic model** | A class that validates data | `PTPArgs` |
| **`Field(...)`** | Adds rules to a field | `Field(gt=0)`, `Field(pattern=...)` |
| **Validator** | Custom check or conversion | `_to_str` converts `1234` (int) to `"1234"` |
| **`ValidationError`** | Raised when data breaks the rules | Caught in `execute_tool` |
| **`model_validate(dict)`** | Validate a dict against a model | `PTPArgs.model_validate(raw)` |
| **`model_json_schema()`** | Produces a JSON Schema describing the model | Becomes the tool schema for the LLM |
| **JSON** | Text format for structured data | Everywhere |
| **Serialization** | Turning objects into text (JSON) | `json.dumps(result)` |
| **ISO-8601** | Standard date format `YYYY-MM-DD` | `ptp_date` |

**`app.main:app` decoded:** package `app`, file `main.py`, object named `app`. Three things called "app", which is confusing but normal.

## 4.6 LLM and agent terms

| Term | Plain meaning |
|---|---|
| **LLM** | A model trained to continue text. Given messages, it writes a reply |
| **Agent** | LLM plus instructions plus tools plus a goal |
| **Prompt** | Everything you send to the LLM |
| **System prompt** | The first, hidden message with rules and persona |
| **Roles** | `system` rules, `user` customer, `assistant` Maya, `tool` tool results |
| **Message list** | The full conversation you send each time |
| **Context window** | The maximum text the LLM can read at once |
| **Token** | A small chunk of text (about 3/4 of a word). Limits and billing use tokens |
| **Turn** | One customer message plus Maya's reply |
| **Call session** | The whole conversation (many turns) |
| **Stateless** | No memory between calls. **LLMs are stateless**, so we resend history |
| **Temperature** | Randomness. 0.1 is steady, 1.0 is creative |
| **`max_tokens`** | Cap on reply length (we use 300) |
| **Hallucination** | Confidently wrong or invented output |
| **Prompt injection / pressure** | User tries to override the rules ("ignore your instructions") |
| **Tool / function calling** | The LLM returns a structured request to run a function instead of text |
| **Tool schema** | A JSON description of a tool: name, purpose, arguments |
| **`tool_choice="auto"`** | LLM decides whether to call a tool |
| **`tool_call_id`** | Links a tool result to the request that caused it |
| **Guardrail** | A check that limits what the agent can say or do |
| **Orchestration** | The code that coordinates LLM, tools and state (our `engine.py`) |
| **Scripted / fake LLM** | A test helper that returns pre-written replies |
| **Groq** | A service hosting fast open models, with a free tier |
| **Rate limit** | Max requests allowed per time period. Exceeding it gives an error |

## 4.7 Design, security and business terms

| Term | Meaning |
|---|---|
| **Defence in depth** | Several independent protections, so one failure isn't fatal |
| **Data minimisation** | Don't give a component data it doesn't need (our "locked cabinet") |
| **PII** | Personal data. Handle carefully and never log it |
| **Hashing** | One-way scramble. Same input always gives the same hash |
| **Salt** | Random text added before hashing |
| **Masking** | Showing part of a value (`Rahul S*****`) |
| **Race condition** | Two things happening at once cause a wrong result |
| **Idempotent** | Doing it twice has the same effect as once |
| **Adapter** | A small wrapper hiding an external service (`llm.py`) |
| **Mock / fake / stub** | Test stand-ins for real components |
| **EMI** | Monthly loan instalment |
| **DPD** | Days Past Due |
| **PAN** | Indian tax ID. We ask for the last 4 digits |
| **PTP** | Promise To Pay |
| **Disposition** | Final outcome label for a call |
| **DNC** | Do Not Call request |
| **Escalation** | Handing over to a human agent |
| **Waiver** | Discount on the amount owed |
| **Third party** | Someone other than the customer |
| **RBI Fair Practices** | Indian rules on how lenders contact borrowers |
| **STT / TTS** | Speech to text / text to speech |
| **Telephony** | Phone connection technology |
| **Vapi** | A platform bundling telephony + STT + TTS around your LLM |
| **Webhook** | Your URL that another service calls |
| **Latency** | Delay before the reply starts |

---

# 5. The state machine in this project

## Diagram

```text
                 turn_done
   ┌──────────┐ ───────────────► ┌───────────┐
   │ GREETING │                  │ VERIFYING │
   └──────────┘                  └───────────┘
     │   │                          │    │
     │   └──── verified ──┐         │    │ verified
     │                    ▼         │    ▼
     │               ┌─────────────┐◄───┘
     │               │ NEGOTIATING │
     │               └─────────────┘
     │ ended              │ ended         (also VERIFYING → ENDED)
     └───────────┬────────┘
                 ▼
            ┌─────────┐
            │  ENDED  │  terminal
            └─────────┘
```

## The three tables that define everything

**1. Transition table** (`TRANSITIONS`): *where can I go?*

| From | Event | To |
|---|---|---|
| GREETING | `turn_done` | VERIFYING |
| GREETING | `verified` | NEGOTIATING |
| VERIFYING | `verified` | NEGOTIATING |
| GREETING / VERIFYING / NEGOTIATING | `ended` | ENDED |

**2. Allowed-tools table** (`ALLOWED_TOOLS`): *what can the LLM do here?*

| State | Tools |
|---|---|
| GREETING | `verify_customer`, `mark_disposition` |
| VERIFYING | `verify_customer`, `mark_disposition` |
| NEGOTIATING | `log_promise_to_pay`, `escalate_to_agent`, `mark_disposition` |
| ENDED | none |

**3. Prompt per state** (`build_system_prompt`): *what does the LLM know here?* Only `NEGOTIATING` contains debt facts.

## The original project's 5 states mapped to ours

| Original | Ours |
|---|---|
| State 0 Greeting | `GREETING` |
| State 1 Verification | `VERIFYING` |
| State 2 Disclosure and negotiation | `NEGOTIATING` |
| State 3 Action execution | Tool calls inside `NEGOTIATING` |
| State 4 Wrap-up | `mark_disposition`, which leads to `ENDED` |

## Who triggers each event?

| Event | Triggered by | Code location |
|---|---|---|
| `turn_done` | End of the first customer turn | `finalize()` |
| `verified` | Successful `verify_customer` | `_verify()` |
| `ended` | Any final outcome | `end_call()` |

## Why `GREETING` allows `verify_customer`

A customer might say "Yes, my PAN ends with 1234" in the first reply. If verification were blocked in `GREETING`, Maya would ask for the code again. Allowing it is harmless: **the gate is verification, not the state label.**

## Invariants (facts that must always be true)

These are your best review and test targets.

| # | Invariant |
|---|---|
| I1 | `state == NEGOTIATING` implies `verified == True` |
| I2 | `verified == False` means the system prompt contains no debt facts |
| I3 | `state == ENDED` implies `disposition` and `ended_at` are set |
| I4 | `ptp_logged == True` means a `PTP` event exists for that call |
| I5 | An ended call has exactly one `DISPOSITION` event |
| I6 | `FAILED_AUTH` and `TERMINATED_ABUSE` can only come from code, never from the LLM |
| I7 | A `VERIFY` event never contains the code |

## State versus flags: why both `state` and `verified`?

They carry overlapping information and normally agree. `state` drives **tools and prompt**. `verified` drives the **output filter**. Keeping both means a bug in one doesn't automatically disable the other, which is also a form of defence in depth. The cost: they can disagree if you edit one by hand (glitch 22 in `BUILD_AND_DEBUG.md`).

---

# 6. How an LLM behaves (what a builder must know)

1. **It writes the likeliest helpful continuation.** It doesn't "know" your rules, it tends to follow instructions.
2. **It is stateless.** You resend history every call. If you don't send it, it doesn't know it.
3. **It only knows what is in the prompt.** This is why *not including* debt facts is stronger than saying "don't reveal them."
4. **Instructions are soft.** A pushy user, a long conversation, or odd wording can override them.
5. **Same input can give different output**, even at low temperature. Never write code that assumes exact wording.
6. **It is good at language tasks**: understanding "parso", turning "Friday" into a date, answering in Hinglish.
7. **It is bad at guarantees**: counting attempts, never forgetting a rule, exact formats.
8. **Tool calling is a learned skill.** Quality varies by model. Sometimes the model produces a malformed call and the provider returns an error.
9. **It costs time and quota.** Each LLM call takes a moment and counts towards rate limits. Our loop allows up to 4 calls per turn.
10. **You can't unit test it directly.** So we test *our code around it* with a fake LLM, and evaluate the real LLM with a scenario checklist.

**Division of labour**

| Use the LLM for | Use code for |
|---|---|
| Understanding messy speech | Rules that must never fail |
| Wording replies naturally | Counting attempts, limits, ceilings |
| Mapping "parso" to a date | Validating the date |
| Choosing which tool to call | Deciding whether the call is allowed |

---

# 7. Tool calling in depth

## The idea

The LLM can't touch your database. It can only **ask** for an action, in a structured format. Your code checks and performs it.

```text
LLM:  "Please run verify_customer with code 1234"   (a request, not an action)
Code: allowed? valid? correct? → runs it → returns a result
LLM:  reads the result → writes the reply
```

## The four tools

| Tool | Purpose | Arguments | Server-side rules |
|---|---|---|---|
| `verify_customer` | Check identity | `verification_code` (4 digits) | Max 2 attempts. Second failure ends the call as `FAILED_AUTH` |
| `log_promise_to_pay` | Record a PTP | `ptp_date` (ISO), `amount` | Date is today to +30 days. Amount between 90% and 100% of overdue |
| `escalate_to_agent` | Hand to human | `reason`, `summary` | Creates an `ESC-####` ticket |
| `mark_disposition` | Final outcome, ends call | `status`, `notes` | Before verification only `WRONG_PERSON`, `DO_NOT_CALL`, `NO_RESPONSE`. `PTP_AGREED` needs a logged PTP |

`FAILED_AUTH` and `TERMINATED_ABUSE` are **system-only** statuses, set by code. The LLM can't choose them.

## What the LLM is shown

For each allowed tool: a name, a description, and the arguments as a JSON Schema. Pydantic generates the schema from your class, roughly:

```json
{
  "type": "function",
  "function": {
    "name": "log_promise_to_pay",
    "description": "Record the customer's promise to pay.",
    "parameters": {
      "type": "object",
      "properties": {
        "ptp_date": {"type": "string", "format": "date",
                     "description": "Promised payment date, ISO-8601 (YYYY-MM-DD)"},
        "amount":   {"type": "integer", "exclusiveMinimum": 0,
                     "description": "Promised amount in rupees"}
      },
      "required": ["ptp_date", "amount"]
    }
  }
}
```

> **Key point:** the *description* fields are instructions to the LLM. Clear descriptions mean better calls.

## The conversation, step by step

After the customer types "Yes, my PAN ends with 1234", the LLM answers with a tool request. We run it and call the LLM again with this message list:

```json
[
  {"role": "system",    "content": "<NEW prompt: now includes debt facts>"},
  {"role": "assistant", "content": "Hello, this is Maya ... Am I speaking with Rahul Sharma?"},
  {"role": "user",      "content": "Yes, my PAN ends with 1234"},
  {"role": "assistant", "content": "",
   "tool_calls": [{"id": "call_1", "type": "function",
                   "function": {"name": "verify_customer",
                                "arguments": "{\"verification_code\": \"1234\"}"}}]},
  {"role": "tool", "tool_call_id": "call_1",
   "content": "{\"ok\": true, \"verified\": true, \"customer_name\": \"Rahul S*****\"}"}
]
```

Things to notice:

- `arguments` is a **string** containing JSON, so we need `json.loads`.
- The `tool` message uses `tool_call_id` to say "this is the answer to call_1".
- `messages[0]` (the system prompt) was **replaced** after the tool ran, because the state changed.
- The result is also a string, made by `json.dumps`.

## The tool loop

```text
repeat up to 4 times:
    ask LLM (with tools allowed in the current state)
    if reply has tool_calls:
        run each one → append results → rebuild system prompt → loop
    else:
        plain text → this is Maya's reply → stop
```

## What `execute_tool` checks, in order

```text
1. Is the tool name real?                → else error "Unknown tool"
2. Is it allowed in the current state?   → else log BLOCKED_TOOL + error
3. Do the arguments pass Pydantic?       → else error "Invalid arguments"
4. Do the business rules pass?           → else error (e.g. below waiver limit)
5. Do the work, log the event, commit    → return {"ok": true, ...}
```

## Result design rules

- Always return a dict with `"ok"`.
- On failure, include a short **actionable** `"error"`: *"Escalate to a human agent."* The LLM reads it and adapts.
- Never raise exceptions for expected problems. Return data instead.
- Never include secrets in results.

## Tool-calling failure modes

| Failure | What happens in our code |
|---|---|
| LLM invents a tool name | `Unknown tool` error returned |
| LLM calls a tool not allowed now | Blocked, logged as `BLOCKED_TOOL` |
| Arguments are not valid JSON | Treated as `{}`, so a validation error is returned |
| Wrong type (number instead of string) | Validator converts where safe, else error |
| Missing field | Validation error returned |
| Repeats the same call endlessly | `MAX_TOOL_ROUNDS` stops it |
| Provider rejects a malformed call | Exception, so you need the try/except patch (`BUILD_AND_DEBUG.md` section 7-A) |
| Several tool calls in one message | Run in order. The state can change mid-batch (glitch 18, patch 7-B) |

---

# 8. Three layers of defence

```text
Customer message
      │
      ▼
 Layer 0  precheck (code only, no LLM): silence, "stop calling", abuse
      │
      ▼
 Layer 1  DATA ISOLATION: before verification the prompt has NO debt facts
      │
      ▼
 Layer 2  TOOL GATING: LLM only sees allowed tools, server also rejects forbidden ones
      │
      ▼
 Layer 3  OUTPUT FILTER: if unverified and the reply has "overdue", "EMI", "₹"...
          → replaced with a safe sentence
      │
      ▼
 Reply
```

| Layer | Stops | Fails if |
|---|---|---|
| 0 | Obvious cases without wasting an LLM call | Customer uses phrases not on the list |
| 1 | The LLM leaking facts it doesn't have | You accidentally put facts in the pre-verification prompt |
| 2 | Skipping verification, early promises, early links | You forget to update `ALLOWED_TOOLS` for a new tool |
| 3 | Leaks that slipped through | The filter word list misses a phrasing |

---

# 9. State management

## Where state lives

**In the database, not in server memory.** The server forgets everything between requests.

```text
Request arrives with session_id
  → load the call_sessions row (state, flags, history)
  → handle the turn (may change the row, add events)
  → commit
  → respond
```

A server that keeps nothing in memory is **stateless**. That means:

- You can restart it mid-call and nothing is lost.
- You could run several copies later.

## Three kinds of state

| Kind | Where | Example | Who may rely on it |
|---|---|---|---|
| **Control state** | `state`, `verified`, counters | "verified = true" | **Code** (reliable) |
| **Conversation memory** | `history` JSON | What was said | The LLM (unreliable) |
| **Event log** | `call_events` | "PTP-4821 logged" | Reports, audits |

**Rule:** anything that matters for rules must live in control state, not in the LLM's memory.

## What happens to history

- Stored: last 40 messages. Sent to the LLM: last 20.
- Older details drop out. That is why `ptp_logged` is a flag, and the prompt tells the LLM whether a PTP was already logged.

## Commit points (when changes become permanent)

| Moment | What is saved |
|---|---|
| `start_call` | Session created |
| Each tool handler | Event written |
| `end_call` | Final disposition saved |
| `precheck` (silence and abuse counters) | Counter saved |
| `finalize` | History saved |

Consequence: if the server crashes **between** a tool and `finalize`, the tool's effect is saved but the turn isn't in history (glitch 19 in `BUILD_AND_DEBUG.md`).

## Concurrency

Two requests for the same call at the same moment could overwrite each other (**race condition**). A real voice call is sequential (one turn at a time), so Version 1 ignores this. PostgreSQL row locks would be the fix.

---

# 10. Database schema, line by line

## The mental picture

```text
customers (1) ──────< call_sessions (many) ──────< call_events (many)
 "who is the person"    "one row per call"         "one row per action"
```

`1 ──< many` means one customer can have many calls, and one call can have many events.

## `models.py` explained

```python
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base
```
The building blocks. `Base` is the parent class that turns a normal Python class into a table definition.

```python
def utcnow() -> datetime:
    return datetime.now(timezone.utc)
```
Returns "now" in UTC (a world standard time zone). Storing UTC avoids time zone confusion. Used as a column default.

```python
class Customer(Base):
    __tablename__ = "customers"
```
This class **is** the table. `__tablename__` is the table's real name in the database. One `Customer` object is one row.

```python
    id: Mapped[int] = mapped_column(primary_key=True)
```
- `Mapped[int]` says the Python type is `int`.
- `mapped_column(...)` configures the column.
- `primary_key=True` makes it the unique row id, automatically numbered.

```python
    account_id: Mapped[str] = mapped_column(String(30), unique=True, index=True)
```
- `String(30)`: text up to 30 characters.
- `unique=True`: no two customers share an account id.
- `index=True`: lookups by this column are fast (we search by it in `POST /calls`).

```python
    overdue_amount: Mapped[int] = mapped_column(Integer)
```
Whole rupees. (Real systems often store paise to avoid decimals. We keep it simple.)

```python
    salt: Mapped[str] = mapped_column(String(32))
    pan_last4_hash: Mapped[str] = mapped_column(String(64))
```
A SHA-256 hash is 64 characters, so `String(64)`. We store the **scrambled** value, not the real digits.

```python
    do_not_call: Mapped[bool] = mapped_column(Boolean, default=False)
```
`default=False` is a **Python-side default**: SQLAlchemy fills it in when inserting.

```python
class CallSession(Base):
    __tablename__ = "call_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
```
- The id is a **UUID** (random unique text like `3f2a...`), not a number, so ids can't be guessed.
- `lambda` makes a **fresh** UUID per row. Without it, one UUID would be created once and reused.

```python
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
```
A **foreign key**: this value must match some `customers.id`. It ties each call to its customer.

```python
    history: Mapped[list] = mapped_column(JSON, default=list)
```
Stores a Python list as JSON. `default=list` creates an empty list for each new row.

> **Glitch alert:** SQLAlchemy doesn't notice when you modify a JSON list **in place**. Always reassign: `s.history = s.history + [msg]`.

```python
    disposition: Mapped[str | None] = mapped_column(String(30), nullable=True)
```
`str | None` plus `nullable=True`: empty until the call ends.

```python
    customer: Mapped[Customer] = relationship()
```
Not a column. It lets you write `session.customer.full_name` instead of querying by hand. SQLAlchemy uses the foreign key to find the row (**lazy loading**: it fetches the row the first time you touch it).

```python
class CallEvent(Base):
    __tablename__ = "call_events"
    session_id: Mapped[str] = mapped_column(ForeignKey("call_sessions.id"), index=True)
    type: Mapped[str] = mapped_column(String(20))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
```
One row per action. `type` says what kind (`PTP`, `VERIFY`...). `payload` holds the details as JSON, so you don't need a separate table per event type.

## What it looks like in SQL (for intuition)

```sql
CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    account_id VARCHAR(30) NOT NULL UNIQUE,
    full_name VARCHAR(100) NOT NULL,
    overdue_amount INTEGER NOT NULL,
    do_not_call BOOLEAN NOT NULL
    -- ...other columns
);
```
`Mapped[str]` (no `None`) becomes `NOT NULL`. `Mapped[str | None]` is nullable.

## What the engine and session do (`db.py`)

```python
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
```

- **Engine** = the connection to the database file or server.
- **sessionmaker** = a factory making DB workspaces (`SessionLocal()`).
- `expire_on_commit=False` = after saving, keep the loaded values so `s.customer.full_name` still works without another query.
- `autoflush=False` = we decide exactly when things are saved (`commit()`).

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```
FastAPI calls this per request: open a workspace, hand it to the route, close it afterwards. Unsaved changes are discarded on close.

## Defaults are filled at save time

A brand new `CallSession(...)` has `verify_attempts = None` until it is saved. That is why `start_call` commits immediately. If you read counters on an unsaved object, you get `None`.

## The three tables in detail

**`customers`** (who we call)

| Column | Meaning |
|---|---|
| `account_id` | Business id (`ACC-88392`) |
| `full_name` | Used in the greeting and for the masked name |
| `loan_type`, `overdue_amount`, `dpd` | Debt facts. **Only put into the prompt after verification** |
| `salt` | Random string used for hashing |
| `pan_last4_hash`, `birth_year_hash` | Scrambled answers. Real values are never stored |
| `do_not_call` | If true, `/calls` refuses to start a call |

**How verification uses it:** hash the typed code with the customer's salt and compare with both stored hashes. A match with either counts.

**`call_sessions`** (the live status board of a call): `state`, `verified`, `verify_attempts`, `warnings_given`, `silence_count`, `ptp_logged`, `disposition`, `history`, `started_at`, `ended_at`.

**`call_events`** (the logbook). Append only: never edit, never delete.

| `type` | When written | Example payload |
|---|---|---|
| `VERIFY` | Each verification attempt | `{"success": false, "attempt": 1}` (never the code) |
| `PTP` | Promise logged | `{"ptp_id": "PTP-4821", "ptp_date": "2026-10-23", "amount": 8499}` |
| `ESCALATION` | Human handoff | `{"ticket_id": "ESC-3310", "reason": "DISPUTE"}` |
| `DISPOSITION` | Call ended | `{"status": "PTP_AGREED", "notes": ""}` |
| `BLOCKED_TOOL` | LLM tried a forbidden tool | `{"tool": "log_promise_to_pay", "state": "GREETING"}` |

**Why a separate events table?** The session shows *current* status. Events show *what happened and when*. That is your audit trail and the source for metrics.

**Rows after a good call**

```text
call_sessions:
  id=ab12..  state=ENDED  verified=1  verify_attempts=1  ptp_logged=1  disposition=PTP_AGREED

call_events:
  1  VERIFY        {"success": true, "attempt": 1}
  2  PTP           {"ptp_id": "PTP-4821", "ptp_date": "2026-10-23", "amount": 8499}
  4  DISPOSITION   {"status": "PTP_AGREED", "notes": ""}
```

---

# 11. Call processing, recordings, agent management

## What a real call pipeline does

| Stage | What happens | Typical owner |
|---|---|---|
| Before | Pick customers, check allowed calling hours and DNC | Scheduler / dialer |
| Connect | Dial, play the first message | Telephony platform |
| Loop | STT, LLM, tools, TTS, repeated | Platform plus your server |
| Recording | Audio saved (needs consent and legal review) | Platform |
| Transcript | Text version of the call | Platform or your DB |
| After | Disposition, metrics, escalation queue, QA scoring | Your backend |

Platforms such as Vapi offer recording and transcripts. Check their current docs and your legal needs before enabling anything.

## What a real voice call looks like

```text
Customer's phone
      │ speaks
      ▼
 Telephony (Vapi) ──► STT: audio → text
                            │
                            ▼
                      LLM (+ system prompt, history, tools)
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
      plain reply text              tool call request
            │                               │
            │                     your server runs the tool
            │                     (webhook), returns the result
            │                               │
            │                     LLM writes the final reply
            ▼                               ▼
              TTS: text → audio ──► Customer hears Maya
```

Version 1 replaces "STT and TTS" with typing and reading. The brain, rules and logging are identical.

## What Version 1 stores

| Data | Where |
|---|---|
| Transcript (recent) | `call_sessions.history` |
| Actions | `call_events` |
| Outcome | `call_sessions.disposition` plus a `DISPOSITION` event |
| Audio | not stored (no audio exists) |

## Possible upgrades

1. A `call_messages` table (one row per message) for full transcripts.
2. In a voice version, store the platform's recording URL on the call session.
3. A post-call job that scores each call (did Maya follow the rules?).

## "Agent" means three things

| Meaning | In this project |
|---|---|
| **AI agent (Maya)** | Model + system prompts + tools + guardrails |
| **Human agent** | Receives escalations (we only create a ticket id) |
| **Agent configuration** | The files you edit to change behaviour |

| I want to change... | Edit |
|---|---|
| Tone or wording | `prompts.py` |
| Which tools exist | `state_machine.py` (`Tool`) and `tools.py` |
| Which tools are allowed where | `ALLOWED_TOOLS` |
| Limits (waiver %, attempts, dates) | `config.py` |
| Forbidden words | `FORBIDDEN_PRE_AUTH` in `guardrails.py` |
| DNC phrases / abusive words | `guardrails.py` |
| LLM model | `.env` (`GROQ_MODEL`) |
| Customers | `seed.py` or the DB |

**Multi-customer safety:** each call is tied to one customer by `customer_id`. The LLM never supplies an account id, so it **cannot** touch another customer's data.

---

# 12. One turn, end to end

## Who talks to whom

```text
Client        FastAPI(main)       engine          DB            Groq LLM        tools
  │ POST /turn ──►│                  │             │               │              │
  │               │ get_db() ─────────────────────►│ open workspace│              │
  │               │ db.get(CallSession) ──────────►│ row           │              │
  │               │ handle_turn ────►│             │               │              │
  │               │                  │ precheck ───► (counters)    │              │
  │               │                  │ build_messages              │              │
  │               │                  │ llm_round ──────────────────►│              │
  │               │                  │◄────────────── tool_calls ──│              │
  │               │                  │ execute_tool ───────────────────────────────►│
  │               │                  │             │◄── write event + commit ──────│
  │               │                  │ llm_round ──────────────────►│              │
  │               │                  │◄────────────── plain text ──│              │
  │               │                  │ finalize ───► commit history│              │
  │◄──── JSON ────│◄─────────────────│             │               │              │
```

## The turn as a flowchart

```text
handle_turn(db, session, user_text)
 │
 ├─ precheck()      (pure code, no LLM)
 │     already ended?  → "This call has already ended."
 │     silence?        → re-prompt, or end NO_RESPONSE on the 2nd
 │     DNC phrase?     → end DO_NOT_CALL
 │     abusive?        → warn, or end TERMINATED_ABUSE on the 2nd
 │     else            → None (continue)
 │
 ├─ build_messages()   (state-specific system prompt + last 20 messages + new message)
 │
 ├─ loop up to 4 times:
 │     llm_round()
 │        tool calls?  → execute_tool() each → rebuild system prompt → loop again
 │        plain text?  → that is the reply → exit loop
 │
 └─ finalize()
       not verified?    → output filter may replace the reply
       GREETING state?  → move to VERIFYING
       save history, commit, return TurnResult
```

---

# 13. Annotated code

## `state_machine.py` (read this first)

```python
class State(str, Enum): ...        # the 4 stages
class Tool(str, Enum): ...         # the 5 tool names

ALLOWED_TOOLS = {
    State.GREETING:    {Tool.VERIFY_CUSTOMER, Tool.MARK_DISPOSITION},
    ...
}
TRANSITIONS = {
    (State.GREETING, "turn_done"): State.VERIFYING,
    ...
}

def next_state(state, event):
    return TRANSITIONS.get((state, event), state)
```

- `ALLOWED_TOOLS` is a lookup: *"in this state, these tools."* Values are **sets** (unordered, no duplicates).
- `TRANSITIONS` is a lookup: *"from this state, on this event, go there."* The key is a **tuple** `(state, event)`.
- `next_state` returns the new state, or the **same** state if the pair isn't listed (the illegal-transition rule).

## `execute_tool` (the gatekeeper)

```python
def execute_tool(db, s, name, raw_args):
    try:
        tool = Tool(name)                       # 1. real tool name?
    except ValueError:
        return {"ok": False, "error": f"Unknown tool: {name}"}

    if tool not in ALLOWED_TOOLS[State(s.state)]:   # 2. allowed right now?
        log_event(db, s, "BLOCKED_TOOL", {...})
        db.commit()
        return {"ok": False, "error": "..."}

    try:
        return HANDLERS[tool](db, s, raw_args)      # 3. run the handler
    except ValidationError as e:                    #    (Pydantic checks inside)
        return {"ok": False, "error": f"Invalid arguments: {str(e)[:300]}"}
```

- `Tool(name)` raises `ValueError` for unknown strings, and we catch it.
- `HANDLERS[tool]` is a dict from tool to function: a *dispatch table*, the clean alternative to a long if/elif chain.
- `str(e)[:300]` keeps the error text short for the LLM.

## `_verify` (a typical handler)

```python
args = VerifyArgs.model_validate(raw)      # shape check (4 digits)
s.verify_attempts += 1                     # count the try
h = hash_code(args.verification_code, c.salt)
ok = compare(h, pan_hash) or compare(h, birth_year_hash)
log_event(... {"success": ok, "attempt": n})   # NEVER the code
if ok:      s.verified = True; state → NEGOTIATING
elif n >= 2: end_call(FAILED_AUTH)
else:       tell the LLM attempts_left
```

## `precheck` (rules without the LLM)

```text
ended?          → canned reply
empty text?     → silence_count += 1; second silence → NO_RESPONSE
DNC regex?      → DO_NOT_CALL
abusive word?   → warnings_given += 1; second → TERMINATED_ABUSE
else            → None
```

- Returns a **string** when the turn is fully handled, and `None` when the LLM should continue. Callers test `if reply is None:`.
- Order matters: silence is checked before DNC, because empty text can't match a phrase.

## `llm_round` (one LLM call)

```python
response = llm(messages, schemas_for_state(State(s.state)))
msg = response.choices[0].message
if not msg.tool_calls:                       # plain text → done
    return (msg.content or "").strip(), messages
# otherwise: record the assistant's tool request, run each tool,
# append the results, replace messages[0] with a fresh system prompt
return None, messages                        # None = "not finished, loop again"
```

- `choices[0].message` is how OpenAI-style APIs return the answer.
- Returning `(None, messages)` tells the loop to continue. `(text, messages)` means done.

## `finalize`

```text
reply empty?            → use the fallback sentence
not verified?           → sanitize (output filter)
state is GREETING?      → state = VERIFYING
append user+assistant   → history (keep last 40)
commit
return TurnResult(reply, state, ended, disposition)
```

---

# 13A. Regex in guardrails.py, explained

A **regex** (regular expression) is a pattern language for finding text. The output filter and DNC detector depend on it.

```python
FORBIDDEN_PRE_AUTH = re.compile(
    r"\b(overdue|loans?|emis?|outstanding|dues?|owes?|owed|dpd|payments?|amount|rupees?)\b"
    r"|₹|\brs\.?\s*\d|\d{4,}",
    re.IGNORECASE,
)
```

The two strings side by side are joined by Python into one pattern. Read the pattern as **four alternatives separated by `|` (OR)**:

1. `\b(overdue|loans?|...)\b`: any of these whole words
2. `₹`: the rupee symbol
3. `\brs\.?\s*\d`: "rs", then an optional dot, optional spaces, then a digit
4. `\d{4,}`: four or more digits in a row

| Piece | Meaning | Example |
|---|---|---|
| `r"..."` | Raw string: backslashes are kept as typed | `r"\b"` |
| `\b` | Word boundary (start or end of a word) | `\bemi\b` matches "EMI" but **not** "premium" |
| `(a\|b\|c)` | Any one of these | `(overdue\|dues?)` |
| `?` | Previous character is optional | `loans?` matches loan and loans |
| `\.` | A real dot (`.` alone means "any character") | `rs\.?` |
| `\s*` | Zero or more spaces | "Rs. 8499" |
| `\d` | One digit | `\d{4,}` is 4 or more digits |
| `re.IGNORECASE` | Ignore capital letters | "EMI" equals "emi" |

**Try it**

| Reply text | Flagged? | Why |
|---|---|---|
| "Your EMI is pending" | Yes | word `emi` |
| "You owe us Rs. 8,499" | Yes | `owe` and `rs` followed by a digit |
| "Your amount is ₹8,499" | Yes | `amount` and `₹` |
| "Please share your PAN digits" | No | no forbidden word, no 4-digit run |
| "premium plan" | No | `\b` stops a match inside "premium" |
| "Call me on 9876543210" | Yes | 4+ digits. This is a **false positive**, and failing closed is the safe direction |

**DNC pattern**

```python
DNC_RE = re.compile(
    r"\b(stop calling|do not call|don[’']?t call|never call|remove my number|call mat kar\w*)\b",
    re.IGNORECASE,
)
```
- `[’']` matches either kind of apostrophe, so "don't" and "don’t" both work.
- `kar\w*` matches kar, karo, karna (`\w*` is zero or more letters).
- "Please stop calling me" matches. "I am calling about my bill" does not.

**Use `.search`, not `.match`.** `.search` looks anywhere in the text. `.match` only checks the start, so a leak in the middle of a sentence would slip through. `bool(pattern.search(text))` turns the result into True or False.

**Limits:** word lists miss new phrasings and sometimes flag harmless text. That is why they sit behind other layers.

Try it in a Python shell:
```python
from app.guardrails import leaks_debt_info, DNC_RE
print(leaks_debt_info("Your EMI is pending"))          # True
print(leaks_debt_info("premium plan"))                 # False
print(bool(DNC_RE.search("Please stop calling me")))   # True
```

---

# 13B. How Pydantic models become tool schemas

One class does **two jobs**: it validates the arguments, and it describes them to the LLM.

```python
class PTPArgs(BaseModel):
    ptp_date: date = Field(description="Promised payment date, ISO-8601 (YYYY-MM-DD)")
    amount: int = Field(gt=0, description="Promised amount in rupees")
```

| Part | Validation job | What the LLM sees |
|---|---|---|
| `ptp_date: date` | Accepts "2026-10-23", rejects "next friday" | `"type": "string", "format": "date"` |
| `amount: int` | Whole number | `"type": "integer"` |
| `Field(gt=0)` | Must be greater than 0 | `"exclusiveMinimum": 0` |
| `Field(description=...)` | none | The text itself. **It guides the LLM** |
| `Literal["SMS", "WHATSAPP", "EMAIL"]` | Only these strings | An allowed-values list |
| `Field(pattern=r"^\d{4}$")` | Exactly 4 digits | The same pattern |

**The pipeline**

```text
Pydantic class ──model_json_schema()──► JSON Schema ──wrapped in {"type":"function",...}──► sent to the LLM
LLM's arguments (JSON string) ──json.loads──► dict ──Model.model_validate(dict)──► checked object or ValidationError
```

**How `tools.py` builds the tool list**

```python
TOOL_SPECS = {
    Tool.VERIFY_CUSTOMER: ("description text", VerifyArgs),
    Tool.LOG_PTP:         ("description text", PTPArgs),
    ...
}

def schemas_for_state(state):
    return [ {"type": "function", "function": {
                "name": t.value,
                "description": TOOL_SPECS[t][0],
                "parameters": TOOL_SPECS[t][1].model_json_schema()}}
             for t in sorted(ALLOWED_TOOLS[state], key=lambda t: t.value) ]
```
It loops over only the tools **allowed in this state**, so the LLM never sees the others. `sorted(...)` just keeps the order stable.

**What validation does with messy input**

| Input | Result |
|---|---|
| `{"ptp_date": "2026-10-23", "amount": 8499}` | OK |
| `{"ptp_date": "2026-10-23", "amount": "8499"}` | OK. The string is converted to the number 8499 |
| `{"ptp_date": "next friday", "amount": 8499}` | `ValidationError` (not a date) |
| `{"ptp_date": "2026-10-23", "amount": -5}` | `ValidationError` (must be greater than 0) |
| `{"amount": 8499}` | `ValidationError` (`ptp_date` missing) |

**The `_to_str` validator in `VerifyArgs`:** `mode="before"` means it runs **before** the type check. If the LLM sends the number `1234` instead of the string `"1234"`, the validator converts it first, so the 4-digit pattern check still works.

Try it:
```python
from app.tools import PTPArgs
print(PTPArgs.model_validate({"ptp_date": "2026-10-23", "amount": "8499"}))
print(PTPArgs.model_json_schema())
```

---

# 13C. Prompts: how the text is assembled

`prompts.py` builds the prompt from **templates** using `.format()`.

```python
NEGOTIATING.format(loan_type="Personal Loan", amount=8499, dpd=12, ptp="no", today="2026-10-18")
```

| Template piece | Result |
|---|---|
| `{loan_type}` | replaced by "Personal Loan" |
| `₹{amount:,}` | `:,` adds thousands separators, so 8499 becomes `₹8,499` |
| `{{` and `}}` | A literal brace. A stray single `{` in prompt text causes a `KeyError` or `ValueError` |

**Two-step build for pre-verification stages:** `STAGE_NOTES[state].format(name=...)` fills the name in the notes first. The result is then inserted into the `{stage_notes}` slot of `PRE_AUTH`.

**The final prompt is `PERSONA` + a state-specific part.** What the LLM actually sees:

*Before verification* (names the forbidden topics but has **none of the actual facts**):
```text
You are Maya, a calm, polite and professional voice agent calling on behalf of Kapture Finance.
Keep every reply short (1-3 sentences) because this is a phone call. ...

CURRENT STAGE: GREETING
The customer's name is Rahul Sharma. You have NOT verified who you are speaking to.
HARD RULES:
- Do not mention loans, EMIs, dues, amounts, payments or any financial detail. You do not have that information yet.
...
```

*After verification:*
```text
CURRENT STAGE: NEGOTIATING. The customer's identity is verified.
Account facts: Personal Loan, overdue amount ₹8,499, 12 days past due.
Promise to pay already logged in this call: no.
Today's date is 2026-10-18.
Steps: 1. Politely state the overdue amount ...
```

**Why today's date is in the prompt:** the LLM has no clock. To turn "Friday" into `2026-10-23`, it needs to know today.

**Prompt-writing rules used here**
- Short, direct sentences.
- Say what **to do**, not only what not to do.
- Numbered steps for the main flow.
- Tell it how to react to tool errors ("follow its instruction").
- Don't rely on the prompt for rules that must never fail. Those go in code.

Print the rendered prompt for each state to see what the LLM sees:
```python
from app.prompts import build_system_prompt
print(build_system_prompt(session))   # session = a CallSession object
```

---

# 13D. main.py: routes, dependencies and metrics

| Piece | What it does |
|---|---|
| `lifespan` + `yield` | Code before `yield` runs at **startup** (creates tables). Code after runs at shutdown (nothing here) |
| `@app.post("/calls")` | Registers the function as the handler for `POST /calls` |
| `body: StartCall` | FastAPI reads the JSON body and validates it with that Pydantic model. Bad body leads to an automatic 422 error |
| `db: Session = Depends(get_db)` | FastAPI runs `get_db()` and passes the DB workspace in |
| `session_id: str` | Taken from the URL path `{session_id}` |
| `db.scalar(select(...).where(...))` | Runs a query and returns the first result, or `None` |
| `db.get(CallSession, session_id)` | Fetch one row by primary key, or `None` |
| `HTTPException(404, "...")` | Returns an error response immediately |
| `Header(default="")` | Reads the `X-API-Key` header (underscores in the name become hyphens) |
| `dependencies=[Depends(require_key)]` | Runs the key check **before** the route. If it fails, the route never runs |
| plain `def`, not `async def` | FastAPI runs normal functions in a thread pool. That is fine for our blocking DB and LLM calls |

**The `/metrics` query**

```python
select(CallSession.disposition, func.count()).group_by(CallSession.disposition)
```
is the SQL `SELECT disposition, COUNT(*) FROM call_sessions GROUP BY disposition`. It returns rows like:

```text
("PTP_AGREED", 2)   ("FAILED_AUTH", 1)   (None, 1)
```
`None` means the call isn't finished, so the code renames it `IN_PROGRESS`.

**Worked example:** counts are `PTP_AGREED: 2`, `FAILED_AUTH: 1`, `IN_PROGRESS: 1`.
- `total_calls` = 4, `completed_calls` (`done`) = 3
- `ptp_rate` = 2 / 3 = 0.667
- `auth_failure_rate` = 1 / 3 = 0.333
- `containment_rate` = 1 − (escalated / done) = 1 − 0 = 1.0, where escalated means `DISPUTED` plus `HARDSHIP_ESCALATED`

Rates divide by **completed** calls, so unfinished calls don't distort them.

---

# 13E. Hashing and masking in security.py

```python
def hash_code(code, salt):
    return hashlib.sha256((salt + code).encode()).hexdigest()
```
- Joins salt and code, turns the text into bytes (`.encode()`), runs SHA-256, and returns 64 hex characters.
- **Same input gives the same output**, and you can't run it backwards directly.
- The **salt** is random text stored per customer. Two customers with the same PAN digits get different hashes, so one pre-computed table can't crack everyone.
- Weakness: there are only 10,000 possible 4-digit codes, so a stolen hash can be brute-forced. That's fine for a demo and a limit to mention (glitch 23).
- `hmac.compare_digest(a, b)` compares in constant time, so the response time doesn't leak how many characters matched. It's a small habit, but a good one.
- `secrets.token_hex(8)` (in `seed.py`) makes the salt: 16 random hex characters.

```python
def mask_name(name):
    parts = name.split(" ")
    return " ".join(p if i == 0 else p[0] + "*" * max(len(p) - 1, 1) for i, p in enumerate(parts))
```
- Keep the first word, and for every other word keep only the first letter plus stars.
- "Rahul Sharma" becomes "Rahul S*****" (Sharma = S + 5 stars).

```python
from app.security import hash_code, mask_name
print(hash_code("1234", "abcd"))                                   # 64 hex characters
print(hash_code("1234", "abcd") == hash_code("1234", "abcd"))      # True
print(hash_code("1234", "wxyz") == hash_code("1234", "abcd"))      # False (different salt)
print(mask_name("Rahul Sharma"))                                   # Rahul S*****
```

---

# 13F. LangGraph in plain words

**LangGraph** lets you describe a flow as a **graph** instead of a chain of function calls. `graph.py` does exactly what `handle_turn` does, only drawn as a graph.

| Term | Meaning | In `graph.py` |
|---|---|---|
| **State** | A dictionary that travels through the graph | `TurnState` (`user_text`, `messages`, `reply`, `rounds`) |
| **Node** | A function: takes the state, returns the keys it changed | `n_precheck`, `n_llm`, `n_finalize` |
| **Edge** | An arrow: "after A, run B" | `add_edge(START, "precheck")` |
| **Conditional edge** | A function decides which arrow to follow | `after_precheck`, `after_llm` |
| **START / END** | Entry and exit points | |
| **compile()** | Turns the description into something runnable | `g.compile()` |
| **invoke()** | Runs it once and returns the final state | `graph.invoke({"user_text": "..."})` |

**Our graph**

```text
START → precheck ──(canned reply ready)──────────────► finalize → END
            │
        (continue)
            ▼
          llm ◄─────┐
            │       │ tool ran, no text yet, rounds < 4
            ├───────┘
            ▼ text reply, or rounds ≥ 4
         finalize → END
```

**How the state changes for the turn "1234"**

```text
start:          {"user_text": "1234"}
after precheck: {... "messages": [...], "reply": None, "rounds": 0}
after llm #1:   {... "reply": None, "messages": [... + tool result], "rounds": 1}   (tool ran)
after llm #2:   {... "reply": "Thank you, Rahul...", "rounds": 2}                    (text)
after finalize: {... "reply": "<filtered reply>"}
```
A node returns only the keys it changes, and LangGraph merges them into the state.

**Why `db` and `session` aren't in the state:** `build_graph(db, session, llm)` defines the node functions **inside** itself, so they can read `db` and `session` from the enclosing function (a **closure**). The graph state carries only simple data.

**Why `TypedDict, total=False`:** it describes a dictionary with known keys, and `total=False` makes every key optional, since early nodes don't have all of them yet.

**Do you need it?** No. It adds no new behaviour. Its value is a visible flow, an easy place to add steps later, and a good talking point. Learn `handle_turn` first.

If your LangGraph version supports it, `graph.get_graph().draw_mermaid()` prints a diagram you can compare with the one above.

---

# 13G. Small helpers and startup details

**`config.py` and `.env`**
- `load_dotenv()` reads your `.env` file into environment variables. `os.getenv("NAME", default)` reads one.
- Values are read **once, when the file is imported**. After editing `.env`, **restart the server**.

**`Base.metadata.create_all(engine)`**
- Creates tables for every model class **that has been imported**. If `app.models` is never imported before this runs, it creates nothing. `main.py` and `seed.py` import the models, so it works.

**`start_call(db, customer)`**
- Creates the call row in `GREETING` with the opening line already in `history`, saves it, and returns `(session, opening)`. Setting `session.customer = customer` avoids an extra query.

**`log_event` vs `end_call`**
- `log_event(...)` only **queues** a new event (`db.add`). It doesn't save.
- The handler that called it runs `db.commit()`. `end_call` commits itself.

**`TurnResult`**
- A small dataclass that `handle_turn` returns: `reply`, `state`, `ended`, `disposition`. `main.py` turns it into the JSON response.

**`Callable[..., dict]` in `tools.py`**
- A type hint meaning "any function that returns a dict". It is only documentation for readers and editors.

---

# 14. Data journeys

## Journey 1: the verification code `1234`

```text
1. Customer types "1234"
2. chat_cli → POST /calls/{id}/turn  {"text": "1234"}
3. FastAPI validates the body (Turn model), loads the call row
4. precheck: not silence / DNC / abusive
5. build_messages: the code is now inside the messages list
6. LLM decides: tool_calls → verify_customer {"verification_code": "1234"}  (arguments is a JSON string)
7. json.loads → dict
8. execute_tool: tool is real ✓, allowed in this state ✓
9. VerifyArgs.model_validate: exactly 4 digits ✓
10. hash_code("1234", salt) → compared with stored hashes ✓
11. call_events gets {"success": true, "attempt": 1}      ← the code is NOT stored here
12. state → NEGOTIATING, verified = True, commit
13. history saves "1234" as part of the chat (note: it IS in history)
```
> Honest note: the typed digits are in `history` (step 13) because history stores what the customer said. A real system would redact it. That is a good "next improvement" talking point.

## Journey 2: the overdue amount `8499`

```text
customers.overdue_amount = 8499          (database)
   │
   ├─ NOT verified → never leaves the database (prompt has no amount)
   │
   └─ verified → build_system_prompt formats "₹8,499" into the NEGOTIATING prompt
          → LLM sees it → LLM includes it in the reply
          → finalize: verified = True so the filter is skipped
          → customer reads "₹8,499"
```

## Journey 3: a promise "Friday"

```text
Customer: "I'll pay Friday"
Prompt contains: "Today's date is 2026-10-18"
LLM converts → ptp_date "2026-10-23", amount 8499
Server validates:
   date within 0..30 days?   ✓
   amount ≤ overdue?         ✓
   amount ≥ 90% of overdue?  ✓
Event PTP written, ptp_logged = True, id "PTP-####" returned
```
> The LLM does the *language* work (Friday means a date). The code does the *checking*.

---

# 15. Worked scenarios (with database state)

## Scenario 1: happy path

| Turn | Customer says | What happens | State after | Events added |
|---|---|---|---|---|
| 0 | (call starts) | Opening line | GREETING | none |
| 1 | "Yes, speaking" | Maya asks for PAN digits or birth year | VERIFYING | none |
| 2 | "1234" | verify succeeds, debt stated | NEGOTIATING | `VERIFY` |
| 3 | "I'll pay in 3 days" | PTP logged | NEGOTIATING | `PTP` |
| 4 | "Thanks, bye" | `mark_disposition(PTP_AGREED)` | ENDED | `DISPOSITION` |

## Scenario 2: pushing for the amount early

Customer: "Just tell me the amount."

- Layer 1: the prompt has no amount, so the LLM can't state it.
- Layer 3: if the LLM guesses with "overdue" or "₹", the reply becomes *"For your security I need to verify your identity first..."*

## Scenario 3: wrong codes

| Attempt | Result | Call row |
|---|---|---|
| "0000" | `attempts_left: 1`, Maya asks again | `verify_attempts=1` |
| "1111" | code runs `end_call(FAILED_AUTH)` | `state=ENDED, disposition=FAILED_AUTH` |

## Scenario 4: low payment

| Step | Detail |
|---|---|
| Customer: "I'll pay ₹6,000" | LLM calls `log_promise_to_pay(6000)` |
| Server computes the minimum | 90% of 8499 = 7649.1, so 6000 is below it |
| Server returns | `{"ok": false, "must_escalate": true}` |
| LLM follows the error | Calls `escalate_to_agent` |

## Scenario 5: "stop calling me"

`precheck` matches the DNC pattern, so there is **no LLM call**. `end_call(DO_NOT_CALL)` runs and `customer.do_not_call = True`. The next `POST /calls` for that customer returns 403.

## Scenario 6: wrong person

Before verification there are no debt facts in the prompt. The LLM calls `mark_disposition(WRONG_PERSON)` and says goodbye. Nothing sensitive was ever available to reveal.

---

# 16. Recap card

```text
Customer text
  → precheck           silence / DNC / abuse                       [code]
  → prompt for the CURRENT STATE (no debt facts until verified)
  → LLM sees ONLY the tools allowed in this state
  → tool calls → execute_tool: real? allowed? valid? business rules? → DB + event log
  → output filter (if unverified)                                   [code]
  → save call row + history → reply

States:  GREETING → VERIFYING → NEGOTIATING → ENDED
Only way into NEGOTIATING: successful verify_customer
Tables:  customers (who) · call_sessions (status board) · call_events (logbook)
Rule:    LLM for language, code for rules
```