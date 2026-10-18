# EMI Due Reminder Agent: Build and Debug Guide (Do the Project)

**Purpose of this file:** the practical companion to `CONCEPTS.md`. Use it **while coding, testing, debugging and reviewing**: build order with checkpoints, reference tables, tests, debugging tools, known glitches, patches, change checklists, exercises, and review questions. Agent persona: Maya Guard.

**Companion file:** `CONCEPTS.md` explains the *why*: terms, state machine, tool calling, schema, data flow. When a word here is unfamiliar, look it up there (section 4).

> **Honest note:** the Version 1 code was designed and traced by hand, not executed. Expect small errors on the first run. Section 6 lists the likely ones, and section 7 has patches to apply.

---

## Table of contents

0. How to work with this guide
1. Project map (folders, who imports whom, function cheat sheet)
2. Build order with checkpoints
3. Reference tables (endpoints, constants, customers, dispositions, events, commands)
4. Testing guide
5. Debugging toolkit
6. Glitches and gotchas
7. Patches
8. Change checklists
9. Exercises
10. Review checklist and teach-back
11. Interview Q&A
12. Limits and roadmap
13. Quick card

---

# 0. How to work with this guide

**Daily workflow**

1. Pick the next step in section 2.
2. Open the matching concept section in `CONCEPTS.md` if you are unsure *why*.
3. Write the code. Run the checkpoint test.
4. If something breaks, go to section 5, then section 6.
5. Before moving on, tick the checkpoint.

**Three habits that save hours**

- Run `python -m pytest -q` after **every** file you finish.
- Read `call_events` and the call row **before** guessing at a bug.
- Don't write the LLM code until the tool and state-machine tests pass. They need no LLM.

---

# 1. Project map

## Folders

```text
EMI-Due-Reminder-Agent/
├── app/
│   ├── __init__.py
│   ├── config.py          constants (limits, model name, keys)
│   ├── security.py        hash_code(), mask_name()
│   ├── db.py              database connection + session factory
│   ├── models.py          tables: Customer, CallSession, CallEvent
│   ├── state_machine.py   states, tools, allowed-tools table, transitions
│   ├── tools.py           5 tool handlers + validation + execute_tool + end_call
│   ├── guardrails.py      forbidden-word filter, DNC regex, abuse list
│   ├── prompts.py         state-specific system prompts
│   ├── llm.py             Groq call
│   ├── engine.py          the turn pipeline (start_call, handle_turn, ...)
│   ├── graph.py           optional LangGraph version of the same pipeline
│   ├── seed.py            demo customers
│   └── main.py            FastAPI endpoints
├── tests/
│   ├── __init__.py
│   ├── helpers.py         ScriptedLLM, text(), tool()
│   ├── conftest.py        fixtures: db, customer, call, verified_call
│   ├── test_state_machine.py
│   ├── test_tools.py
│   ├── test_guardrails.py
│   └── test_scenarios.py
├── chat_cli.py            terminal test client
├── pytest.ini
├── requirements.txt
└── .env.example
```

## Who imports whom

```text
main → engine → tools → models → db
              → prompts
              → guardrails
              → llm
state_machine and config are used by many
```

## Function cheat sheet

| Function | File | Job |
|---|---|---|
| `start_call` | engine | Create the call row and return Maya's opening line |
| `precheck` | engine | Handle silence, DNC, abuse without the LLM |
| `build_messages` | engine | System prompt + recent history + new message |
| `llm_round` | engine | One LLM call. If tools were asked, run them |
| `finalize` | engine | Output filter, state step, save history |
| `handle_turn` | engine | Runs the steps above in order |
| `execute_tool` | tools | Validate then run one tool safely |
| `end_call` | tools | Set ENDED, save disposition, log the event |
| `log_event` | tools | Add one row to `call_events` (no commit) |
| `schemas_for_state` | tools | Tool list shown to the LLM in this state |
| `build_system_prompt` | prompts | Picks the right prompt for the state |
| `sanitize_pre_auth_reply` | guardrails | Replace leaking replies |
| `leaks_debt_info` | guardrails | True if text contains forbidden words |
| `next_state` | state_machine | Look up the next state |
| `hash_code` / `mask_name` | security | Scramble a code / hide part of a name |

---

# 2. Build order with checkpoints

| Step | Build | Checkpoint |
|---|---|---|
| 1 | `config`, `security`, `db`, `models` | `python -c "from app.models import *"` works |
| 2 | `seed.py` | `python -m app.seed`, then rows appear in `customers` |
| 3 | `state_machine.py` | `test_state_machine.py` passes |
| 4 | `tools.py` | `test_tools.py` passes |
| 5 | `guardrails.py` | `test_guardrails.py` passes |
| 6 | `prompts.py`, `llm.py`, `engine.py` | `test_scenarios.py` passes |
| 7 | `main.py`, `chat_cli.py` | A full call in the terminal |
| 8 | `/metrics` | Numbers make sense |
| 9 | `graph.py` (optional) | Same behaviour as `handle_turn` |

**Rule:** do not write the LLM parts until the tool and state-machine tests pass.

**Environment setup recap**

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then add GROQ_API_KEY
```

Use Python 3.10 or newer, and run everything from the project root, inside WSL.

---

# 3. Reference tables

## Endpoints

| Method | URL | Purpose | Auth |
|---|---|---|---|
| GET | `/health` | Is the server up | none |
| POST | `/calls` | Start a call. Body `{"account_id": "ACC-88392"}` | none |
| POST | `/calls/{id}/turn` | Send customer text. Empty text means silence | none |
| GET | `/dispositions` | List final outcomes | `X-API-Key` |
| GET | `/metrics` | PTP rate, auth failure rate, containment | `X-API-Key` |

```bash
curl -X POST localhost:8000/calls -H "Content-Type: application/json" -d '{"account_id":"ACC-88392"}'
curl -X POST localhost:8000/calls/<SESSION_ID>/turn -H "Content-Type: application/json" -d '{"text":"Yes speaking"}'
curl -H "X-API-Key: dev-key" localhost:8000/metrics
```
Or open `http://127.0.0.1:8000/docs` and click through.

## Constants (`config.py`)

| Name | Value | Used for |
|---|---|---|
| `MAX_VERIFY_ATTEMPTS` | 2 | Wrong codes before `FAILED_AUTH` |
| `MAX_WAIVER_PERCENT` | 10 | Minimum PTP amount is 90% |
| `MAX_PTP_DAYS_AHEAD` | 30 | Latest allowed promise date |
| `MAX_TOOL_ROUNDS` | 4 | Stops runaway LLM loops |

## Demo customers (`seed.py`)

| Account | Name | Overdue | PAN last 4 | Birth year |
|---|---|---|---|---|
| ACC-88392 | Rahul Sharma | 8499 | 1234 | 1995 |
| ACC-77120 | Priya Nair | 12500 | 5678 | 1990 |

## Tools

| Tool | Allowed in | Key rules |
|---|---|---|
| `verify_customer` | GREETING, VERIFYING | 4 digits, max 2 attempts |
| `log_promise_to_pay` | NEGOTIATING | Date today to +30 days, amount 90 to 100% of overdue |
| `send_payment_link` | NEGOTIATING | Needs a PTP first |
| `escalate_to_agent` | NEGOTIATING | Creates `ESC-####` |
| `mark_disposition` | all but ENDED | Pre-verification statuses are limited. `PTP_AGREED` needs a PTP |

## Dispositions

| Status | Set by | Meaning |
|---|---|---|
| `PTP_AGREED` | LLM tool | Promised to pay (needs a logged PTP) |
| `ALREADY_PAID` | LLM tool | Customer says paid |
| `DISPUTED` | LLM tool | Disputes the debt |
| `HARDSHIP_ESCALATED` | LLM tool | Hardship, sent to a human |
| `WRONG_PERSON` | LLM tool | Not the customer |
| `DO_NOT_CALL` | LLM tool or code | Asked to stop calls |
| `NO_RESPONSE` | LLM tool or code | Silence |
| `FAILED_AUTH` | **code only** | Two wrong codes |
| `TERMINATED_ABUSE` | **code only** | Repeated abuse |

Before verification the LLM may only use: `WRONG_PERSON`, `DO_NOT_CALL`, `NO_RESPONSE`.

## Event types

| Type | Written when |
|---|---|
| `VERIFY` | Each verification attempt |
| `PTP` | Promise logged |
| `PAYMENT_LINK` | Link sent |
| `ESCALATION` | Human handoff |
| `DISPOSITION` | Call ended |
| `BLOCKED_TOOL` | LLM tried a tool not allowed in this state |

## Commands

```bash
source .venv/bin/activate
python -m app.seed
uvicorn app.main:app --reload
python chat_cli.py
python -m pytest -q
python -m pytest -q -x -k leak -s      # stop at first failure, filter by name, show prints
```

---

# 4. Testing guide

## The scripted LLM idea

Real LLMs are unpredictable, so tests use a fake with pre-written answers:

```python
llm = ScriptedLLM(
    tool("verify_customer", {"verification_code": "1234"}),   # LLM call 1
    text("Thank you. Your overdue amount is ₹8,499."),         # LLM call 2
)
handle_turn(db, session, "1234", llm=llm)
```

- If the code calls the LLM **more** times than scripted, you get `IndexError`. That is a **feature**: it proves an LLM call happened when none was expected. The DNC, silence and abuse tests rely on this.
- `llm.calls` records everything sent to the LLM, so tests can inspect the prompts and tool lists.

## What each test file proves

| File | Proves |
|---|---|
| `test_state_machine.py` | `NEGOTIATING` is reachable only through verification. `ENDED` is terminal |
| `test_tools.py` | Tool gating, waiver boundary (7649 rejected, 7650 accepted), date limits, attempt limit, PTP before link, bad arguments don't crash |
| `test_guardrails.py` | Leak detector catches leaks. Abuse detector works |
| `test_scenarios.py` | Whole turns: leak blocked, no debt data in the pre-verification prompt, wrong person, DNC, silence, abuse |

## Test helpers (fixtures)

| Fixture | Gives you |
|---|---|
| `db` | A fresh in-memory database |
| `customer` | Rahul in the DB |
| `call` | A started call (GREETING) |
| `verified_call` | A call already in NEGOTIATING with `verified=True` |

`verified_call` sets `verified` and `state` **by hand**, a shortcut that creates the state/flag mismatch risk (glitch 22).

## How to check an invariant with a test

Example: *"every ended call has exactly one DISPOSITION event"*:

```python
def test_one_disposition_per_ended_call(db, call):
    handle_turn(db, call, "stop calling me", llm=ScriptedLLM())
    from app.models import CallEvent
    n = db.query(CallEvent).filter_by(session_id=call.id, type="DISPOSITION").count()
    assert n == 1
```
(Add `from app.engine import handle_turn` and `from tests.helpers import ScriptedLLM` at the top of that test file.)

## Invariants worth a test each

| # | Invariant |
|---|---|
| I1 | `state == NEGOTIATING` implies `verified == True` |
| I2 | Before verification, the system prompt contains no debt facts |
| I3 | Ended call has `disposition` and `ended_at` |
| I4 | `ptp_logged` means a `PTP` event exists |
| I5 | Exactly one `DISPOSITION` event per ended call |
| I6 | `FAILED_AUTH` and `TERMINATED_ABUSE` are only set by code |
| I7 | A `VERIFY` event never contains the code |

## Testing the real LLM

You can't assert exact wording. Keep a **scenario list** and run it by hand in `chat_cli.py`, checking: *no leaks, correct tool calls, sensible tone.*

| # | Try this | Expect |
|---|---|---|
| 1 | "Yes speaking. Just tell me the amount." | Refusal, no debt words |
| 2 | Wrong code twice | Call ends, `FAILED_AUTH` |
| 3 | `1234`, then "I'll pay in 3 days" | PTP id, payment link, `PTP_AGREED` |
| 4 | Ask for a 20% discount | Escalation, no logged PTP |
| 5 | "Stop calling me" | `DO_NOT_CALL`, no LLM call |
| 6 | Press Enter twice | `NO_RESPONSE` |
| 7 | Same message in Hinglish | Reply in Hinglish, same tool calls |
| 8 | "No, wrong number" | `WRONG_PERSON`, nothing revealed |

Automating this with an "LLM as judge" is a Version 2 and beyond idea.

---

## 4A. How pytest and the scripted LLM actually work

**pytest basics**

| Concept | Meaning |
|---|---|
| Discovery | pytest runs functions named `test_*` in files named `test_*.py` |
| `assert` | A normal Python statement. If it is false, the test fails |
| **Fixture** | A helper that prepares data. A test asks for it by naming it as a **parameter** |
| Fixture chain | `verified_call` asks for `call`, which asks for `db` and `customer`. pytest builds them in order |
| `yield` in a fixture | Code before `yield` is setup. Code after it is cleanup (`db.close()`) |
| `conftest.py` | Fixtures in this file are available to every test automatically, with no import |
| Isolation | Every test gets a **fresh** in-memory database, so tests can't affect each other |
| `StaticPool` | An in-memory SQLite database normally exists per connection. `StaticPool` forces one shared connection, so the tables persist for the whole test |

**What the fake LLM mimics**

| Real Groq response | Fake in tests |
|---|---|
| `response.choices[0].message.content` | `text("...")` sets `content` |
| `message.tool_calls` is empty or `None` | `text(...)` sets `tool_calls=None` |
| `message.tool_calls[0].id` | `tool(..., call_id="call_1")` |
| `message.tool_calls[0].function.name` | `NS(name=...)` |
| `message.tool_calls[0].function.arguments` (a **JSON string**) | `json.dumps(args)` |

`NS` is `SimpleNamespace`, a quick object whose attributes you set freely. `ScriptedLLM` has a `__call__` method, which makes the object **callable like a function**. Each call records its inputs in `self.calls` and returns the next scripted response (`self.responses.pop(0)`).

**Hand trace of one test.** `test_debt_data_absent_from_pre_auth_prompt_and_present_after`:

```text
Setup:  call in GREETING, verified=False.
        ScriptedLLM(tool(verify_customer "1234"), text("Thank you. Your overdue amount is ₹8,499..."))
Call:   handle_turn(db, call, "My PAN ends with 1234", llm=...)

1. precheck        not ended, not silent, no DNC phrase, not abusive          → None
2. build_messages  GREETING prompt (no debt facts) + history + user message
3. loop round 1:   llm_round calls the fake LLM (call #1 is recorded)
                   it returns a tool call → execute_tool("verify_customer"):
                     tool name valid ✓ · allowed in GREETING ✓ · 4 digits ✓
                     hash matches stored hash → VERIFY event, verified=True,
                     state=NEGOTIATING, commit
                   tool result appended, messages[0] replaced with the NEGOTIATING prompt
                   returns (None, messages) → loop again
4. loop round 2:   fake LLM called again (call #2) with the NEGOTIATING tool list → returns text
5. finalize        verified=True → output filter skipped, history saved, TurnResult

Asserts: calls[0] system prompt has no "8,499" · calls[1] has it · tool lists differ ·
         state is NEGOTIATING · the reply contains "8,499"
```

**Why `llm_round` builds a new list (`messages = messages + [...]`)** instead of appending in place: the fake LLM stored a reference to the first list in `calls[0]`. If the code later changed that same list, the recorded "what the LLM saw in call #1" would change too, and your test would be inspecting the wrong thing.

---

# 5. Debugging toolkit

| Tool | How | Use it to |
|---|---|---|
| **Read events** | `sqlite3 maya.db "SELECT session_id,type,payload FROM call_events ORDER BY id;"` | See what the code actually did |
| **Read call rows** | `sqlite3 maya.db "SELECT id,state,verified,verify_attempts,disposition FROM call_sessions;"` | See the live state |
| **Print what the LLM saw** | `print(json.dumps(messages, indent=2))` inside `llm_round` | Check the prompt and history |
| **Print what came back** | `print(msg)` after `msg = response.choices[0].message` | See raw tool calls |
| **See SQL** | `create_engine(..., echo=True)` | Watch every query |
| **Swagger UI** | Open `/docs` | Call endpoints with a form |
| **Pytest flags** | `-x` stop at first failure, `-s` show prints, `-k name` filter, `--pdb` debugger | Isolate failures |
| **Fresh database** | Delete `maya.db`, then `python -m app.seed` | Reset after model changes |

(Install sqlite3 in WSL with `sudo apt install sqlite3` if needed.)

**Debug habit:** always look at `call_events` and the call row **before** guessing.

## Symptom → likely cause

| Symptom | Likely cause | Check |
|---|---|---|
| Debt facts appear before verification | Facts put in the pre-verification prompt | `build_system_prompt` for `GREETING` and `VERIFYING` |
| Verification never succeeds | Hash mismatch (different salt or wrong digits) | `make_customer`, `hash_code`, and that you used the seeded codes |
| "not allowed at this stage" | Wrong state for that tool | `ALLOWED_TOOLS` and `session.state` |
| "Invalid arguments" | LLM sent a wrong type or format | The error text and the tool's schema description |
| History changes not saved | In-place mutation of a JSON column | Reassign instead of `.append` |
| Long or endless loop | LLM keeps calling tools | `MAX_TOOL_ROUNDS` and tool error messages |
| Crash on LLM error | Missing error handling | Patch 7-A |
| Reply replaced with "verify your identity" | Output filter caught a word | `FORBIDDEN_PRE_AUTH`. The reply may have echoed digits |
| `/calls` returns 403 | Customer is on the DNC list | `customers.do_not_call` |
| `No module named 'tests'` | pytest path | `pytest.ini` has `pythonpath = .` and `tests/__init__.py` exists |
| Model not found | Groq model name changed | `GROQ_MODEL` in `.env` |
| Two `/dispositions` rows for one call | Check the `session_id`. There should be one per call | `call_events` |

---

# 6. Glitches and gotchas

| # | Glitch | Where | Symptom | Fix or note |
|---|---|---|---|---|
| 1 | Code was designed, not executed | everything | Small typos or version mismatches | Run tests early. Fix as you go |
| 2 | "session" means three things | engine / db | Confusing variable names | `db` is the notebook, `session` is the call |
| 3 | JSON column mutated in place | `history` | Changes silently not saved | Reassign: `s.history = s.history + [...]` |
| 4 | Defaults are `None` before saving | models | `verify_attempts` is `None` on a new object | Commit first, as `start_call` does |
| 5 | `create_all` doesn't alter tables | `main.py` lifespan | "no such column" after a model change | Delete `maya.db` (dev) or add Alembic |
| 6 | Running from the wrong folder | shell | `No module named 'app'` | Run commands from the project root |
| 7 | Missing `__init__.py` | `app/`, `tests/` | Import errors | Create empty `__init__.py` files |
| 8 | `app.main:app` confusion | uvicorn | "Attribute app not found" | Package `app`, file `main`, object `app` |
| 9 | Provider rejects a malformed tool call | `llm.py` | Crash with an API error (often HTTP 400) | Patch 7-A |
| 10 | Model name retired or renamed | `.env` | "model not found" | Check Groq's current model list |
| 11 | LLM sends the code as a number | `VerifyArgs` | Leading zero lost (`0456` becomes `456`) so validation fails | The LLM retries. Tell it in the prompt to send a string |
| 12 | Relative dates and time zone | `date.today()` | "Tomorrow" is off by a day near midnight | Use an explicit time zone (`zoneinfo`) |
| 13 | Output filter false positives | `FORBIDDEN_PRE_AUTH` | Harmless reply replaced (e.g. echoed digits, the word "payment") | Tune the pattern. Failing closed is the safe direction |
| 14 | Abuse list is crude | `ABUSE_TERMS` | "I'd be a fool not to pay" triggers a warning. Real abuse is missed | Treat it as a placeholder |
| 15 | Few DNC phrases | `DNC_RE` | Missed phrasing in other languages | Extend the list. The LLM's `DO_NOT_CALL` tool is the backup |
| 16 | **Fail-open default** | `build_system_prompt` | A new state you forget to handle falls into the **NEGOTIATING** prompt, so it gets debt facts | Patch 7-C: make the last branch explicit |
| 17 | New state missing from `ALLOWED_TOOLS` | `state_machine.py` | `KeyError` | Add the state to every table (section 8) |
| 18 | **Several tool calls in one LLM message** | `llm_round` | The state can change mid-batch. A request that was invalid when the LLM made it (e.g. `verify_customer` then `log_promise_to_pay` in one message) becomes allowed after verify succeeds | Patch 7-B: snapshot the state before running the batch. (Duplicate `mark_disposition` calls are already blocked, because the first one moves the call to `ENDED`) |
| 19 | Partial commit on crash | tools, `finalize` | Tool effect saved but the turn is missing from history | Commit once at the end of a turn |
| 20 | Race condition | same call, two requests | Lost update | Fine for sequential calls. Use row locks if needed |
| 21 | History is trimmed | `finalize` | LLM forgets old details | Put important facts in flags, not history |
| 22 | `state` and `verified` can disagree | fixtures, manual edits | Prompt and filter behave differently | Update both together. Add an invariant test |
| 23 | 4-digit values are weak even when hashed | `security.py` | Only 10,000 possibilities, so a leaked hash is easy to reverse | Fine for a demo. Real systems verify against the lender's system and limit attempts |
| 24 | In-memory SQLite needs `StaticPool` | `conftest.py` | "no such table" in tests | Keep `poolclass=StaticPool` |
| 25 | Pydantic version mismatch | tools | `model_validate` not found | Use Pydantic v2 (`pip show pydantic`) |
| 26 | Python older than 3.10 | models | Syntax error on `str \| None` | Use Python 3.10 or newer |
| 27 | Groq free-tier rate limit | `llm.py` | HTTP 429 | Wait, slow down, or add retry |
| 28 | Typed code stays in `history` | `finalize` | PAN digits appear in stored chat | Redact before saving (nice improvement) |
| 29 | Graph path doesn't strip text | `graph.py` | Extra spaces reach the LLM | Patch 7-D |
| 30 | WSL vs Windows paths and ports | environment | Can't reach the server | Run everything inside WSL. Use `127.0.0.1` |
| 31 | `create_all` before the models are imported | `main.py`, `seed.py` | No tables get created | Make sure `app.models` is imported before `create_all` |
| 32 | A stray `{` or `}` in prompt text | `prompts.py` | `KeyError` or `ValueError` from `.format()` | Double the braces (`{{ }}`) or avoid them |
| 33 | `.match` used instead of `.search` | `guardrails.py` | Leaks in the middle of a sentence are missed | Use `.search` |
| 34 | `.env` edited while the server runs | `config.py` | New values ignored | Restart the server |
| 35 | Tests inspect `llm.calls`, but code mutates the same list | `llm_round` | Recorded inputs change after the fact | Build a new list instead of appending in place (already done) |

---

# 7. Patches (apply these)

## 7-A. Handle LLM errors (prevents crashes)

In `engine.py`:

```python
from groq import GroqError   # if unavailable in your version, use groq.APIError


def llm_round(db: Session, s: CallSession, messages: list[dict], llm=chat):
    try:
        response = llm(messages, schemas_for_state(State(s.state)))
    except GroqError:
        return FALLBACK_REPLY, messages
    msg = response.choices[0].message
    # ...rest unchanged
```

## 7-B. Safer handling of several tool calls in one message

In `tools.py`, change the signature and the check:

```python
def execute_tool(db, s, name, raw_args, state: State | None = None) -> dict:
    try:
        tool = Tool(name)
    except ValueError:
        return {"ok": False, "error": f"Unknown tool: {name}"}

    current = state or State(s.state)
    if s.state == State.ENDED.value or tool not in ALLOWED_TOOLS[current]:
        log_event(db, s, "BLOCKED_TOOL", {"tool": name, "state": s.state})
        db.commit()
        return {"ok": False, "error": f"Tool {name} is not allowed at this stage."}
    # ...rest unchanged
```

In `engine.py`, inside `llm_round`, take the snapshot **before** the loop over tool calls:

```python
    state_at_request = State(s.state)
    for tc in msg.tool_calls:
        ...
        result = execute_tool(db, s, tc.function.name, args, state=state_at_request)
```

## 7-C. Fail-closed prompt selection

In `prompts.py`, replace the final `return` in `build_system_prompt`:

```python
    if state == State.NEGOTIATING:
        return PERSONA + NEGOTIATING.format(
            loan_type=c.loan_type,
            amount=c.overdue_amount,
            dpd=c.dpd,
            ptp="yes" if s.ptp_logged else "no",
            today=date.today().isoformat(),
        )
    raise ValueError(f"No prompt defined for state {state}")
```

## 7-D. Strip text in the graph version

In `graph.py`, `n_precheck`:

```python
text_in = state["user_text"].strip()
canned = precheck(db, session, text_in)
...
"messages": build_messages(session, text_in),
```

---

# 8. Change checklists (so you don't miss a spot)

## Add a new tool (e.g. `request_callback`)

| # | File | Change |
|---|---|---|
| 1 | `state_machine.py` | Add to the `Tool` enum |
| 2 | `state_machine.py` | Add to `ALLOWED_TOOLS` for the right states |
| 3 | `tools.py` | New `Args` Pydantic model |
| 4 | `tools.py` | Add to `TOOL_SPECS` (description + model) |
| 5 | `tools.py` | Write the `_request_callback` handler |
| 6 | `tools.py` | Add to `HANDLERS` |
| 7 | `prompts.py` | Tell the LLM when to use it |
| 8 | `tests/` | Add tests (allowed, blocked, validation) |

## Add a new state

| # | File | Change |
|---|---|---|
| 1 | `state_machine.py` | Add to `State` |
| 2 | `state_machine.py` | Add to `ALLOWED_TOOLS` (or you get a `KeyError`) |
| 3 | `state_machine.py` | Add `TRANSITIONS` entries |
| 4 | `prompts.py` | Add its prompt (see glitch 16) |
| 5 | `engine.py` / `tools.py` | Trigger the new event somewhere |
| 6 | `tests/` | Reachability and tool tests |

## Add a new disposition

| # | File | Change |
|---|---|---|
| 1 | `tools.py` | Add to the `Literal` in `DispositionArgs` (or handle as system-only) |
| 2 | `tools.py` | Decide if it's allowed before verification (`PRE_AUTH_STATUSES`) |
| 3 | `prompts.py` | Tell the LLM when to use it |
| 4 | `main.py` | Update `/metrics` if it should be counted |
| 5 | `tests/` | Add a test |

## Change a limit (e.g. waiver 10% to 15%)

| # | File | Change |
|---|---|---|
| 1 | `config.py` | Change `MAX_WAIVER_PERCENT` |
| 2 | `tests/test_tools.py` | The boundary test will fail. Update the numbers |
| 3 | `prompts.py` | Check no text still says "10%" |

## Change a model column

| # | Step |
|---|---|
| 1 | Edit `models.py` |
| 2 | Delete `maya.db` (dev) or write a migration |
| 3 | Re-run `python -m app.seed` |
| 4 | Update `seed.py` and tests if the column is required |

---

# 9. Exercises (learn by changing things)

| # | Exercise | What you learn |
|---|---|---|
| 1 | Run all tests. Then **comment out** the `if not s.verified:` filter block in `finalize()` and see `test_misbehaving_llm_cannot_leak_pre_auth` fail. Restore it | What the output filter protects, and how a test catches its removal |
| 2 | Print the full `messages` list for one turn and read it | What the LLM really sees |
| 3 | Complete a call, then read `call_events` and tell the story in your own words | Audit trail thinking |
| 4 | Change the waiver to 15% and fix the tests | Coupling between config and tests |
| 5 | Add a `request_callback` tool using the checklist in section 8 | The full path of a tool |
| 6 | Add the disposition `CALLBACK_REQUESTED` | Enums, literals, metrics |
| 7 | Write a test for invariant I1 (NEGOTIATING implies verified) | Invariant testing |
| 8 | Add a Hinglish DNC phrase to `DNC_RE` and test it | Regex and rule extension |
| 9 | Apply patch 7-B and write a test with `verify_customer` plus `log_promise_to_pay` in one message | Edge-case reasoning |
| 10 | Add a `call_messages` table and store every message | Schema design |
| 11 | Switch `DATABASE_URL` to PostgreSQL and rerun | Portability |
| 12 | Redact digit sequences before saving history (glitch 28) | Privacy thinking |
| 13 | Run the regex snippet from CONCEPTS 13A. Add the word `balance` to `FORBIDDEN_PRE_AUTH` and add a test row for it | How the output filter and its test relate |
| 14 | Print the rendered system prompt for `GREETING`, `VERIFYING` and `NEGOTIATING` and compare them | What changes after verification |
| 15 | Draw the `handle_turn` flow by hand, then compare it with `graph.py` | That the graph is the same logic drawn differently |

---

# 10. Review checklist and teach-back

## Behaviour checklist

- [ ] No path reaches `NEGOTIATING` without successful verification
- [ ] Pre-verification prompt has no debt facts
- [ ] A scripted leak is blocked
- [ ] Two wrong codes lead to `FAILED_AUTH`
- [ ] Waiver boundary: 7649 rejected, 7650 accepted
- [ ] Link can't be sent before a PTP
- [ ] `PTP_AGREED` can't be set without a logged PTP
- [ ] DNC, silence and abuse work without calling the LLM
- [ ] Every ended call has exactly one `DISPOSITION` event
- [ ] LLM errors don't crash a call (patch 7-A)

## Data checklist

- [ ] No plain PAN or birth year in the database
- [ ] Verification codes aren't in events (note: they are in history, glitch 28)
- [ ] `call_events` is append only

## Quality checklist

- [ ] All tests pass
- [ ] README lists the limitations (section 12)
- [ ] You can run the 8-step real-LLM scenario list in section 4

## Teach-back questions

Answer these **out loud without looking**. If you get stuck, re-read the linked section of `CONCEPTS.md`.

1. What is a state machine, and why not just use `if` statements? (CONCEPTS 4.3, 5)
2. What is the only way into `NEGOTIATING`? (CONCEPTS 5)
3. Why is debt data left out of the pre-verification prompt? (CONCEPTS 8)
4. What does `State("GREETING")` do, and what does `.value` do? (CONCEPTS 4.2)
5. What is a tool call, and who actually performs the action? (CONCEPTS 7)
6. Why does `arguments` need `json.loads`? (CONCEPTS 7)
7. Why do we replace `messages[0]` after a tool runs? (CONCEPTS 7)
8. Where is a call's state stored, and why not in memory? (CONCEPTS 9)
9. Why is `history` a bad place for rules? (CONCEPTS 9)
10. What does `commit()` do? What if you never call it? (CONCEPTS 4.4)
11. Why must you reassign a JSON column? (CONCEPTS 10)
12. What is the difference between `state` and `verified`? (CONCEPTS 5)
13. Why does the waiver check live in code and not the prompt? (CONCEPTS 6, 15)
14. What does the scripted LLM prove and not prove? (section 4 here)
15. What is "fail-closed", and where does our code fail open? (CONCEPTS 4.3, glitch 16)

---

# 11. Interview Q&A

**What is the main idea?**
Compliance rules enforced in code, not only in the prompt, because LLMs can be talked out of instructions.

**How do you prevent leaks before verification?**
Three layers: debt data isn't in the prompt, only allowed tools are visible and enforced, and an output filter replaces leaking replies.

**What is a state machine and why use one?**
A system with fixed states and allowed transitions. It makes behaviour predictable and testable.

**Why combine states with flags?**
States keep the diagram small. Flags store details such as attempts and whether a PTP exists.

**How does tool calling work?**
The LLM returns a structured request. Our code checks that it's allowed, validates arguments, performs it, and returns a result. The LLM then writes the reply.

**Why validate LLM output?**
Treat tool arguments like untrusted user input: they can be wrong, missing or malformed.

**Where is state stored and why?**
In the database, so the server is stateless and restart-safe.

**Why an events table?**
It is an append-only audit trail and the source for metrics.

**How do you test code with an LLM inside?**
A scripted fake LLM tests the rules deterministically. Real-model quality is checked with a scenario list.

**Biggest weaknesses?**
Keyword-based abuse and DNC detection, the LLM still converts spoken dates (we validate but can't check intent), 4-digit verification is weak, and there's no auth on `/calls`.

**What would you build next?**
Full transcript table, history redaction, migrations, a stronger abuse classifier, single-transaction turns, and a voice layer.

---

# 12. Limits and roadmap

## Known limits (write these in your README)

- Text only. No audio or recording
- Keyword-based abuse and DNC detection
- No authentication on `/calls`
- `create_all` instead of migrations
- 4-digit verification with hashed storage is weak by nature
- Typed codes remain in stored history
- No concurrency protection
- Not tested against a real LLM in automated tests

## Roadmap

| Version | Goal | When |
|---|---|---|
| 1 | Text agent: states, tools, DB, guardrails, tests | Now |
| 2 | More scenarios, metrics, PostgreSQL, README with diagram, patches from section 7 | After Version 1 passes |
| 3 | Voice layer (browser mic or Vapi web call) | Optional |

---

# 13. Quick card

```text
Build:    config → db/models → seed → state_machine → tools → guardrails → prompts/llm/engine → main/cli
Run:      python -m app.seed · uvicorn app.main:app --reload · python chat_cli.py
Test:     python -m pytest -q          (-x stop first fail · -k name · -s prints)
Debug:    read call_events + call row FIRST · print messages in llm_round · /docs for endpoints
Reset:    delete maya.db → python -m app.seed
Rules:    LLM for language, code for rules · reassign JSON columns · commit your changes
Never:    log verification codes · put debt facts in the pre-verification prompt
```