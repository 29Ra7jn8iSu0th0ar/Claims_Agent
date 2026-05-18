# app/models/claim.py
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Text, DateTime, JSON
from app.database import Base
from app.core.enums import ClaimStatus          # ← add this line

class Claim(Base):
    __tablename__ = "claims"

    id             = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Raw intake
    claimant_name  = Column(String, nullable=False)
    product_name   = Column(String, nullable=False)
    claim_amount   = Column(Float, nullable=False)
    incident_date  = Column(String, nullable=False)   # keep as string from user input
    description    = Column(Text, nullable=False)
    
    # Extracted fields (set by document_extractor)
    extracted_data = Column(JSON, default=dict)       # structured parse of description
    
    # Processing outputs
    status         = Column(String, default=ClaimStatus.SUBMITTED, nullable=False)
    risk_level     = Column(String, nullable=True)
    risk_score     = Column(Float, nullable=True)
    decision       = Column(String, nullable=True)
    
    # LLM-generated (explanation only, never decision)
    llm_reasoning  = Column(Text, nullable=True)
    llm_anomalies  = Column(Text, nullable=True)
    
    # Human review
    reviewer_id    = Column(String, nullable=True)
    reviewer_decision = Column(String, nullable=True)
    reviewer_note  = Column(Text, nullable=True)
    reviewed_at    = Column(DateTime, nullable=True)
    
    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)