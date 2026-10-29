"""DeepEval quality and judge integration tests."""
import os
from unittest.mock import MagicMock

import pytest

from app.engine import handle_turn
from evals.judge import GroqJudge
from evals.deepeval_metrics import evaluate_answer_relevance
from evals.runner import run_case
from evals.schema import EvalCase, ExpectedCustomOutcome, DeepEvalCaseConfig
from tests.helpers import ScriptedLLM, text


def test_response_relevance_with_deepeval(db, verified_call):
    """Live judge test, skipped unless RUN_DEEPEVAL=1 is set."""
    enabled = os.getenv("RUN_DEEPEVAL", "").strip().lower()
    if enabled not in {"1", "true", "yes"}:
        pytest.skip("Set RUN_DEEPEVAL=1 to enable DeepEval judging.")

    pytest.importorskip("deepeval")

    customer_input = "I am having difficulty paying my EMI. What can I do?"
    llm = ScriptedLLM(
        text(
            "I understand. I can refer your hardship request to a human agent "
            "who can discuss the available next steps."
        )
    )
    result = handle_turn(db, verified_call, customer_input, llm=llm)

    evaluation = evaluate_answer_relevance(
        customer_input=customer_input,
        actual_reply=result.reply,
    )

    assert 0.0 <= evaluation["score"] <= 1.0
    assert evaluation["metric"] == "answer_relevancy"


def test_groq_judge_configuration_and_model_name():
    """Verify GroqJudge uses Groq model without requiring OpenAI key."""
    judge = GroqJudge(model_name="openai/gpt-oss-120b", api_key="gsk_test123")
    assert judge.get_model_name() == "openai/gpt-oss-120b"
    assert judge.name == "openai/gpt-oss-120b"
    assert judge.api_key == "gsk_test123"

    messages = judge._prepare_messages("Rate this turn", schema=MagicMock)
    assert any("json" in m["content"].lower() for m in messages)


def test_evaluate_answer_relevance_with_mocked_groq_judge():
    """Test full DeepEval AnswerRelevancyMetric flow through GroqJudge."""
    judge = GroqJudge(model_name="openai/gpt-oss-120b", api_key="gsk_test123")

    mock_client = MagicMock()

    def mock_create(*args, **kwargs):
        messages = kwargs.get("messages", [])
        content = messages[-1]["content"] if messages else ""
        resp = MagicMock()
        if "generate a list of statements" in content.lower():
            resp.choices = [
                MagicMock(message=MagicMock(content='{"statements": ["I can refer your hardship request to a human agent."]}'))
            ]
        elif "determine whether each" in content.lower():
            resp.choices = [
                MagicMock(message=MagicMock(content='{"verdicts": [{"verdict": "yes", "reason": "Addresses customer hardship query."}]}'))
            ]
        else:
            resp.choices = [
                MagicMock(message=MagicMock(content='{"reason": "The response is relevant and helpful."}'))
            ]
        return resp

    mock_client.chat.completions.create.side_effect = mock_create
    judge._sync_client = mock_client

    evaluation = evaluate_answer_relevance(
        customer_input="I am having difficulty paying my EMI. What can I do?",
        actual_reply="I can refer your hardship request to a human agent.",
        model=judge,
        async_mode=False,
    )

    assert evaluation["metric"] == "answer_relevancy"
    assert 0.0 <= evaluation["score"] <= 1.0
    assert evaluation["passed"] is True
    assert evaluation["score"] == 1.0
    assert evaluation["reason"] == "The response is relevant and helpful."


def test_deterministic_checks_run_independently_when_judge_fails():
    """Custom deterministic checks must pass even if the LLM judge throws an error."""
    broken_judge = GroqJudge(model_name="llama-3.3-70b-versatile", api_key="gsk_broken")
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("Groq rate limit exceeded")
    broken_judge._sync_client = mock_client

    case = EvalCase(
        id="hardship_response",
        category="conversation_quality",
        severity="medium",
        customer_input="I am having difficulty paying my EMI. What can I do?",
        expected_custom_outcome=ExpectedCustomOutcome(requires_review=True),
        deepeval=DeepEvalCaseConfig(enabled=True, metric="answer_relevancy"),
    )

    fake_llm = ScriptedLLM(text("I understand your hardship. Let me connect you to our support team."))

    result = run_case(
        case=case,
        llm=fake_llm,
        judge_model=broken_judge,
        run_deepeval=True,
    )

    # Custom checks ran and passed
    assert len(result.custom_checks) >= 1
    assert all(chk.passed for chk in result.custom_checks)
    # DeepEval captured the provider error without crashing
    assert len(result.deepeval_results) == 1
    assert "error" in result.deepeval_results[0] or result.deepeval_results[0]["passed"] is False
    # Overall case still passes because custom checks passed and DeepEval is informational
    assert result.passed is True
