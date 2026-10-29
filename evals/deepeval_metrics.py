"""DeepEval metrics wrapper configured for the EMI reminder agent."""
from __future__ import annotations

import logging
from typing import Any, Optional

from deepeval.metrics import AnswerRelevancyMetric
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase

from evals.judge import get_eval_judge

logger = logging.getLogger("evals.deepeval_metrics")


def evaluate_answer_relevance(
    customer_input: str,
    actual_reply: str,
    model: Optional[DeepEvalBaseLLM] = None,
    threshold: float = 0.5,
    include_reason: bool = True,
    async_mode: bool = False,
) -> dict[str, Any]:
    """Evaluate response relevance using DeepEval and a Groq-supported judge.

    Returns a dictionary containing the metric name, numeric score, threshold,
    pass/fail status, and explanation reason.
    """
    judge = model or get_eval_judge()

    test_case = LLMTestCase(
        input=customer_input,
        actual_output=actual_reply,
    )

    metric = AnswerRelevancyMetric(
        threshold=threshold,
        model=judge,
        include_reason=include_reason,
        async_mode=async_mode,
    )

    try:
        metric.measure(test_case)
        verdicts = []
        for v in getattr(metric, "verdicts", []):
            verdicts.append({
                "verdict": getattr(v, "verdict", ""),
                "reason": getattr(v, "reason", ""),
            })

        return {
            "metric": "answer_relevancy",
            "score": float(metric.score if metric.score is not None else 0.0),
            "threshold": float(threshold),
            "passed": bool(metric.is_successful()),
            "reason": str(metric.reason or ""),
            "statements": list(getattr(metric, "statements", [])),
            "verdicts": verdicts,
        }
    except Exception as exc:
        logger.warning("AnswerRelevancyMetric evaluation failed with provider: %r", exc)
        return {
            "metric": "answer_relevancy",
            "score": None,
            "threshold": float(threshold),
            "passed": False,
            "status": "ERROR",
            "reason": f"Provider evaluation error: {exc}",
            "error": str(exc),
        }

