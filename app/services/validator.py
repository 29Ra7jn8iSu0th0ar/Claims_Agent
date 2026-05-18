# app/services/validator.py
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.claim import Claim
from app.models.policy import PolicyRule


class ValidationResult:
    def __init__(self):
        self.passed = True
        self.failures: list[dict] = []
        self.warnings: list[dict] = []

    def fail(self, rule: str, reason: str):
        self.passed = False
        self.failures.append({"rule": rule, "reason": reason})

    def warn(self, rule: str, reason: str):
        self.warnings.append({"rule": rule, "reason": reason})

    def to_dict(self):
        return {
            "passed":   self.passed,
            "failures": self.failures,
            "warnings": self.warnings,
        }


class DeterministicValidator:
    def __init__(self, db: Session):
        self.db = db

    def validate(self, claim: Claim) -> ValidationResult:
        result    = ValidationResult()
        extracted = claim.extracted_data or {}

        # ── Hard rules (failures block auto-processing) ───────────────────

        # Rule 1: Claim amount ceiling
        if claim.claim_amount > 10_000:
            result.fail(
                "MAX_AMOUNT_EXCEEDED",
                f"Claim amount ${claim.claim_amount} exceeds auto-processing ceiling of $10,000"
            )

        # Rule 2: Incident date not in the future
        try:
            incident = datetime.strptime(claim.incident_date, "%Y-%m-%d")
            if incident > datetime.utcnow():
                result.fail(
                    "FUTURE_INCIDENT_DATE",
                    f"Incident date {claim.incident_date} is in the future"
                )
        except ValueError:
            result.fail("INVALID_DATE_FORMAT", "Incident date could not be parsed")

        # Rule 3: Waiting period — must be 30+ days since incident
        days_since = extracted.get("days_since_incident")
        if days_since is not None and days_since < 30:
            result.fail(
                "WAITING_PERIOD_VIOLATION",
                f"Only {days_since} days since incident. Minimum waiting period is 30 days."
            )

        # Rule 4: Minimum description quality
        if extracted.get("description_word_count", 0) < 10:
            result.fail(
                "INSUFFICIENT_DESCRIPTION",
                "Claim description is too brief to process"
            )

        # Rule 5: Excessive reporting delay
        # Most warranty policies require claims within 30-90 days of incident
        if days_since is not None and days_since > 90:
            result.fail(
                "EXCESSIVE_REPORTING_DELAY",
                f"Claim reported {days_since} days after incident. "
                f"Maximum allowed reporting window is 90 days."
            )


        # ── Soft rules (warnings raise risk score but don't block) ─────────

        urgency_flags = extracted.get("urgency_flags", [])

        if "legal_threat" in urgency_flags:
            result.warn("LEGAL_THREAT_LANGUAGE",
                        "Description contains legal threat language")

        if "repeat_claim_language" in urgency_flags:
            result.warn("REPEAT_CLAIM_SIGNAL",
                        "Description suggests a prior claim on this product")

        if claim.claim_amount > 5_000:
            result.warn("HIGH_VALUE_CLAIM",
                        f"Claim amount ${claim.claim_amount} is above $5,000")

        if extracted.get("damage_types") == ["unclassified"]:
            result.warn("UNCLASSIFIED_DAMAGE",
                        "Could not classify damage type from description")

        # ── Gap 2: Ambiguity guardrail (fulfillment confusion prevention) ──
        # Detects vague submissions before committing to a decision.
        # Addresses the exact merchant trust problem — they need to know
        # WHY a decision was made. Ambiguous claims get flagged first.

        ambiguity_score = 0

        if extracted.get("damage_types") == ["unclassified"]:
            ambiguity_score += 1   # couldn't classify what actually happened

        if extracted.get("description_word_count", 0) < 20:
            ambiguity_score += 1   # description too short to reason about

        if not extracted.get("urgency_flags") and claim.claim_amount > 3_000:
            ambiguity_score += 1   # high value claim with zero signal — suspicious

        if ambiguity_score >= 2:
            result.warn(
                "AMBIGUOUS_SUBMISSION",
                "Claim lacks sufficient detail for confident automated processing. "
                "Recommend requesting additional evidence before decision."
            )

        return result