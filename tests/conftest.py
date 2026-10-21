import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.engine import start_call
from app.seed import make_customer

@pytest.fixture
def db():
    # An in-memory SQLite database exists per connection. StaticPool forces ONE
    # shared connection so the tables survive for the whole test.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield session
    session.close()

@pytest.fixture
def customer(db):
    c = make_customer("ACC-88392", "Rahul Sharma", 8499, 12, "1234", "1995")
    db.add(c)
    db.commit()
    return c


@pytest.fixture
def call(db, customer):
    """A freshly started call in GREETING."""
    session, _ = start_call(db, customer)
    return session


@pytest.fixture
def verified_call(db, call):
    """A call already verified and in NEGOTIATING (set by hand as a shortcut)."""
    call.verified = True
    call.state = "NEGOTIATING"
    db.commit()
    return call
