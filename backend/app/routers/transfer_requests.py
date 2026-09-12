import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.models import TransferRequest, TransferRequestAssignment, Mouse, User
from backend.app.services.transfer_assignment_service import reconcile_assignments, parse_codes
from backend.app.routers.mice import enrich_mouse_response
from backend.app.schemas.schemas import (
    TransferRequestCreate, TransferRequestUpdate, TransferRequestResponse
)
from backend.app.auth import require_auth, require_admin

router = APIRouter(prefix="/api/transfer-requests", tags=["Transfer Requests"])

@router.get("", response_model=List[TransferRequestResponse])
def list_transfer_requests(
    demander: Optional[str] = None,
    status: Optional[str] = None,
    strain: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    query = db.query(TransferRequest)
    if demander:
        query = query.filter(TransferRequest.demander.ilike(f"%{demander.strip()}%"))
    if status:
        query = query.filter(TransferRequest.status == status)
    if strain:
        query = query.filter(TransferRequest.strain.ilike(f"%{strain.strip()}%"))

    return query.order_by(TransferRequest.id.desc()).all()

@router.post("", response_model=TransferRequestResponse)
def create_transfer_request(
    data: TransferRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Both Guests and Admins can submit transfer/claim requests"""
    clean_demander = data.demander.strip()
    if not clean_demander:
        raise HTTPException(status_code=400, detail="需求者姓名不能为空")
    target_room = (data.target_room or "东五").strip()
    if not target_room:
        raise HTTPException(status_code=400, detail="期望转入鼠房不能为空")
    if len(target_room) > 64:
        raise HTTPException(status_code=400, detail="期望转入鼠房不能超过 64 个字符")

    today_str = data.request_date or datetime.date.today().strftime("%Y-%m-%d")

    # Generate sequence number
    count = db.query(TransferRequest).count()
    seq_val = str(count + 1)

    req = TransferRequest(
        seq=seq_val,
        request_date=today_str,
        demander=clean_demander,
        strain=data.strain.strip(),
        age_gender_req=data.age_gender_req or "成年/无要求",
        target_room=target_room,
        cage_count=data.cage_count or 1,
        source_room=data.source_room,
        mouse_gender=data.mouse_gender,
        mouse_codes=data.mouse_codes,
        status="申请中",
        feedback=data.feedback,
        handler=current_user.display_name or current_user.username
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req

@router.get("/{request_id}/assigned-mice")
def get_assigned_mice(request_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    req = db.get(TransferRequest, request_id)
    if req is None:
        raise HTTPException(404, "转鼠申请未找到")
    snapshots = {item.mouse_id: item for item in db.query(TransferRequestAssignment).filter_by(request_id=req.id).all()}
    codes = parse_codes(req.mouse_codes) if req.status == "已转" else []
    mice = db.query(Mouse).filter(Mouse.mouse_code.in_(codes)).all() if codes else []
    result = []
    for mouse in mice:
        item = enrich_mouse_response(mouse)
        snapshot = snapshots.get(mouse.id)
        item["assignment_source_room"] = snapshot.source_room if snapshot else item["cage_room"]
        item["assignment_source_cage"] = snapshot.source_cage if snapshot else item["cage_code"]
        item["assigned_to_request"] = True
        result.append(item)
    return result


@router.put("/{request_id}", response_model=TransferRequestResponse)
def process_transfer_request(
    request_id: int,
    data: TransferRequestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Admin processes transfer request (assign mice, update status, auto-link owner)"""
    req = db.query(TransferRequest).filter(TransferRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="转鼠申请未找到")

    update_dict = data.model_dump(exclude_unset=True)
    try:
        reconcile_assignments(db, req, update_dict, current_user.display_name or current_user.username)
        for k, v in update_dict.items():
            setattr(req, k, v)
        req.handler = current_user.display_name or current_user.username
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(req)
    return req

@router.delete("/{request_id}")
def delete_transfer_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    req = db.query(TransferRequest).filter(TransferRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="转鼠申请未找到")
    try:
        reconcile_assignments(db, req, {"status": "取消"}, current_user.display_name or current_user.username)
        db.flush()
        db.delete(req)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"message": "转鼠需求已删除"}
