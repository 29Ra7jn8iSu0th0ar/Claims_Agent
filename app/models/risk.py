import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Text, DateTime, JSON
from app.database import Base


class RiskScore(Base):
    """
    Stores the detailed risk scoring breakdown per claim.
    Kept separate from the Claim model so the scoring history
    is queryable independently (useful for model evaluation later).
    """
    __tablename__ = "risk_scores"

    id         = Column(String, primary_key=True,
                        default=lambda: str(uuid.uuid4()))
    claim_id   = Column(String, nullable=False, index=True)

    score      = Column(Float, nullable=False)
    level      = Column(String, nullable=False)   # low / medium / high
    decision   = Column(String, nullable=False)   # auto_approve / auto_reject / human_review

    # Human-readable breakdown of what drove the score
    factors    = Column(JSON, default=list)

    # Snapshot of the validation result at scoring time
    # Lets you replay exactly why a score was what it was
    validation_snapshot = Column(JSON, default=dict)

    # LLM anomaly count at scoring time
    llm_anomaly_count   = Column(Float, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id":          self.id,
            "claim_id":    self.claim_id,
            "score":       self.score,
            "level":       self.level,
            "decision":    self.decision,
            "factors":     self.factors,
            "created_at":  self.created_at.isoformat(),
        }