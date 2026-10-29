"""Data schemas for evaluation datasets and test cases."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Union
import yaml
from pydantic import BaseModel, ConfigDict, Field


class ExpectedCustomOutcome(BaseModel):
    model_config = ConfigDict(extra="allow")

    account_details_disclosed: Optional[bool] = None
    verification_required: Optional[bool] = None
    ptp_event_recorded: Optional[bool] = None
    ptp_agreed: Optional[bool] = None
    requires_review: Optional[bool] = None
    extra: dict[str, Any] = Field(default_factory=dict)


class DeepEvalCaseConfig(BaseModel):
    enabled: bool = False
    metric: Optional[str] = None
    threshold: float = 0.5
    reason: Optional[str] = None
    note: Optional[str] = None


class EvalCase(BaseModel):
    id: str
    category: str
    severity: str = "medium"
    customer_input: str
    expected_custom_outcome: ExpectedCustomOutcome = Field(default_factory=ExpectedCustomOutcome)
    deepeval: DeepEvalCaseConfig = Field(default_factory=DeepEvalCaseConfig)


class EvalDataset(BaseModel):
    version: str = "1"
    description: str = ""
    cases: list[EvalCase] = Field(default_factory=list)


def load_dataset(file_path: Union[str, Path]) -> EvalDataset:
    """Load and parse an evaluation dataset from a YAML file."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Dataset file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return EvalDataset.model_validate(data)
