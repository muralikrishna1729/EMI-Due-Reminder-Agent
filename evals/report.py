"""Combine custom checks and semantic scores without hiding safety failures."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class CustomCheckResult:
    name: str
    passed: bool
    severity: str
    detail: str = ""


@dataclass
class HybridCaseResult:
    case_id: str
    custom_checks: list[CustomCheckResult]
    deepeval_results: list[dict[str, Any]]
    execution_error: str | None = None

    @property
    def critical_failure(self) -> bool:
        return any(
            not check.passed and check.severity.lower() == "critical"
            for check in self.custom_checks
        )

    @property
    def has_judge_error(self) -> bool:
        return any(bool(de.get("error")) for de in self.deepeval_results)

    @property
    def passed(self) -> bool:
        if self.execution_error:
            return False
        if self.critical_failure:
            return False
        # Any failed custom check fails the case
        if any(not check.passed for check in self.custom_checks):
            return False
        # DeepEval is informational here; it cannot override custom failures
        return True

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["critical_failure"] = self.critical_failure
        result["has_judge_error"] = self.has_judge_error
        result["passed"] = self.passed
        return result
