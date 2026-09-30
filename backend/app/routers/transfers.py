from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.models import TransferLog, User
from backend.app.schemas.schemas import TransferLogResponse, TransferLogCreate, TransferLogPageResponse
from backend.app.auth import require_auth, require_admin

router = APIRouter(prefix="/api/transfers", tags=["Transfers"])

@router.get("", response_model=TransferLogPageResponse)
def list_transfers(
    claimer_name: Optional[str] = None,
    action_type: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    query = db.query(TransferLog)
    if claimer_name:
        query = query.filter(TransferLog.claimer_name == claimer_name)
    if action_type:
        query = query.filter(TransferLog.action_type == action_type)
    if status:
        query = query.filter(TransferLog.status == status)

    total = query.count()
    items = (
        query.order_by(TransferLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}

@router.post("", response_model=TransferLogResponse)
def create_transfer_log(data: TransferLogCreate, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    log = TransferLog(
        action_type=data.action_type,
        mouse_codes=data.mouse_codes,
        mouse_count=data.mouse_count or 1,
        claimer_name=data.claimer_name,
        source_room=data.source_room,
        target_room=data.target_room,
        source_cage=data.source_cage,
        target_cage=data.target_cage,
        operator=current_user.display_name or current_user.username,
        date=data.date or "",
        status=data.status or "已完成",
        notes=data.notes
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
