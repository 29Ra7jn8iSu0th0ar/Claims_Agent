# app/models/policy.py
# PolicyRule is deterministic config — not LLM, not ML.
# These are the rules that can be audited by a regulator.

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime
from app.database import Base   
class PolicyRule(Base):
    __tablename__ = "policy_rules"

    id              = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_name       = Column(String, nullable=False, unique=True)
    product_category = Column(String, nullable=True)  # null = applies to all
    max_claim_amount = Column(Float, nullable=True)
    min_days_before_claim = Column(Integer, nullable=True)  # waiting period
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=datetime.utcnow)