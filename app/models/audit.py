# app/models/audit.py
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, JSON
from app.database import Base
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    claim_id    = Column(String, nullable=False, index=True)
    
    from_status = Column(String, nullable=True)   # null on creation
    to_status   = Column(String, nullable=False)
    actor       = Column(String, nullable=False)   # "system", "llm", "reviewer:{id}"
    reason      = Column(Text, nullable=False)     # must always have a reason
    # metadata    = Column(JSON, default=dict)       # risk_score, flags, anything extra
    extra_data  = Column(JSON, default=dict)
    
    timestamp   = Column(DateTime, default=datetime.utcnow, nullable=False)

    entry_hash    = Column(String, nullable=True)   # hash of this entry
    previous_hash = Column(String, nullable=True)   # hash of previous entry — forms chain