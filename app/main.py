from email.policy import HTTP
import hmac
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select 
from sqlalchemy.orm import Session

from app import config 
from app.db import Base, engine, get_db
from app.engine import handle_turn, start_call
from app.models import CallEvent, CallSession, Customer

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield

app = FastAPI(title = "EMI Due Reminder Agent", lifespan = lifespan)
@app.get("/health")
def health():
    return {"status": "ok"}

class StartCall(BaseModel):
    account_id: str 

@app.post("/calls")
def create_call(body: StartCall, db: Session= Depends(get_db)):
    account_id = body.account_id.strip().upper()
    customer= db.scalar(select(Customer).where(Customer.account_id == account_id))
    if not customer:
        raise HTTPException(404, "Unknown Account")
    if customer.do_not_call:
        raise HTTPException(403, "Customer is on the do-not-call list")
    session, opening = start_call(db, customer)
    return {"session_id": session.id, "reply": opening, "state": session.state}

class Turn(BaseModel):
    text: str = ""  # empty text = customer silence

@app.post("/calls/{session_id}/turn")
def turn(session_id:str, body:Turn, db:Session = Depends(get_db)):
    session = db.get(CallSession, session_id)
    if not session:
        raise HTTPException(404, "Unknown session")
    r = handle_turn(db, session, body.text)
    return {"reply": r.reply, "state": r.state, "ended": r.ended, "disposition": r.disposition}

def require_key(x_api_key: str = Header(default="")):
    if not hmac.compare_digest(x_api_key, config.ADMIN_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")

@app.get("/metrics", dependencies=[Depends(require_key)])
def metrics(db: Session = Depends(get_db)):
    rows = db.execute(
        select(CallSession.disposition, func.count()).group_by(CallSession.disposition)
    ).all()
    counts = {(d or "IN_PROGRESS"): n for d, n in rows}
    total = sum(counts.values())
    done = total - counts.get("IN_PROGRESS", 0)

    def rate(key: str) -> float:
        return round(counts.get(key, 0) / done, 3) if done else 0.0

    escalated = counts.get("DISPUTED", 0) + counts.get("HARDSHIP_ESCALATED", 0)
    return {
        "total_calls": total,
        "completed_calls": done,
        "by_disposition": counts,
        "ptp_rate": rate("PTP_AGREED"),
        "auth_failure_rate": rate("FAILED_AUTH"),
        "containment_rate": round(1 - escalated / done, 3) if done else 0.0,
    }

@app.get("/dispositions", dependencies=[Depends(require_key)])
def dispositions(db:Session = Depends(get_db)):
    rows = db.scalars(
        select(CallEvent).where(CallEvent.type == "DISPOSITION").order_by(CallEvent.id)
    ).all()
    return [
        {"session_id": e.session_id, **e.payload, "at": e.created_at.isoformat()} for e in rows
    ]


