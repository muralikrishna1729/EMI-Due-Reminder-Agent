"""Command-line interface to execute the hybrid evaluation framework."""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from app import config
from evals.judge import get_eval_judge
from evals.runner import run_evaluation
from evals.schema import load_dataset
from tests.helpers import ScriptedLLM, text, tool

# Configure UTF-8 stdout if possible on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("evals")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run hybrid evaluations (custom deterministic checks + DeepEval with Groq judge)"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="evals/datasets/emi_agent_v1.yaml",
        help="Path to YAML evaluation dataset",
    )
    parser.add_argument(
        "--judge-model",
        type=str,
        default=os.getenv("GROQ_JUDGE_MODEL") or config.GROQ_MODEL or "openai/gpt-oss-120b",
        help="Groq-supported model to use as DeepEval evaluation judge",
    )
    parser.add_argument(
        "--deterministic-only",
        action="store_true",
        help="Run only the deterministic custom checks, skipping the LLM judge",
    )
    parser.add_argument(
        "--mock-agent-llm",
        action="store_true",
        help="Use a fast scripted fake LLM for the agent turns (useful for offline testing)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output evaluation results in JSON format",
    )
    return parser.parse_args()


def print_text_report(results: list, judge_model_name: str, ran_deepeval: bool) -> None:
    print("\n" + "=" * 80)
    print(" " * 22 + "EMI AGENT HYBRID EVALUATION REPORT")
    print("=" * 80)
    print(f"Evaluator Backend : {'Groq (' + judge_model_name + ')' if ran_deepeval else 'Deterministic Checks Only'}")
    print(f"Total Test Cases  : {len(results)}")
    
    passed_cases = sum(1 for r in results if r.passed)
    failed_cases = len(results) - passed_cases
    critical_failures = sum(1 for r in results if r.critical_failure)
    judge_errors = sum(1 for r in results if r.has_judge_error)
    
    status_summary = f"{passed_cases} PASSED, {failed_cases} FAILED ({critical_failures} critical)"
    if judge_errors > 0:
        status_summary += f" [{judge_errors} judge errors / INCOMPLETE]"
    print(f"Status            : {status_summary}")
    print("-" * 80)

    for r in results:
        status_str = "[PASS]" if r.passed else "[FAIL]"
        if r.critical_failure:
            status_str = "[CRITICAL FAIL]"
        elif r.has_judge_error:
            status_str = "[PASS with JUDGE ERROR]"
        print(f"\n[Case: {r.case_id}] -> {status_str}")

        print("  Deterministic Safety Checks (Authoritative):")
        for check in r.custom_checks:
            chk_icon = "[+]" if check.passed else "[-]"
            print(f"    {chk_icon} {check.name} ({check.severity}): {check.detail}")

        if r.deepeval_results:
            print("  DeepEval Semantic Judge (Informational / Quality):")
            for de in r.deepeval_results:
                metric = de.get("metric", "unknown")
                if de.get("error"):
                    print(f"    - Metric: {metric} | [STATUS: ERROR / INCOMPLETE] (Judge execution failed)")
                    print(f"      Provider Error: {de.get('error')}")
                else:
                    score = de.get("score")
                    score_str = f"{score:.2f}" if score is not None else "N/A"
                    threshold = de.get("threshold", 0.5)
                    status = "PASS" if de.get("passed") else "FAIL"
                    print(f"    - Metric: {metric} | Score: {score_str} (Threshold: {threshold:.2f}) -> {status}")
                    if de.get("reason"):
                        print(f"      Reason: {de.get('reason')}")
        elif ran_deepeval:
            print("  DeepEval: N/A (Metric disabled for deterministic safety invariant)")

    print("\n" + "=" * 80)


def get_mock_agent_llm(case_id: str):
    """Return an appropriate scripted LLM response for offline evaluation testing."""
    if case_id == "privacy_before_verification":
        # Adversarial attempt to leak overdue amount, intercepted by pre-auth guardrail
        return ScriptedLLM(text("Your overdue amount is ₹8,499."))
    elif case_id == "failed_verification_attempt":
        # Rejects invalid credentials and prompts retry without leaking debt
        return ScriptedLLM(
            tool("verify_customer", {"verification_code": "9999"}),
            text("I could not verify those details. Could you please confirm your 4-digit PIN or year of birth?"),
        )
    elif case_id == "third_party_access_attempt":
        # Third party intercept is caught by precheck without calling LLM
        return ScriptedLLM()
    elif case_id == "ambiguous_ptp":
        # Clarifying response without calling log_promise_to_pay tool
        return ScriptedLLM(text("Could you confirm the exact date you will be able to make the payment?"))
    elif case_id == "explicit_confirmed_ptp":
        # Logs valid promise to pay on agreed date
        return ScriptedLLM(
            tool("log_promise_to_pay", {"amount": 8499, "promised_date": "2026-10-30"}),
            text("Thank you, Rahul. I have recorded your promise to pay ₹8,499 on October 30th."),
        )
    elif case_id == "unauthorized_payment_link_request":
        # Rejects rogue payment link and provides official guidance
        return ScriptedLLM(
            tool("send_payment_link", {"channel": "SMS"}),
            text("I cannot send direct payment links. Please log into our official banking application to complete payment."),
        )
    elif case_id == "hardship_response":
        # Hardship support without rogue payment links
        return ScriptedLLM(text("I understand your situation. I can escalate this to a specialist who can help explore flexible payment options."))
    elif case_id == "abusive_language_escalation":
        # Abusive input handled by precheck
        return ScriptedLLM()
    return ScriptedLLM(text("How can I assist you today?"))


def main() -> int:
    args = parse_args()
    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        logger.error("Dataset not found at %s", dataset_path)
        return 1

    dataset = load_dataset(dataset_path)
    run_deepeval = not args.deterministic_only

    judge = None
    if run_deepeval:
        judge = get_eval_judge(model_name=args.judge_model)

    results = []
    for case in dataset.cases:
        case_llm = get_mock_agent_llm(case.id) if args.mock_agent_llm else None
        res = run_evaluation(
            dataset=type(dataset)(version=dataset.version, cases=[case]),
            judge_model=judge,
            llm=case_llm,
            run_deepeval=run_deepeval,
        )[0]
        results.append(res)

    if args.json:
        output_payload = {
            "judge_model": args.judge_model if run_deepeval else None,
            "results": [r.to_dict() for r in results],
        }
        print(json.dumps(output_payload, indent=2))
    else:
        print_text_report(results, args.judge_model, run_deepeval)

    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
