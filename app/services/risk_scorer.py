
# app/services/risk_scorer.py
"""
Weighted scoring model. Fully deterministic.
The LLM anomalies can INFLUENCE the score (as soft signals)
but cannot override hard rule failures.

Score range: 0.0 (no risk) → 1.0 (maximum risk)
Thresholds determine routing.
"""
from app.core.enums import RiskLevel, DecisionOutcome

# Tunable weights — these are business decisions, not ML
SCORE_WEIGHTS = {
    # Hard failures (each adds 0.3, capped)
    # "hard_failure_per":     0.30,
    "hard_failure_per":     0.65,
    # Soft warnings
    "legal_threat":         0.25,
    "repeat_claim_signal":  0.15,
    "high_value_claim":     0.10,
    "unclassified_damage":  0.05,
    "waiting_period_violation": 0.25,   # NEW: waiting period flag
    # Claim amount scaling
    "amount_over_5000":     0.10,
    "amount_over_8000":     0.20,       # increased from 0.10
    "amount_over_10000":    0.20,       # NEW
    # LLM anomaly signals (soft, from LLM output)
    "llm_anomaly_per":      0.05,  # per anomaly, capped at 0.15
    # "ambiguous_submission": 0.40,
    "ambiguous_submission": 0.60,
}

# Routing thresholds – lowered to catch medium‑risk claims
HUMAN_REVIEW_THRESHOLD = 0.45   # was 0.60 – now $15k + one failure exceeds this
AUTO_REJECT_THRESHOLD  = 0.90   # very high confidence needed to auto-reject


def score_claim(claim, validation_result: dict, llm_result: dict) -> dict:
    score = 0.0
    factors = []

    # Hard failures
    n_failures = len(validation_result.get("failures", []))
    failure_contribution = min(n_failures * SCORE_WEIGHTS["hard_failure_per"], 0.90)
    if n_failures:
        score += failure_contribution
        factors.append(f"{n_failures} validation failure(s) (+{failure_contribution:.2f})")

    # Warning flags
    warnings = {w["rule"] for w in validation_result.get("warnings", [])}
    for flag, weight in [
        ("LEGAL_THREAT_LANGUAGE",   "legal_threat"),
        ("REPEAT_CLAIM_SIGNAL",     "repeat_claim_signal"),
        ("HIGH_VALUE_CLAIM",        "high_value_claim"),
        ("UNCLASSIFIED_DAMAGE",     "unclassified_damage"),
        ("WAITING_PERIOD_VIOLATION","waiting_period_violation"),   # NEW
        ("AMBIGUOUS_SUBMISSION",    "ambiguous_submission"), 
    ]:
        if flag in warnings:
            score += SCORE_WEIGHTS[weight]
            factors.append(f"{flag} (+{SCORE_WEIGHTS[weight]:.2f})")

    # Amount tiers – now progressive: 5k, 8k, 10k+
    if claim.claim_amount > 10_000:
        score += SCORE_WEIGHTS["amount_over_10000"]
        factors.append(f"Amount >$10000 (+{SCORE_WEIGHTS['amount_over_10000']:.2f})")
    if claim.claim_amount > 8_000:
        score += SCORE_WEIGHTS["amount_over_8000"]
        factors.append(f"Amount >$8000 (+{SCORE_WEIGHTS['amount_over_8000']:.2f})")
    elif claim.claim_amount > 5_000:
        score += SCORE_WEIGHTS["amount_over_5000"]
        factors.append(f"Amount >$5000 (+{SCORE_WEIGHTS['amount_over_5000']:.2f})")

    # LLM anomalies (soft signal, capped)
    n_anomalies = len(llm_result.get("anomalies", []))
    if n_anomalies:
        anomaly_contribution = min(n_anomalies * SCORE_WEIGHTS["llm_anomaly_per"], 0.15)
        score += anomaly_contribution
        factors.append(f"{n_anomalies} LLM anomaly signal(s) (+{anomaly_contribution:.2f})")

    score = min(score, 1.0)  # cap at 1.0

    # Classify
    if score >= 0.70:
        level = RiskLevel.HIGH
    elif score >= 0.35:
        level = RiskLevel.MEDIUM
    else:
        level = RiskLevel.LOW

    
    # In risk_scorer.py — replace the routing block at the bottom

    fraud_flags = {"LEGAL_THREAT_LANGUAGE", "REPEAT_CLAIM_SIGNAL"}
    warning_rules = {w["rule"] for w in validation_result.get("warnings", [])}
    has_fraud_signal = bool(fraud_flags & warning_rules)

# Get failure rules to check if it's delay-only
    failure_rules = {f["rule"] for f in validation_result.get("failures", [])}
    delay_only = failure_rules == {"EXCESSIVE_REPORTING_DELAY"}

    if n_failures > 0 and has_fraud_signal and score >= AUTO_REJECT_THRESHOLD and not delay_only:
        decision = DecisionOutcome.AUTO_REJECT
    elif score >= HUMAN_REVIEW_THRESHOLD:
        decision = DecisionOutcome.HUMAN_REVIEW
    else:
        decision = DecisionOutcome.AUTO_APPROVE

    # fraud_flags = {"LEGAL_THREAT_LANGUAGE", "REPEAT_CLAIM_SIGNAL"}
    # warning_rules = {w["rule"] for w in validation_result.get("warnings", [])}
    # has_fraud_signal = bool(fraud_flags & warning_rules)

    # if n_failures > 0 and has_fraud_signal and score >= AUTO_REJECT_THRESHOLD:
    #     decision = DecisionOutcome.AUTO_REJECT
    # elif score >= HUMAN_REVIEW_THRESHOLD:
    #     decision = DecisionOutcome.HUMAN_REVIEW
    # else:
    #     decision = DecisionOutcome.AUTO_APPROVE

    return {
        "score":    round(score, 3),
        "level":    level,
        "decision": decision,
        "factors":  factors,
    }