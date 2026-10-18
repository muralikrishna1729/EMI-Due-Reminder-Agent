import uuid
from datetime import datetime, timezone
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

def utcnow():
    return datetime.now(timezone.utc)

class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(100))
    loan_type: Mapped[str] = mapped_column(String(50), default="Personal Loan")
    overdue_amount: Mapped[int] = mapped_column(Integer)
    dpd: Mapped[int] = mapped_column(Integer)
    salt: Mapped[str] = mapped_column(String(32))
    pan_last4_hash: Mapped[str] = mapped_column(String(64))
    birth_year_hash: Mapped[str] = mapped_column(String(64))
    do_not_call: Mapped[bool] = mapped_column(Boolean, default=False)

class CallSession(Base):
    __tablename__ = "call_sessions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    state: Mapped[str] = mapped_column(String(20), default="GREETING")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verify_attempts: Mapped[int] = mapped_column(Integer, default=0)
    warnings_given: Mapped[int] = mapped_column(Integer, default=0)
    silence_count: Mapped[int] = mapped_column(Integer, default=0)
    ptp_logged: Mapped[bool] = mapped_column(Boolean, default=False)
    disposition: Mapped[str | None] = mapped_column(String(30), nullable=True)
    history: Mapped[list] = mapped_column(JSON, default=list)
    # JSON columns don’t detect in-place changes. Always reassign (s.history = s.history + [...]) instead of calling .append.
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    customer: Mapped[Customer] = relationship()

class CallEvent(Base):
    __tablename__ = "call_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("call_sessions.id"), index=True)
    type: Mapped[str] = mapped_column(String(20))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
