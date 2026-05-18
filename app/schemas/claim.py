# app/schemas/claim.py
from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional

class ClaimSubmitRequest(BaseModel):
    claimant_name: str = Field(..., min_length=2)
    product_name:  str = Field(..., min_length=2)
    claim_amount:  float = Field(..., gt=0, le=50_000)  # hard ceiling
    incident_date: str   # validated below
    description:   str = Field(..., min_length=20)

    @validator("incident_date")
    def validate_date(cls, v):
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("incident_date must be YYYY-MM-DD")
        return v

class ClaimResponse(BaseModel):
    id:           str
    status:       str
    risk_level:   Optional[str]
    risk_score:   Optional[float]
    decision:     Optional[str]
    llm_reasoning: Optional[str]
    llm_anomalies: Optional[str]
    created_at:   datetime
    updated_at:   datetime

    class Config:
        from_attributes = True