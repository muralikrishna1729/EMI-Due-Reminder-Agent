from pydantic._internal._generics import replace_types
from sqlalchemy import exc
from httpx import request
import json
from dataclasses import dataclass

from groq import GroqError
from sqlalchemy.orm import Session

from app import config
from app.guardrails import DNC_RE, is_abusive, sanitize_pre_auth_reply
from app.llm import chat
from app.models import CallSession, Customer
from app.prompts import build_system_prompt
from app.state_machine import State, next_state
from app.tools import end_call, execute_tool, schemas_for_state

FALLBACK_REPLY = "Sorry, I didn't catch that. Could you please repeat?"

@dataclass
class TurnResult:
    reply:str
    state:str
    ended:bool
    disposition:str | bool


def start_call(db:Session, customer: Customer)-> tuple[CallSession,str]:
    opening = (
         "Hello, this is your EMI reminder service calling. "
        f"Am I speaking with {customer.full_name}?"
    )
    session = CallSession(
        customer_id = customer.id,
        state = State.GREETING.value,
        history = [{"role": "assistant", "content": opening}]
    )
    session.customer = customer
    db.add(session)
    db.commit()
    return session, opening


def precheck(db:Session, s: CallSession, user_text:str)->str | None:
    """Return a canned reply if handled without the LLM; otherwise None."""
    text = (user_text or "").strip()
    if s.state == State.ENDED.value:
        return "This call has already ended."
    
    if not text:
        s.silence_count +=1
        if s.silence_count >=2:
            end_call(db,s, "NO_RESPONSE", "No response after re-prompt")
            return "I'm not able to hear you, so I'll end the call now. Goodbye."
        db.commit()
        return "Hello, are you still there?"
    s.silence_count = 0

    if DNC_RE.search(text):
        end_call(db,s, "DO_NOT_CALL", "Customer asked not to be called")
        return "Understood. We will not call you again. Goodbye."
    if is_abusive(text):
        s.warnings_given+=1
        if s.warnings_given >=2:
            end_call(db, s, "TERMINATED_ABUSE", "Ended after repeated abusive language")
            return "I'm ending this call now. Goodbye."
        db.commit()
        return "I understand this is frustrating, but I'll need us to keep this respectful to continue."
    return None


def build_messages(s:CallSession, user_text:str)->list[dict]:
    system = {"role": "system", "content": build_system_prompt(s)}
    return [system]+ list(s.history)[-20:] + [{"role": "user", "content": user_text}]

def llm_round(db:Session, s:CallSession, messages: list[dict], llm = chat):
    """One LLM call. Returns (reply, messages); reply=None means tools ran."""
    try:
        response = llm(messages, schemas_for_state(State(s.state)))
    except GroqError:
        return FALLBACK_REPLY, messages
    msg = response.choices[0].message
    if not msg.tool_calls:
        return (msg.content or "").strip(), messages
    
    messages = messages + [{
    "role": "assistant",
    "content": msg.content or "",
    "tool_calls": [{
        "id": tc.id,
        "type": "function",
        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
    } for tc in msg.tool_calls],
    }]

    for tc in msg.tool_calls:
        try:
            args = json.loads(tc.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {}
        if not isinstance(args, dict):
            args = {}
        result = execute_tool(db, s, tc.function.name, args)
        messages.append({
            "role": "tool",
            "tool_call_id": tc.id,
            "content": json.dumps(result),
        })

    # Verification or another tool may have changed the session state.
    messages[0] = {"role": "system", "content": build_system_prompt(s)}
    return None, messages

def finalize(db:Session, s:CallSession, user_text:str, reply:str | None)-> TurnResult:
    reply = (reply or "").strip() or FALLBACK_REPLY
    if not s.verified:
        reply = sanitize_pre_auth_reply(reply, call_ended = s.state == State.ENDED.value)
    if s.state == State.GREETING.value:
        s.state = next_state(State.GREETING, "turn_done").value
    s.history = (list(s.history) + [
        {"role": "user", "content": user_text.strip() or "(silence)"},
        {"role": "assistant", "content": reply},
    ])[-40:]
    db.commit()
    return TurnResult(
        reply = reply,
        state = s.state,
        ended = s.state == State.ENDED.value,
        disposition=s.disposition,
    )

def handle_turn(db:Session, s:CallSession, user_text:str, llm= chat)->TurnResult:
    user_text = (user_text or "").strip()
    reply = precheck(db,s, user_text)
    if reply is None:
        messages = build_messages(s, user_text)
        for _ in range(config.MAX_TOOL_ROUNDS):
            reply, messages = llm_round(db,s, messages, llm)
            if reply is not None:
                break
        # If every round ran tools (reply is None), finalize uses FALLBACK_REPLY.
    return finalize(db, s, user_text, reply)


