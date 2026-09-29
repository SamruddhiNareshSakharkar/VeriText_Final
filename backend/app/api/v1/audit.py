from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.database.session import get_db
from backend.app.core.dependencies import get_current_teacher
from backend.app.models.entities import AuditLog, User
from backend.app.schemas.schemas import AuditLogOut

router = APIRouter(prefix="/audit", tags=["Audit Log"])

@router.get("", response_model=List[AuditLogOut])
def get_audit_logs(
    limit: int = Query(default=50, le=200),
    current_user: User = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    query = db.query(AuditLog)
    if current_user.role != "admin":
        query = query.filter(AuditLog.user_id == current_user.id)

    logs = query.order_by(AuditLog.created_at.desc()).limit(limit).all()

    return [
        AuditLogOut(
            id=log.id,
            user_id=log.user_id,
            user_name=log.user.full_name if log.user else "System",
            action=log.action,
            target_type=log.target_type,
            target_id=log.target_id,
            details=log.details_json or {},
            created_at=log.created_at
        )
        for log in logs
    ]
