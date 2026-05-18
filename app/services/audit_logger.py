# # app/services/audit_logger.py
# from datetime import datetime
# from sqlalchemy.orm import Session
# from app.models.audit import AuditLog

# class AuditLogger:
#     def __init__(self, db: Session):
#         self.db = db

#     def log(
#         self,
#         claim_id: str,
#         from_status,
#         to_status,
#         actor: str,
#         reason: str,
#         metadata: dict = None,
#     ):
#         """
#         Write synchronously within the same transaction as the state change.
#         If the claim transition rolls back, so does this log entry.
#         The audit log is never ahead of or behind the claim state.
#         """
#         entry = AuditLog(
#             claim_id=claim_id,
#             from_status=str(from_status) if from_status else None,
#             to_status=str(to_status),
#             actor=actor,
#             reason=reason,
#             # metadata=metadata or {},
#             extra_data=metadata or {},
#             timestamp=datetime.utcnow(),
#         )
#         self.db.add(entry)
#         # No commit here — caller commits the whole transaction atomically













import hashlib
import json
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.audit import AuditLog


def _compute_hash(entry_data: dict) -> str:
    """
    SHA-256 hash of this entry's content + previous entry's hash.
    Forms a chain — altering any entry breaks all subsequent hashes.
    """
    canonical = json.dumps(entry_data, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


class AuditLogger:
    def __init__(self, db: Session):
        self.db = db

    def _get_previous_hash(self, claim_id: str) -> str:
        """Get the hash of the most recent audit entry for this claim."""
        last = (
            self.db.query(AuditLog)
            .filter(AuditLog.claim_id == claim_id)
            .order_by(AuditLog.timestamp.desc())
            .first()
        )
        return last.entry_hash if (last and hasattr(last, 'entry_hash') and last.entry_hash) else "GENESIS"

    def log(self, claim_id, from_status, to_status, actor, reason, metadata=None) -> AuditLog:
        previous_hash = self._get_previous_hash(claim_id)
        timestamp     = datetime.utcnow()

        # Build the content that gets hashed
        entry_content = {
            "claim_id":     claim_id,
            "from_status":  str(from_status) if from_status else None,
            "to_status":    to_status.value if hasattr(to_status, "value") else str(to_status),
            "actor":        actor,
            "reason":       reason,
            "timestamp":    timestamp.isoformat(),
            "previous_hash": previous_hash,
        }
        entry_hash = _compute_hash(entry_content)

        entry = AuditLog(
            claim_id=claim_id,
            from_status=entry_content["from_status"],
            to_status=entry_content["to_status"],
            actor=actor,
            reason=reason,
            extra_data=metadata or {},
            timestamp=timestamp,
            entry_hash=entry_hash,
            previous_hash=previous_hash,
        )
        self.db.add(entry)
        return entry