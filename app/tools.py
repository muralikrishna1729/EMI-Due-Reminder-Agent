import hmac
import secrets
from datetime import date, timedelta
from typing import Callable, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from app import config
from app.models import CallEvent, CallSession, utcnow
from app.security import hash_code, mask_name
from app.state_machine import ALLOWED_TOOLS, State, Tool, next_state

# ---------- Argument schemas (also used to generate the LLM tool schemas) ----------
class VerifyArgs(BaseModel):
    verification_code: str = Field(
        pattern=r"^\d{4}$",
        description="Last 4 digits of PAN, or 4-digit birth year. Send as a string.",
    )
    @field_validator("verification_code", mode="before")
    @classmethod
    def _to_str(cls, v):
        return str(v).strip() if v is not None else v

class PTPArgs(BaseModel):
    ptp_date: date = Field(description="Promised payment date, ISO-8601 (YYYY-MM-DD)")
    amount: int = Field(gt=0, description="Promised amount in rupees")

class EscalateArgs(BaseModel):
    reason: Literal["DISPUTE", "HARDSHIP", "WAIVER_REQUEST", "OTHER"]
    summary: str = ""

class DispositionArgs(BaseModel):
    status: Literal[
        "PTP_AGREED",
        "ALREADY_PAID",
        "DISPUTED",
        "HARDSHIP_ESCALATED",
        "WRONG_PERSON",
        "DO_NOT_CALL",
        "NO_RESPONSE",
    ]
    notes: str = ""

# Statuses the LLM may use before the customer is verified.
PRE_AUTH_STATUSES = {"WRONG_PERSON", "DO_NOT_CALL", "NO_RESPONSE"}

# documentation description and Pydantic argument schema for each tool.
TOOL_SPECS: dict[Tool, tuple[str, type[BaseModel]]] = {
    Tool.VERIFY_CUSTOMER: (
        "Verify the customer's identity. Must succeed before discussing any account detail.",
        VerifyArgs,
    ),
    Tool.LOG_PTP: ("Record the customer's promise to pay.", PTPArgs),
    Tool.ESCALATE: (
        "Hand over to a human agent for disputes, hardship or discount requests.",
        EscalateArgs,
    ),
    Tool.MARK_DISPOSITION: (
        "Record the final outcome of the call. This ends the call.",
        DispositionArgs,
    ),
}
"""
The LLM is only allowed to call tools in the current state, and must provide valid arguments for the tool.
Input: It takes the current state of the call (e.g., State.GREETING, State.VERIFYING, or State.NEGOTIATING).
Output: It returns a list of dictionaries formatted specifically as OpenAI/Groq-compatible tool (function) declarations.
"""
def schemas_for_state(state: State) -> list[dict]:
    """Only the tools allowed in this state are ever shown to the LLM."""
    return [
        {
            "type": "function", # Specifies that this tool is a function call.
            "function": {
                "name": t.value, # The name of the tool (e.g., "verify_customer").
                "description": TOOL_SPECS[t][0], #  text description from TOOL_SPECS  in tools.py
                "parameters": TOOL_SPECS[t][1].model_json_schema(), # converts it into a standard JSON Schema so the LLM knows what arguments it is required to provide.
            },
        }
        for t in sorted(ALLOWED_TOOLS[state], key=lambda t: t.value)
        # ALLOWED_TOOLS Looks up the lookup table in state_machine.py to find the exact set of tool enums permitted in the current state
    ]

# ---------- Helpers ----------


def log_event(db, s: CallSession, type_: str, payload: dict) -> None:
    db.add(CallEvent(session_id=s.id, type=type_, payload=payload))

"""
gracefully wrap up a call session by updating its status, setting timestamps, and logging the final outcome."""
def end_call(db, s: CallSession, status: str, notes: str = "") -> None:
    s.state = next_state(State(s.state), "ended").value
    s.disposition = status   # final outcome, status, or categorization of a call
    s.ended_at = utcnow()
    if status == "DO_NOT_CALL":
        s.customer.do_not_call = True
    log_event(db, s, "DISPOSITION", {"status": status, "notes": notes})
    db.commit()


# ---------- Handlers ----------
def _verify(db, s: CallSession, raw: dict) -> dict:
    # Implementation for verifying customer identity
    args = VerifyArgs.model_validate(raw)
    c = s.customer
    s.verify_attempts +=1
    h = hash_code(args.verification_code, c.salt)
    ok = hmac.compare_digest(h, c.pan_last4_hash) or hmac.compare_digest(
        h, c.birth_year_hash
    )
    log_event(db, s, "VERIFY", {"success": ok, "attempt": s.verify_attempts})
    if ok:
        s.verified = True
        s.state = next_state(State(s.state), "verified").value
        db.commit()
        return {"ok": True, "verified": True, "customer_name": mask_name(c.full_name)}

    if s.verify_attempts >= config.MAX_VERIFY_ATTEMPTS:
        end_call(db, s, "FAILED_AUTH", "Failed verification twice")
        return {"ok": True, "verified": False, "call_ended": True}

    db.commit()
    return {
        "ok": True,
        "verified": False,
        "attempts_left": config.MAX_VERIFY_ATTEMPTS - s.verify_attempts,
    }

def _ptp(db, s: CallSession, raw: dict) -> dict:
    """responsible for validating and recording when a customer agrees to pay their overdue amount by a specific date."""
    a = PTPArgs.model_validate(raw) #ensures ptp_date is a valid date (in YYYY-MM-DD format) and amount is a positive integer.
    c = s.customer #customer profile linked to the current call session
    today = date.today()

    if a.ptp_date < today or a.ptp_date > today + timedelta(days=config.MAX_PTP_DAYS_AHEAD):
        return {"ok": False,
                "error": f"ptp_date must be between today and {config.MAX_PTP_DAYS_AHEAD} days ahead."
        }
    if a.amount > c.overdue_amount: #A customer cannot promise to pay more than their total overdue balance
        return {"ok": False, "error": "Amount is higher than the overdue amount."}

    min_amount = c.overdue_amount * (100 - config.MAX_WAIVER_PERCENT) / 100
    if a.amount < min_amount:
        return {
            "ok": False,
            "error": "Amount is below the allowed limit. Escalate to a human agent.",
            "must_escalate": True,
        }
    ptp_id = f"PTP-{secrets.randbelow(9000) + 1000}"
    s.ptp_logged = True
    log_event(db, s, "PTP", {
        "ptp_id": ptp_id,
        "ptp_date": a.ptp_date.isoformat(),
        "amount": a.amount
    })
    db.commit()
    return {
        "ok": True,
        "ptp_id": ptp_id,
        "confirmed_date": a.ptp_date.isoformat()
    }

def _escalate(db, s: CallSession, raw: dict) -> dict:
    a = EscalateArgs.model_validate(raw)
    ticket = f"ESC-{secrets.randbelow(9000) + 1000}"
    log_event(db, s, "ESCALATION", {"ticket_id": ticket, "reason": a.reason, "summary": a.summary})
    db.commit()
    return {"ok": True, "ticket_id": ticket}

def _disposition(db, s: CallSession, raw: dict) -> dict:
    a = DispositionArgs.model_validate(raw)
    if not s.verified and a.status not in PRE_AUTH_STATUSES:
        return {"ok": False, "error": f"Status {a.status} is not allowed before verification."}
    if a.status == "PTP_AGREED" and not s.ptp_logged:
        return {"ok": False, "error": "Log a promise to pay first."}
    end_call(db, s, a.status, a.notes)
    return {"ok": True, "disposition_logged": a.status, "call_ended": True}

HANDLERS: dict[Tool, Callable[..., dict]] = {
    Tool.VERIFY_CUSTOMER: _verify,
    Tool.LOG_PTP: _ptp,
    Tool.ESCALATE: _escalate,
    Tool.MARK_DISPOSITION: _disposition,
}

def execute_tool(db, s: CallSession, name: str, raw_args: dict) -> dict:
    try:
        tool = Tool(name)
    except ValueError:
        return {"ok": False, "error": f"Unknown tool: {name}"}

    if s.state == State.ENDED.value or tool not in ALLOWED_TOOLS[State(s.state)]:
        log_event(db, s, "BLOCKED_TOOL", {"tool": name, "state": s.state})
        db.commit()
        return {"ok": False, "error": f"Tool {name} is not allowed in state {s.state}"}
    try:
        return HANDLERS[tool](db, s, raw_args)
    except ValidationError as e:
        return {"ok": False, "error": f"Invalid arguments: {str(e)[:300]}"}
