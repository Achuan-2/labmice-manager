from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.auth import require_admin, require_auth
from backend.app.database import get_db
from backend.app.models.models import Mouse, MouseStatus, User
from backend.app.schemas.schemas import MouseStatusCreate, MouseStatusDelete, MouseStatusUpdate
from backend.app.services.mouse_status_service import clean_status_name, ensure_mouse_status, sync_mouse_statuses


router = APIRouter(prefix="/api/mouse-statuses", tags=["Mouse Statuses"])


def status_payload(status: MouseStatus, usage_count: int = 0):
    return {
        "id": status.id,
        "name": status.name,
        "is_system": status.is_system,
        "removes_from_cage": status.removes_from_cage,
        "sort_order": status.sort_order,
        "usage_count": usage_count,
    }


@router.get("")
def list_statuses(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    sync_mouse_statuses(db)
    counts = dict(db.query(Mouse.status, func.count(Mouse.id)).group_by(Mouse.status).all())
    statuses = db.query(MouseStatus).order_by(MouseStatus.sort_order, MouseStatus.id).all()
    return [status_payload(item, counts.get(item.name, 0)) for item in statuses]


@router.post("")
def create_status(
    data: MouseStatusCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        clean_name = clean_status_name(data.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if db.query(MouseStatus).filter(MouseStatus.name == clean_name).first():
        raise HTTPException(status_code=400, detail=f"状态 [{clean_name}] 已存在")
    status = ensure_mouse_status(db, clean_name)
    db.commit()
    db.refresh(status)
    return status_payload(status)


@router.put("/{status_id}")
def rename_status(
    status_id: int,
    data: MouseStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    status = db.query(MouseStatus).filter(MouseStatus.id == status_id).first()
    if not status:
        raise HTTPException(status_code=404, detail="状态未找到")
    if status.is_system:
        raise HTTPException(status_code=400, detail=f"系统状态 [{status.name}] 不可重命名")
    try:
        clean_name = clean_status_name(data.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    conflict = db.query(MouseStatus).filter(MouseStatus.name == clean_name, MouseStatus.id != status_id).first()
    if conflict:
        raise HTTPException(status_code=400, detail=f"状态 [{clean_name}] 已存在")

    old_name = status.name
    db.query(Mouse).filter(Mouse.status == old_name).update(
        {Mouse.status: clean_name}, synchronize_session=False
    )
    status.name = clean_name
    db.commit()
    usage_count = db.query(Mouse).filter(Mouse.status == clean_name).count()
    return status_payload(status, usage_count)


@router.delete("/{status_id}")
def delete_status(
    status_id: int,
    data: MouseStatusDelete,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    status = db.query(MouseStatus).filter(MouseStatus.id == status_id).first()
    if not status:
        raise HTTPException(status_code=404, detail="状态未找到")
    if status.is_system:
        raise HTTPException(status_code=400, detail=f"系统状态 [{status.name}] 不可删除")

    usage_count = db.query(Mouse).filter(Mouse.status == status.name).count()
    replacement = None
    if usage_count:
        if not data.replacement_status:
            raise HTTPException(
                status_code=409,
                detail=f"仍有 {usage_count} 只小鼠使用该状态，请先选择迁移到其他状态",
            )
        replacement = db.query(MouseStatus).filter(
            MouseStatus.name == data.replacement_status.strip(),
            MouseStatus.id != status.id,
        ).first()
        if not replacement:
            raise HTTPException(status_code=400, detail="请选择有效的目标状态")
        updates = {Mouse.status: replacement.name}
        if replacement.removes_from_cage:
            updates[Mouse.cage_id] = None
        db.query(Mouse).filter(Mouse.status == status.name).update(
            updates, synchronize_session=False
        )

    deleted_name = status.name
    db.delete(status)
    db.commit()
    return {
        "success": True,
        "message": f"状态 [{deleted_name}] 已删除" + (f"，{usage_count} 只小鼠已迁移至 [{replacement.name}]" if replacement else ""),
        "migrated_count": usage_count,
    }
