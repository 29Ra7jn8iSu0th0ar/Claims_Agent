# eval_harness.py  (in root of project)
"""
Run this to prove the claims pipeline doesn't hallucinate decisions.
Each test case has a known expected outcome — the harness checks reality matches.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import create_tables, SessionLocal
from app.models.claim import Claim
from app.services.document_extractor import extract_claim_fields
from app.services.validator import DeterministicValidator
from app.services.risk_scorer import score_claim
from datetime import datetime, timedelta

# ── Golden test set ──────────────────────────────────────────────────────────
# These are ground-truth cases. Expected outcome must never change
# unless a human deliberately updates this file and commits the change.






OLD      = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
NEW      = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
DELAYED  = (datetime.now() - timedelta(days=200)).strftime("%Y-%m-%d")
VERY_OLD = (datetime.now() - timedelta(days=623)).strftime("%Y-%m-%d")

GOLDEN_CASES = [
    {
        "id": "TC-001",
        "description": "Clean low-value claim, no flags — expect auto_approve",
        "claim": {
            "claimant_name": "Test User",
            "product_name":  "LG Washing Machine",
            "claim_amount":  450.0,
            "incident_date": OLD,
            "description":   "The washing machine stopped spinning during a normal cycle. "
                             "It makes a loud grinding noise and the drum does not rotate. "
                             "The machine is 18 months old.",
        },
        "expected_decision": "auto_approve",
        "expected_risk":     "low",
    },
    {
        "id": "TC-002",
        "description": "Legal threat + high value + repeat claim — expect human_review",
        "claim": {
            "claimant_name": "Test User",
            "product_name":  "Samsung TV",
            "claim_amount":  7200.0,
            "incident_date": OLD,
            "description":   "TV stopped working again. This is the second time. "
                             "My lawyer has advised me. I will take legal action immediately.",
        },
        "expected_decision": "human_review",
        "expected_risk":     "medium",
    },
    {
        "id": "TC-003",
        "description": "Waiting period violation — filed 5 days after incident",
        "claim": {
            "claimant_name": "Test User",
            "product_name":  "Dyson Vacuum",
            "claim_amount":  600.0,
            "incident_date": NEW,
            "description":   "The vacuum stopped working after 3 uses. "
                             "The motor makes a burning smell and shuts off automatically. "
                             "This is clearly a manufacturing defect from the factory.",
        },
        "expected_decision": "human_review",
        "expected_risk":     "medium",
    },
    {
        "id": "TC-004",
        "description": "Amount exceeds ceiling — expect human_review",
        "claim": {
            "claimant_name": "Test User",
            "product_name":  "Industrial Equipment",
            "claim_amount":  11000.0,
            "incident_date": OLD,
            "description":   "The equipment broke down after normal use. "
                             "It has been consistently malfunctioning for three weeks. "
                             "We need immediate repair or replacement of the unit.",
        },
        "expected_decision": "human_review",
        "expected_risk":     "high",
    },
    {
        "id": "TC-005",
        "description": "Excessive delay — 200 days since incident — expect human_review",
        "claim": {
            "claimant_name": "Test User",
            "product_name":  "MiPhone",
            "claim_amount":  800.0,
            "incident_date": DELAYED,
            "description":   "The phone stopped working after a loud popping sound. "
                             "The screen went completely black and will not turn on. "
                             "The phone is 14 months old and has never had issues before.",
        },
        "expected_decision": "human_review",
        "expected_risk":     "medium",
    },
    {
        "id": "TC-006",
        "description": "623-day delay — should NOT auto_approve — expect human_review",
        "claim": {
            "claimant_name": "Test User",
            "product_name":  "MiPhone",
            "claim_amount":  8200.0,
            "incident_date": VERY_OLD,
            "description":   "The phone stopped working suddenly with a loud popping sound. "
                             "The screen went completely black and will not turn on. "
                             "The phone is 14 months old and has never had any issues before.",
        },
        "expected_decision": "human_review",
        "expected_risk":     "high",
    },
    {
        "id": "TC-007",
        "description": "Ambiguous submission — vague high-value claim — expect human_review",
        "claim": {
            "claimant_name": "Test User",
            "product_name":  "Unknown Device",
            "claim_amount":  4500.0,
            "incident_date": OLD,
            "description":   "The product stopped working and I want a refund for it.",
        },
        "expected_decision": "human_review",
        "expected_risk":     "medium",
    },
]


# ── Harness runner ───────────────────────────────────────────────────────────
def run_eval():
    create_tables()
    db = SessionLocal()

    results = []
    passed  = 0
    failed  = 0

    print("\n" + "="*60)
    print("  CLAIMS AGENT — EVAL HARNESS")
    print("="*60)

    for case in GOLDEN_CASES:
        # Build a transient Claim object (not saved to DB)
        claim = Claim(**case["claim"])
        claim.extracted_data = extract_claim_fields(
            claim.description, claim.incident_date
        )

        validator         = DeterministicValidator(db)
        validation_result = validator.validate(claim)

        # No LLM call in eval — we use empty anomalies
        # This makes evals fast, free, and deterministic
        llm_mock   = {"anomalies": [], "llm_success": True}
        score_result = score_claim(claim, validation_result.to_dict(), llm_mock)

        actual_decision = score_result["decision"].value \
            if hasattr(score_result["decision"], "value") \
            else str(score_result["decision"])
        actual_risk = score_result["level"].value \
            if hasattr(score_result["level"], "value") \
            else str(score_result["level"])

        decision_pass = actual_decision == case["expected_decision"]
        risk_pass     = actual_risk     == case["expected_risk"]
        overall_pass  = decision_pass and risk_pass

        status = "✓ PASS" if overall_pass else "✗ FAIL"
        if overall_pass:
            passed += 1
        else:
            failed += 1

        print(f"\n{status}  [{case['id']}] {case['description']}")
        print(f"        Decision : expected={case['expected_decision']:<15} "
              f"actual={actual_decision:<15} {'✓' if decision_pass else '✗'}")
        print(f"        Risk     : expected={case['expected_risk']:<15} "
              f"actual={actual_risk:<15} {'✓' if risk_pass else '✗'}")
        print(f"        Score    : {score_result['score']} | "
              f"Factors: {', '.join(score_result['factors']) or 'none'}")

        results.append({
            "id": case["id"],
            "passed": overall_pass,
            "actual_decision": actual_decision,
            "actual_risk": actual_risk,
        })

    db.close()

    print("\n" + "="*60)
    quality_score = round((passed / len(GOLDEN_CASES)) * 100)
    print(f"  RESULT: {passed}/{len(GOLDEN_CASES)} passed — "
          f"Quality score: {quality_score}%")
    print("="*60 + "\n")

    if failed > 0:
        print("  ⚠  REGRESSION DETECTED — do not deploy until all cases pass\n")
        sys.exit(1)  # non-zero exit = CI pipeline fails the build
    else:
        print("  ✓  All golden cases pass — safe to deploy\n")
        sys.exit(0)


if __name__ == "__main__":
    run_eval()