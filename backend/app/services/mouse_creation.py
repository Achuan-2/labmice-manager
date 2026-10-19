"""Shared mouse creation without committing the caller's transaction."""

import datetime
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.models.models import Cage, Claimer, GenotypeRecord, Mouse, TransferLog, User
from backend.app.schemas.schemas import MouseCreate
from backend.app.services.mouse_status_service import ensure_mouse_status
from backend.app.services.owner_service import is_euthanasia_owner
from backend.app.services.pedigree_service import normalize_parents_pedigree
from backend.app.services.strain_service import normalize_strain_name
from backend.app.services.genotype_service import ensure_pending_genotype_record


def next_available_mouse_code(db: Session, requested_code: str, occupied_codes: Optional[set[str]] = None) -> str:
    """Return the requested code, or append _2, _3, ... until it is unique."""
    code = requested_code.strip()

    def is_occupied(candidate: str) -> bool:
        if occupied_codes is not None:
            return candidate in occupied_codes
        return db.query(Mouse.id).filter(Mouse.mouse_code == candidate).first() is not None

    if not is_occupied(code):
        return code

    suffix_number = 2
    while True:
        suffix = f"_{suffix_number}"
        candidate = f"{code[:64 - len(suffix)]}{suffix}"
        if not is_occupied(candidate):
            return candidate
        suffix_number += 1


def record_mouse_creation(
    db: Session, mouse_codes: List[str], owner_name: Optional[str],
    room: Optional[str], cage_code: Optional[str], current_user: User,
) -> None:
    db.add(TransferLog(
        action_type="新增小鼠",
        mouse_codes=", ".join(mouse_codes),
        mouse_count=len(mouse_codes),
        claimer_name=owner_name,
        target_room=room,
        target_cage=cage_code,
        operator=current_user.display_name or current_user.username,
        date=datetime.date.today().isoformat(),
        status="已完成",
        notes="新增小鼠档案",
    ))


def create_mouse_in_session(
    data: MouseCreate, db: Session, current_user: User, *, occupied_codes: Optional[set[str]] = None,
) -> Mouse:
    """Create an archive, resolve code conflicts, link history and write its audit log."""
    mouse_code = next_available_mouse_code(db, data.mouse_code, occupied_codes)
    if occupied_codes is not None:
        occupied_codes.add(mouse_code)
    owner_id = data.owner_id
    owner_name = data.owner_name
    if owner_id:
        claimer = db.get(Claimer, owner_id)
        if not claimer:
            raise HTTPException(status_code=400, detail="领取人不存在")
        owner_name = claimer.name
    elif owner_name:
        claimer = db.query(Claimer).filter(Claimer.name == owner_name.strip()).first()
        if not claimer:
            claimer = Claimer(name=owner_name.strip())
            db.add(claimer)
            db.flush()
        owner_id = claimer.id
        owner_name = claimer.name

    canonical_strain = normalize_strain_name(db, data.strain)
    canonical_parents = normalize_parents_pedigree(db, data.parents)

    cage_id = data.cage_id
    if not cage_id and data.cage_code and data.cage_code.strip():
        room_name = (data.source_room or "默认鼠房").strip() or "默认鼠房"
        cage_code = data.cage_code.strip()
        cage = db.query(Cage).filter(Cage.cage_code == cage_code, Cage.room == room_name).first()
        if not cage:
            cage = Cage(cage_code=cage_code, room=room_name, strain=canonical_strain)
            db.add(cage)
            db.flush()
        cage_id = cage.id

    requested_status = "死亡" if is_euthanasia_owner(owner_name) else data.status or ("在笼" if cage_id else "出笼")
    if not cage_id and requested_status in {"在笼", "已领用"}:
        requested_status = "出笼"
    try:
        status = ensure_mouse_status(db, requested_status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    mouse = Mouse(
        mouse_code=mouse_code,
        cage_id=cage_id if not status.removes_from_cage else None,
        strain=canonical_strain,
        gender=data.gender or "未知",
        dob=data.dob,
        parents=canonical_parents,
        genotype_1=data.genotype_1,
        genotype_2=data.genotype_2,
        test_date=data.test_date,
        owner_id=owner_id,
        owner_name=owner_name,
        status=status.name,
        claim_date=data.claim_date,
        claim_purpose=data.claim_purpose,
        source_room=data.source_room,
        notes=data.notes,
    )
    db.add(mouse)
    db.flush()
    db.query(GenotypeRecord).filter(
        GenotypeRecord.mouse_code == mouse.mouse_code,
        GenotypeRecord.mouse_id.is_(None),
    ).update({"mouse_id": mouse.id}, synchronize_session="fetch")
    if mouse.status == "待鉴定":
        ensure_pending_genotype_record(mouse, db)
    target_cage = db.get(Cage, mouse.cage_id) if mouse.cage_id else None
    record_mouse_creation(
        db, [mouse.mouse_code], mouse.owner_name,
        target_cage.room if target_cage else mouse.source_room,
        target_cage.cage_code if target_cage else None, current_user,
    )
    return mouse
