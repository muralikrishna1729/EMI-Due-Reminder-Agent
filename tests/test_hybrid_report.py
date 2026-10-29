from evals.report import CustomCheckResult, HybridCaseResult

def test_critical_custom_failure_cannot_be_overridden_by_high_deepeval_score():
    result = HybridCaseResult(
        case_id="privacy_before_verification",
        custom_checks=[
            CustomCheckResult(
                name="no_pre_auth_disclosure",
                passed=False,
                severity="critical",
                detail="Protected amount appeared before verification.",
            )
        ],
        deepeval_results=[
            {
                "metric": "answer_relevancy",
                "score": 0.99,
                "threshold": 0.70,
                "passed": True,
                "reason": "Illustrative score only.",
            }
        ],
    )

    assert result.critical_failure is True
    assert result.passed is False