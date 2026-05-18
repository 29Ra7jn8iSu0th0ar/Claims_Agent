# app/services/orchestrator.py
"""
The main pipeline runner. Called by BackgroundTasks after claim submission.
Each step is wrapped in try/except — a failure in any step transitions
the claim to FAILED with a specific reason rather than crashing silently.
"""
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.claim import Claim
from app.core.enums import ClaimStatus, DecisionOutcome
from app.services.state_machine import ClaimStateMachine
from app.services.audit_logger import AuditLogger
from app.services.document_extractor import extract_claim_fields
from app.services.validator import DeterministicValidator
from app.services.llm_reasoner import analyze_claim
from app.services.risk_scorer import score_claim


def run_claim_pipeline(claim_id: str):
    """
    Each pipeline step is: try → transition → except → fail.
    A claim that enters this function will always exit in a terminal state.
    """
    db = SessionLocal()
    try:
        claim = db.query(Claim).filter(Claim.id == claim_id).first()
        if not claim:
            return  # shouldn't happen, but guard it

        audit = AuditLogger(db)
        sm = ClaimStateMachine(db, audit)

        # ── Step 1: SUBMITTED → ANALYZING ──────────────────────────────
        try:
            sm.transition(claim, ClaimStatus.ANALYZING, "system", "Pipeline started")
        except Exception as e:
            _fail(sm, claim, f"Could not start pipeline: {e}")
            return

        # ── Step 2: Document extraction (deterministic, always succeeds) ─
        try:
            extracted = extract_claim_fields(claim.description, claim.incident_date)
            claim.extracted_data = extracted
            db.add(claim)
            db.commit()
        except Exception as e:
            _fail(sm, claim, f"Extraction failed: {e}")
            return

        # ── Step 3: ANALYZING → VALIDATED ──────────────────────────────
        try:
            validator = DeterministicValidator(db)
            validation_result = validator.validate(claim)
            sm.transition(
                claim, ClaimStatus.VALIDATED,
                actor="system",
                reason="Deterministic validation complete",
                metadata=validation_result.to_dict(),
            )
        except Exception as e:
            _fail(sm, claim, f"Validation failed: {e}")
            return

        # ── Step 4: LLM reasoning (non-fatal if it fails) ───────────────
        llm_result = analyze_claim(claim, validation_result.to_dict())
        # Write LLM output to claim regardless of success
        claim.llm_reasoning = llm_result.get("reviewer_note", "")
        claim.llm_anomalies = "; ".join(llm_result.get("anomalies", []))
        db.add(claim)
        db.commit()

        # ── Step 5: VALIDATED → SCORED ──────────────────────────────────
        try:
            score_result = score_claim(claim, validation_result.to_dict(), llm_result)
            claim.risk_score  = score_result["score"]
            claim.risk_level  = score_result["level"]
            claim.decision    = score_result["decision"]
            db.add(claim)
            db.commit()

            sm.transition(
                claim, ClaimStatus.SCORED,
                actor="system",
                reason=f"Risk scored: {score_result['level']} ({score_result['score']})",
                metadata=score_result,
            )
        except Exception as e:
            _fail(sm, claim, f"Scoring failed: {e}")
            return

        # ── Step 6: Route by decision ────────────────────────────────────
        decision = DecisionOutcome(claim.decision)

        if decision == DecisionOutcome.AUTO_APPROVE:
            sm.transition(claim, ClaimStatus.APPROVED, "system",
                          "Auto-approved: low risk score")

        elif decision == DecisionOutcome.AUTO_REJECT:
            sm.transition(claim, ClaimStatus.REJECTED, "system",
                          "Auto-rejected: exceeded rejection threshold with hard failures")

        elif decision == DecisionOutcome.HUMAN_REVIEW:
            sm.transition(claim, ClaimStatus.ESCALATED, "system",
                          f"Escalated for human review: score={claim.risk_score}")

    finally:
        db.close()


def _fail(sm: ClaimStateMachine, claim: Claim, reason: str):
    """
    Transition to FAILED state. Always succeeds — if this fails too,
    the claim is stuck but at least the original exception is logged.
    """
    try:
        sm.transition(claim, ClaimStatus.FAILED, "system", reason)
    except Exception:
        pass  # If FAILED transition itself fails, we can't do much