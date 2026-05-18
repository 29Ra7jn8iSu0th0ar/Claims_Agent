from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Any


class AuditLogResponse(BaseModel):
    id:          str
    claim_id:    str
    from_status: Optional[str]
    to_status:   str
    actor:       str
    reason:      str
    # metadata:    Optional[Any]
    extra_data:  dict[str, Any]
    timestamp:   datetime

    class Config:
        from_attributes = True