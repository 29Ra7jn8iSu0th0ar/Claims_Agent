# app/routers/review.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import get_db
from app.models.claim import Claim
from app.core.enums import ClaimStatus, DecisionOutcome
from app.services.state_machine import ClaimStateMachine
from app.services.audit_logger import AuditLogger

router = APIRouter(prefix="/claims", tags=["review"])

class ReviewDecision(BaseModel):
    reviewer_id: str
    decision: str        # "approved" | "rejected"
    note: str

@router.post("/{claim_id}/review")
def submit_review(
    claim_id: str,
    payload: ReviewDecision,
    db: Session = Depends(get_db),
):
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(404, "Claim not found")
    
    if claim.status != ClaimStatus.ESCALATED:
        raise HTTPException(
            400,
            f"Claim is in status '{claim.status}', not 'escalated'. Cannot review."
        )

    if payload.decision not in ("approved", "rejected"):
        raise HTTPException(400, "Decision must be 'approved' or 'rejected'")

    # Map string to enum
    to_status = (
        ClaimStatus.APPROVED if payload.decision == "approved"
        else ClaimStatus.REJECTED
    )

    # Record reviewer data on the claim
    claim.reviewer_id       = payload.reviewer_id
    claim.reviewer_decision = payload.decision
    claim.reviewer_note     = payload.note
    claim.reviewed_at       = datetime.utcnow()

    audit = AuditLogger(db)
    sm = ClaimStateMachine(db, audit)
    sm.transition(
        claim=claim,
        to_status=to_status,
        actor=f"reviewer:{payload.reviewer_id}",
        reason=payload.note,
        metadata={"reviewer_decision": payload.decision},
    )

    return {
        "claim_id": claim.id,
        "final_status": claim.status,
        "reviewed_by": payload.reviewer_id,
        "reviewed_at": claim.reviewed_at.isoformat(),
    }