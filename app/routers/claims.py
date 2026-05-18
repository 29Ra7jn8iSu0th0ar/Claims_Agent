# app/routers/claims.py
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.claim import ClaimSubmitRequest, ClaimResponse
from app.models.claim import Claim
from app.services.orchestrator import run_claim_pipeline  # built in step 11

router = APIRouter(prefix="/claims", tags=["claims"])

@router.post("/", response_model=ClaimResponse, status_code=202)
def submit_claim(
    payload: ClaimSubmitRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    202 Accepted — claim is created synchronously,
    pipeline runs asynchronously in the background.
    The caller polls GET /claims/{id} to check progress.
    
    Why not run synchronously? The LLM call can take 3-8 seconds.
    A synchronous endpoint would time out under load and give a
    terrible developer experience. 202 + polling is the correct pattern.
    """
    claim = Claim(
        claimant_name=payload.claimant_name,
        product_name=payload.product_name,
        claim_amount=payload.claim_amount,
        incident_date=payload.incident_date,
        description=payload.description,
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)

    # Schedule pipeline — runs after response is sent
    background_tasks.add_task(run_claim_pipeline, claim.id)

    return claim


@router.get("/{claim_id}", response_model=ClaimResponse)
def get_claim(claim_id: str, db: Session = Depends(get_db)):
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


@router.get("/{claim_id}/audit")
def get_audit_trail(claim_id: str, db: Session = Depends(get_db)):
    from app.models.audit import AuditLog
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.claim_id == claim_id)
        .order_by(AuditLog.timestamp.asc())
        .all()
    )
    return [
        {
            "from": log.from_status,
            "to":   log.to_status,
            "actor": log.actor,
            "reason": log.reason,
            "metadata": log.metadata,
            "timestamp": log.timestamp.isoformat(),
        }
        for log in logs
    ]