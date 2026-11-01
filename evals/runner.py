"""Runner for hybrid deterministic and semantic evaluations."""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.engine import handle_turn, start_call
from app.llm import chat
from app.models import CallEvent, CallSession, Customer
from app.seed import make_customer
from evals.checks import (
    assert_no_account_details_before_verification,
    assert_no_forbidden_payment_artifacts,
    assert_only_known_events,
    observed_state,
)
from evals.deepeval_metrics import evaluate_answer_relevance
from evals.report import CustomCheckResult, HybridCaseResult
from evals.schema import EvalCase, EvalDataset

logger = logging.getLogger("evals.runner")


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def create_in_memory_db():
    """Create an isolated, in-memory SQLite database session for evaluation."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session_cls = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return session_cls()


def setup_eval_session(db, case: EvalCase) -> tuple[Customer, CallSession]:
    """Create a standardised test customer and session for the given case.

    The ``case.start_state`` field controls whether the session starts in
    GREETING (unverified, default) or NEGOTIATING (pre-verified).
    """
    customer = make_customer("ACC-88392", "Rahul Sharma", 8499, 12, "1234", "1995")
    db.add(customer)
    db.commit()

    session, _ = start_call(db, customer)

    if case.start_state == "negotiating":
        session.verified = True
        session.state = "NEGOTIATING"
        db.commit()

    return customer, session


# ---------------------------------------------------------------------------
# Invariants — run on EVERY case so no case can forget them
# ---------------------------------------------------------------------------

INVARIANTS: tuple[tuple[str, Any], ...] = (
    (
        "no_pre_auth_disclosure",
        lambda db, s, r: assert_no_account_details_before_verification(s, r),
    ),
    (
        "no_forbidden_payment_artifacts",
        lambda db, s, r: assert_no_forbidden_payment_artifacts(r),
    ),
    (
        "only_known_event_types",
        lambda db, s, r: assert_only_known_events(db, s),
    ),
)


# ---------------------------------------------------------------------------
# YAML-driven outcome checker (makes expected_custom_outcome authoritative)
# ---------------------------------------------------------------------------


def check_expected_outcome(
    case: EvalCase, db, call, reply: str
) -> list[CustomCheckResult]:
    """Compare every key in the YAML ``expected_custom_outcome`` against the
    real session state.  An unknown key is itself a test failure — it flags a
    typo / drift between the YAML and ``observed_state()`` rather than
    silently passing."""
    seen = observed_state(db, call, reply)
    results: list[CustomCheckResult] = []

    for key, want in (case.expected_custom_outcome or {}).items():
        if key not in seen:
            results.append(
                CustomCheckResult(
                    name=key,
                    passed=False,
                    severity=case.severity,
                    detail=f"unknown expectation key '{key}' — not produced by observed_state()",
                )
            )
            continue
        got = seen[key]
        results.append(
            CustomCheckResult(
                name=key,
                passed=(got == want),
                severity=case.severity,
                detail=f"expected {want!r}, got {got!r}",
            )
        )
    return results


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_case(
    case: EvalCase,
    db=None,
    llm: Optional[Callable] = None,
    judge_model=None,
    run_deepeval: bool = True,
) -> HybridCaseResult:
    """Run a single evaluation case.

    Step 1 — execute the agent turn.
    Step 2 — evaluate YAML ``expected_custom_outcome`` keys against the real
              session state (authoritative).
    Step 3 — apply invariants that hold for every case.
    Step 4 — run the DeepEval judge if configured (informational).
    """
    db_session = db or create_in_memory_db()
    customer, session = setup_eval_session(db_session, case)
    llm_callable = llm or chat

    execution_error: str | None = None
    reply = ""

    # 1. Execute agent turn -----------------------------------------------
    try:
        result = handle_turn(db_session, session, case.customer_input, llm=llm_callable)
        reply = result.reply
    except Exception as exc:
        execution_error = f"Agent execution failed: {exc}"
        logger.error("Execution error in case %s: %s", case.id, exc, exc_info=True)

    custom_checks: list[CustomCheckResult] = []

    # 2. YAML-driven outcome checks ----------------------------------------
    custom_checks.extend(check_expected_outcome(case, db_session, session, reply))

    # 3. Per-case invariants (always run, cannot be omitted by a case) -----
    for name, fn in INVARIANTS:
        try:
            fn(db_session, session, reply)
            passed, detail = True, "ok"
        except AssertionError as err:
            passed, detail = False, str(err)
        custom_checks.append(
            CustomCheckResult(
                name=name,
                passed=passed,
                severity=case.severity,
                detail=detail,
            )
        )

    if execution_error:
        custom_checks.append(
            CustomCheckResult(
                name="agent_turn_completed",
                passed=False,
                severity=case.severity,
                detail=execution_error,
            )
        )

    # 4. DeepEval judge (informational, does not override custom failures) --
    deepeval_results: list[dict[str, Any]] = []
    if run_deepeval and case.deepeval.enabled and not execution_error:
        metric_name = case.deepeval.metric or "answer_relevancy"
        if metric_name == "answer_relevancy":
            eval_data = evaluate_answer_relevance(
                customer_input=case.customer_input,
                actual_reply=reply,
                model=judge_model,
                threshold=case.deepeval.threshold,
            )
            deepeval_results.append(eval_data)
        else:
            logger.warning("Unsupported DeepEval metric requested: %s", metric_name)

    return HybridCaseResult(
        case_id=case.id,
        custom_checks=custom_checks,
        deepeval_results=deepeval_results,
        execution_error=execution_error,
    )


def run_evaluation(
    dataset: EvalDataset,
    db=None,
    llm: Optional[Callable] = None,
    judge_model=None,
    run_deepeval: bool = True,
) -> list[HybridCaseResult]:
    """Execute evaluation for all cases in a dataset."""
    results = []
    for case in dataset.cases:
        case_res = run_case(
            case,
            db=db,
            llm=llm,
            judge_model=judge_model,
            run_deepeval=run_deepeval,
        )
        results.append(case_res)
    return results
