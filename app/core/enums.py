# app/core/enums.py
from enum import Enum

class ClaimStatus(str, Enum):
    SUBMITTED   = "submitted"
    ANALYZING   = "analyzing"
    VALIDATED   = "validated"
    SCORED      = "scored"
    ESCALATED   = "escalated"    # awaiting human review
    APPROVED    = "approved"
    REJECTED    = "rejected"
    FAILED      = "failed"       # pipeline error — never silently swallow

class RiskLevel(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"

class DecisionOutcome(str, Enum):
    AUTO_APPROVE  = "auto_approve"
    AUTO_REJECT   = "auto_reject"
    HUMAN_REVIEW  = "human_review"