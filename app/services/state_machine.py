# app/services/state_machine.py
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.claim import Claim
from app.core.enums import ClaimStatus
from app.services.audit_logger import AuditLogger

# Valid transitions — this dict IS the state machine.
# Any transition not in this map is illegal and will raise.
VALID_TRANSITIONS: dict[ClaimStatus, list[ClaimStatus]] = {
    ClaimStatus.SUBMITTED:  [ClaimStatus.ANALYZING, ClaimStatus.FAILED],
    ClaimStatus.ANALYZING:  [ClaimStatus.VALIDATED, ClaimStatus.FAILED],
    ClaimStatus.VALIDATED:  [ClaimStatus.SCORED,    ClaimStatus.FAILED],
    ClaimStatus.SCORED:     [ClaimStatus.ESCALATED, ClaimStatus.APPROVED, ClaimStatus.REJECTED],
    ClaimStatus.ESCALATED:  [ClaimStatus.APPROVED,  ClaimStatus.REJECTED],
    # Terminal states — no transitions allowed
    ClaimStatus.APPROVED:   [],
    ClaimStatus.REJECTED:   [],
    ClaimStatus.FAILED:     [],
}

class InvalidTransitionError(Exception):
    pass

class ClaimStateMachine:
    def __init__(self, db: Session, audit_logger: AuditLogger):
        self.db = db
        self.audit = audit_logger

    def transition(
        self,
        claim: Claim,
        to_status: ClaimStatus,
        actor: str,
        reason: str,
        metadata: dict = None,
    ) -> Claim:
        from_status = ClaimStatus(claim.status)

        # Guard: is this transition legal?
        allowed = VALID_TRANSITIONS.get(from_status, [])
        if to_status not in allowed:
            raise InvalidTransitionError(
                f"Illegal transition: {from_status} → {to_status} "
                f"for claim {claim.id}"
            )

        # Mutate
        claim.status = to_status
        claim.updated_at = datetime.utcnow()
        self.db.add(claim)

        # Always write audit before commit — if commit fails, audit entry
        # is rolled back too. That's correct: partial audit is worse than none.
        self.audit.log(
            claim_id=claim.id,
            from_status=from_status,
            to_status=to_status,
            actor=actor,
            reason=reason,
            metadata=metadata or {},
        )

        self.db.commit()
        self.db.refresh(claim)
        return claim

    def can_transition(self, claim: Claim, to_status: ClaimStatus) -> bool:
        from_status = ClaimStatus(claim.status)
        return to_status in VALID_TRANSITIONS.get(from_status, [])