#!/usr/bin/env python3
"""
Northwind Expense Reviewer — Evaluation Harness
Measures: Verdict Accuracy, Citation Faithfulness, Out-of-Scope Refusal Rate,
          Confidence Calibration, False Confident Rate.

Usage:
    python evaluation_harness.py --api http://localhost:8000 --cases expected_outcomes.json
"""

import argparse
import json
import sys
import time
from pathlib import Path
import urllib.request
import urllib.error


def api_post(base_url: str, path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        base_url + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def api_get(base_url: str, path: str) -> dict:
    with urllib.request.urlopen(base_url + path, timeout=10) as resp:
        return json.loads(resp.read())


# ─── Metric helpers ──────────────────────────────────────────────────────────

def verdict_accuracy(results: list) -> float:
    if not results:
        return 0.0
    correct = sum(1 for r in results if r["predicted"] == r["expected"])
    return correct / len(results)


def citation_faithfulness(results: list) -> float:
    """Fraction of verdicts that include at least one cited clause."""
    if not results:
        return 0.0
    cited = sum(1 for r in results if r.get("has_citation", False))
    return cited / len(results)


def refusal_rate(results: list) -> float:
    """Fraction of out-of-scope questions that were correctly refused."""
    oos = [r for r in results if r.get("expected_in_scope") is False]
    if not oos:
        return 1.0
    refused = sum(1 for r in oos if not r.get("answered_in_scope", True))
    return refused / len(oos)


def false_confident_rate(results: list) -> float:
    """Fraction of wrong verdicts where confidence >= 0.85 (worst signal)."""
    wrong = [r for r in results if r["predicted"] != r["expected"]]
    if not wrong:
        return 0.0
    false_conf = sum(1 for r in wrong if r.get("confidence", 0) >= 0.85)
    return false_conf / len(wrong)


def calibration_error(results: list) -> float:
    """Mean absolute difference between confidence and per-bucket accuracy."""
    buckets = {}
    for r in results:
        b = round(r.get("confidence", 0) * 10) / 10  # bucket to 0.1
        buckets.setdefault(b, []).append(r["predicted"] == r["expected"])
    if not buckets:
        return 0.0
    errors = [abs(sum(v) / len(v) - b) for b, v in buckets.items()]
    return sum(errors) / len(errors)


# ─── Test runners ─────────────────────────────────────────────────────────────

def run_verdict_tests(base_url: str, cases: list) -> list:
    print("\n📋 Running verdict evaluation tests…")
    results = []
    employees = api_get(base_url, "/api/employees")
    emp_id = employees[0]["id"] if employees else "NW-00001"

    for i, case in enumerate(cases):
        print(f"  [{i+1}/{len(cases)}] {case.get('description', 'case')}", end=" ", flush=True)
        try:
            # Create a submission
            sub = api_post(base_url, "/api/submissions/new", {
                "employee_id": emp_id,
                "trip_purpose": case.get("trip_purpose", "Business travel"),
                "trip_start_date": case.get("trip_start_date", "2025-01-10"),
                "trip_end_date": case.get("trip_end_date", "2025-01-12"),
            })
            sub_id = sub["submission_id"]

            # Upload a synthetic text receipt
            receipt_text = (
                f"RECEIPT\n"
                f"Vendor: {case['vendor']}\n"
                f"Amount: ${case['amount']}\n"
                f"Date: {case.get('receipt_date', '2025-01-11')}\n"
                f"Category: {case['category']}\n"
                f"Description: {case.get('description', '')}\n"
            )
            import io
            import urllib.parse

            boundary = "----FormBoundary"
            body = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="receipt.txt"\r\n'
                f"Content-Type: text/plain\r\n\r\n"
                f"{receipt_text}\r\n"
                f"--{boundary}--\r\n"
            ).encode()

            req = urllib.request.Request(
                base_url + f"/api/submissions/{sub_id}/upload",
                data=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                upload = json.loads(resp.read())

            verdict = upload.get("verdict", {})
            predicted = verdict.get("verdict", "ambiguous")
            confidence = verdict.get("confidence", 0.0)
            has_citation = bool(verdict.get("cited_clauses"))

            result = {
                "case": case.get("description"),
                "expected": case["expected_verdict"],
                "predicted": predicted,
                "confidence": confidence,
                "has_citation": has_citation,
            }
            results.append(result)
            match = "✅" if predicted == case["expected_verdict"] else "❌"
            print(f"{match} expected={case['expected_verdict']} got={predicted} conf={confidence:.2f}")
        except Exception as exc:
            print(f"💥 Error: {exc}")
            results.append({
                "case": case.get("description"),
                "expected": case.get("expected_verdict", "unknown"),
                "predicted": "error",
                "confidence": 0.0,
                "has_citation": False,
            })
        time.sleep(0.5)

    return results


def run_qa_tests(base_url: str, cases: list) -> list:
    print("\n💬 Running policy Q&A tests…")
    results = []
    for i, case in enumerate(cases):
        print(f"  [{i+1}/{len(cases)}] {case['question'][:60]}", end=" ", flush=True)
        try:
            resp = api_post(base_url, "/api/policy/ask", {"question": case["question"]})
            answered_in_scope = resp.get("in_scope", True)
            result = {
                "question": case["question"],
                "expected_in_scope": case.get("expected_in_scope", True),
                "answered_in_scope": answered_in_scope,
                "has_citation": bool(resp.get("cited_clauses")),
            }
            results.append(result)
            correct = answered_in_scope == case.get("expected_in_scope", True)
            print("✅" if correct else "❌")
        except Exception as exc:
            print(f"💥 {exc}")
            results.append({
                "question": case["question"],
                "expected_in_scope": case.get("expected_in_scope", True),
                "answered_in_scope": True,
                "has_citation": False,
            })
        time.sleep(0.3)
    return results


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Northwind Expense Reviewer — Evaluation Harness")
    parser.add_argument("--api", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--cases", default="expected_outcomes.json", help="Test cases JSON file")
    args = parser.parse_args()

    # Health check
    try:
        health = api_get(args.api, "/api/health")
        print(f"✅ API healthy: {health}")
    except Exception as e:
        print(f"❌ API not reachable at {args.api}: {e}")
        sys.exit(1)

    # Load test cases
    cases_path = Path(args.cases)
    if not cases_path.exists():
        print(f"⚠️  Test cases file not found: {cases_path}. Using built-in defaults.")
        test_data = _default_test_cases()
    else:
        with open(cases_path) as f:
            test_data = json.load(f)

    verdict_cases = test_data.get("verdict_tests", [])
    qa_cases = test_data.get("qa_tests", [])

    # Run tests
    verdict_results = run_verdict_tests(args.api, verdict_cases) if verdict_cases else []
    qa_results = run_qa_tests(args.api, qa_cases) if qa_cases else []

    # Compute metrics
    print("\n" + "=" * 60)
    print("📊 EVALUATION RESULTS")
    print("=" * 60)

    if verdict_results:
        acc = verdict_accuracy(verdict_results)
        cit = citation_faithfulness(verdict_results)
        fc  = false_confident_rate(verdict_results)
        cal = calibration_error(verdict_results)
        print(f"  Verdict Accuracy:        {acc*100:.1f}%  ({sum(1 for r in verdict_results if r['predicted']==r['expected'])}/{len(verdict_results)} correct)")
        print(f"  Citation Faithfulness:   {cit*100:.1f}%  (verdicts with ≥1 policy citation)")
        print(f"  False Confident Rate:    {fc*100:.1f}%  (wrong verdicts with conf≥85% — lower is better)")
        print(f"  Calibration Error (MAE): {cal:.3f}  (lower is better)")

    if qa_results:
        ref = refusal_rate(qa_results)
        qa_cit = sum(1 for r in qa_results if r.get("has_citation")) / max(len(qa_results), 1)
        print(f"  Out-of-Scope Refusal:    {ref*100:.1f}%  (correctly refused out-of-scope questions)")
        print(f"  Q&A Citation Rate:       {qa_cit*100:.1f}%  (answers with policy citations)")

    print("=" * 60)

    # Detailed results
    print("\nDetailed Verdict Results:")
    for r in verdict_results:
        status = "✅" if r["predicted"] == r["expected"] else "❌"
        print(f"  {status} [{r['case']}] expected={r['expected']} got={r['predicted']} conf={r['confidence']:.2f} cited={r['has_citation']}")


def _default_test_cases() -> dict:
    return {
        "verdict_tests": [
            {
                "description": "Compliant NYC dinner under limit",
                "vendor": "Ruth's Chris Steakhouse",
                "amount": 85.00,
                "category": "meal",
                "receipt_date": "2025-01-11",
                "trip_purpose": "Client meeting in New York",
                "trip_start_date": "2025-01-10",
                "trip_end_date": "2025-01-12",
                "expected_verdict": "compliant",
            },
            {
                "description": "Over-limit NYC dinner",
                "vendor": "Le Bernardin",
                "amount": 210.00,
                "category": "meal",
                "receipt_date": "2025-01-11",
                "trip_purpose": "Team dinner in New York",
                "trip_start_date": "2025-01-10",
                "trip_end_date": "2025-01-12",
                "expected_verdict": "rejected",
            },
            {
                "description": "Compliant Tier 2 lodging",
                "vendor": "Marriott Chicago",
                "amount": 235.00,
                "category": "lodging",
                "receipt_date": "2025-01-11",
                "trip_purpose": "Sales conference in Chicago",
                "trip_start_date": "2025-01-10",
                "trip_end_date": "2025-01-12",
                "expected_verdict": "compliant",
            },
            {
                "description": "Over-limit NYC lodging",
                "vendor": "The Plaza Hotel",
                "amount": 580.00,
                "category": "lodging",
                "receipt_date": "2025-01-11",
                "trip_purpose": "Client visit in New York",
                "trip_start_date": "2025-01-10",
                "trip_end_date": "2025-01-12",
                "expected_verdict": "rejected",
            },
            {
                "description": "Economy flight — compliant",
                "vendor": "Delta Airlines",
                "amount": 420.00,
                "category": "air_travel",
                "receipt_date": "2025-01-10",
                "trip_purpose": "Conference travel",
                "trip_start_date": "2025-01-10",
                "trip_end_date": "2025-01-14",
                "expected_verdict": "compliant",
            },
        ],
        "qa_tests": [
            {"question": "What is the maximum lodging rate in New York?", "expected_in_scope": True},
            {"question": "Can I expense first class flights?", "expected_in_scope": True},
            {"question": "What is the capital of France?", "expected_in_scope": False},
            {"question": "How much can I spend on a client dinner per person?", "expected_in_scope": True},
            {"question": "What is the stock price of Northwind?", "expected_in_scope": False},
        ],
    }


if __name__ == "__main__":
    main()
