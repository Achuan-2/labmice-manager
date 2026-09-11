import re
import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import or_, and_, case, func, literal

from backend.app.database import get_db
from backend.app.models.models import Mouse, Cage, Claimer, TransferLog, User, GenotypeRecord
from backend.app.schemas.schemas import (
    MouseResponse, MouseCreate, MouseUpdate,
    MouseBatchSetOwner, MouseBatchTransfer, MouseBatchSplitTransfer, MouseBatchUpdateStatus, MouseBatchUpdateFields, MouseBatchCreate,
    ParentsParseRequest
)
from backend.app.services.strain_service import normalize_strain_name
from backend.app.services.pedigree_service import parse_parents_detail, normalize_parents_pedigree
from backend.app.services.mouse_status_service import apply_mouse_status, ensure_mouse_status
from backend.app.services.owner_service import apply_owner_status, is_euthanasia_owner
from backend.app.auth import require_auth, require_admin

router = APIRouter(prefix="/api/mice", tags=["Mice"])
PARENT_SPLIT_PATTERN = r'[+、/,，\s\\]+'


def split_parent_tokens(value: Optional[str]) -> List[str]:
    tokens = [token.strip() for token in re.split(PARENT_SPLIT_PATTERN, str(value or "")) if token.strip()]
    return list(dict.fromkeys(token for token in tokens if re.fullmatch(r"[A-Za-z0-9_-]{1,32}", token) and re.search(r"\d", token)))


def normalized_parents_expression():
    expression = func.lower(func.coalesce(Mouse.parents, ""))
    for separator in ["+", "、", "/", "，", " ", "\\", "\t", "\n", "\r"]:
        expression = func.replace(expression, separator, ",")
    return literal(",") + expression + literal(",")


def natural_parent_key(value: str):
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", value)]


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

@router.post("/parse-parents")
def parse_parents_endpoint(
    data: ParentsParseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    return parse_parents_detail(db, data.parents)

def enrich_mouse_response(m: Mouse, db: Optional[Session] = None) -> Dict[str, Any]:
    """Calculate age in days/weeks, linked genotype records, and transfer logs"""
    age_days = None
    age_weeks = None
    if m.dob:
        try:
            parts = m.dob.split("-")
            if len(parts) == 3:
                dob_d = datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
                delta = datetime.date.today() - dob_d
                age_days = max(0, delta.days)
                age_weeks = round(age_days / 7.0, 1)
        except Exception:
            pass

    # Genotype history for this mouse
    gt_list = []
    if m.genotype_records:
        for g in m.genotype_records:
            gt_list.append({
                "id": g.id,
                "mouse_code": g.mouse_code,
                "test_date": g.test_date,
                "strain": g.strain,
                "parents": g.parents or m.parents,
                "genotype_1": g.genotype_1,
                "genotype_2": g.genotype_2,
                "genotype_3": g.genotype_3,
                "op_record": g.op_record,
                "notes": g.notes
            })
    elif db:
        # Fallback search by mouse_code
        records = db.query(GenotypeRecord).filter(GenotypeRecord.mouse_code == m.mouse_code).all()
        for g in records:
            gt_list.append({
                "id": g.id,
                "mouse_code": g.mouse_code,
                "test_date": g.test_date,
                "strain": g.strain,
                "parents": g.parents or m.parents,
                "genotype_1": g.genotype_1,
                "genotype_2": g.genotype_2,
                "genotype_3": g.genotype_3,
                "op_record": g.op_record,
                "notes": g.notes
            })

    # Transfer logs
    transfer_logs = []
    if db:
        possible_logs = db.query(TransferLog).filter(
            TransferLog.mouse_codes.ilike(f"%{m.mouse_code}%")
        ).order_by(TransferLog.id.desc()).all()
        logs = [
            log for log in possible_logs
            if m.mouse_code in {
                code.strip()
                for code in re.split(r"[,，、;\s]+", log.mouse_codes or "")
                if code.strip()
            }
        ][:15]
        for l in logs:
            transfer_logs.append({
                "id": l.id,
                "action_type": l.action_type,
                "claimer_name": l.claimer_name,
                "source_room": l.source_room,
                "target_room": l.target_room,
                "source_cage": l.source_cage,
                "target_cage": l.target_cage,
                "operator": l.operator,
                "date": l.date,
                "status": l.status,
                "notes": l.notes
            })

    return {
        "id": m.id,
        "mouse_code": m.mouse_code,
        "cage_id": m.cage_id,
        "cage_code": m.cage.cage_code if m.cage else None,
        "cage_room": m.cage.room if m.cage else m.source_room,
        "strain": m.strain,
        "gender": m.gender,
        "dob": m.dob,
        "age_days": age_days,
        "age_weeks": age_weeks,
        "parents": m.parents,
        "genotype_1": m.genotype_1,
        "genotype_2": m.genotype_2,
        "test_date": m.test_date,
        "genotypes": gt_list,
        "transfer_logs": transfer_logs,
        "owner_id": m.owner_id,
        "owner_name": m.owner_name,
        "status": m.status,
        "claim_date": m.claim_date,
        "claim_purpose": m.claim_purpose,
        "source_room": m.source_room,
        "notes": m.notes,
        "created_at": m.created_at,
        "updated_at": m.updated_at
    }

@router.get("")
def list_mice(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    keyword: Optional[str] = None,
    mouse_code: Optional[str] = None,
    room: Optional[str] = None,
    cage_code: Optional[str] = None,
    strain: Optional[str] = None,
    parents: Optional[str] = None,
    gender: Optional[str] = None,
    owner_name: Optional[str] = None,
    status: Optional[str] = None,
    has_owner: Optional[bool] = None,
    in_cage: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    query = db.query(Mouse).join(Mouse.cage, isouter=True)

    if mouse_code:
        query = query.filter(Mouse.mouse_code == mouse_code.strip())
    if keyword:
        k = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                Mouse.mouse_code.ilike(k),
                Mouse.strain.ilike(k),
                Mouse.parents.ilike(k),
                Mouse.notes.ilike(k),
                Mouse.owner_name.ilike(k),
                Mouse.genotype_1.ilike(k),
                Cage.cage_code.ilike(k)
            )
        )
    if room:
        query = query.filter(or_(Cage.room == room, Mouse.source_room == room))
    if cage_code:
        query = query.filter(Cage.cage_code == cage_code)
    if strain:
        query = query.filter(Mouse.strain == strain)
    parent_filters = split_parent_tokens(parents)
    if parent_filters:
        parent_expression = normalized_parents_expression()
        query = query.filter(or_(*(parent_expression.like(f"%,{parent.lower()},%") for parent in parent_filters)))
    if gender:
        query = query.filter(Mouse.gender == gender)
    if owner_name:
        query = query.filter(Mouse.owner_name == owner_name)
    if status:
        query = query.filter(Mouse.status == status)
    if in_cage is True:
        query = query.filter(Mouse.cage_id.isnot(None), Mouse.status != "出笼")
    elif in_cage is False:
        query = query.filter(Mouse.cage_id.is_(None))
    if has_owner is not None:
        if has_owner:
            query = query.filter(Mouse.owner_id.isnot(None))
        else:
            query = query.filter(Mouse.owner_id.is_(None))

    total = query.count()

    order_clauses = []
    if keyword:
        kw = keyword.strip()
        k = f"%{kw}%"
        k_prefix = f"{kw}%"
        relevance = case(
            (Mouse.mouse_code.ilike(kw), 1),
            (Mouse.mouse_code.ilike(k_prefix), 2),
            (Mouse.mouse_code.ilike(k), 3),
            (
                or_(
                    Mouse.strain.ilike(k),
                    Mouse.owner_name.ilike(k),
                    Mouse.genotype_1.ilike(k),
                    Mouse.notes.ilike(k),
                    Cage.cage_code.ilike(k)
                ),
                4
            ),
            (Mouse.parents.ilike(k), 5),
            else_=6
        )
        order_clauses.append(relevance)
    status_priority = case(
        (Mouse.status == "在笼", 0),
        (Mouse.status.in_(["出笼", "死亡"]), 2),
        else_=1,
    )
    order_clauses.append(status_priority)
    order_clauses.append(Mouse.id.desc())

    items = (
        query.options(
            joinedload(Mouse.cage),
            selectinload(Mouse.genotype_records)
        )
        .order_by(*order_clauses)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [enrich_mouse_response(m) for m in items]
    }

@router.get("/all-strains", response_model=List[str])
def get_all_strains(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    results = db.query(Mouse.strain).filter(Mouse.strain != "").distinct().all()
    strains = sorted([r[0] for r in results if r[0]])
    return strains


@router.get("/all-parents", response_model=List[str])
def get_all_parents(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    values = db.query(Mouse.parents).filter(Mouse.parents.isnot(None), Mouse.parents != "").distinct().all()
    parents = {token for (value,) in values for token in split_parent_tokens(value)}
    return sorted(parents, key=natural_parent_key)

@router.get("/by-code/{mouse_code}")
def get_mouse_by_code(
    mouse_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    code = mouse_code.strip()
    mouse = (
        db.query(Mouse)
        .options(
            joinedload(Mouse.cage),
            selectinload(Mouse.genotype_records)
        )
        .filter(Mouse.mouse_code == code)
        .first()
    )
    if not mouse:
        # Check partial match
        mouse = (
            db.query(Mouse)
            .options(
                joinedload(Mouse.cage),
                selectinload(Mouse.genotype_records)
            )
            .filter(Mouse.mouse_code.ilike(f"%{code}%"))
            .first()
        )
    if not mouse:
        # Check if there is a genotype record with this mouse_code
        gt = db.query(GenotypeRecord).filter(GenotypeRecord.mouse_code == code).first()
        if gt:
            return {
                "id": None,
                "mouse_code": gt.mouse_code,
                "cage_id": None,
                "cage_code": None,
                "cage_room": None,
                "strain": gt.strain or "",
                "gender": gt.gender or "未知",
                "dob": gt.dob,
                "age_days": None,
                "age_weeks": None,
                "parents": gt.parents,
                "genotype_1": gt.genotype_1,
                "genotype_2": gt.genotype_2,
                "test_date": gt.test_date,
                "genotypes": [{
                    "id": gt.id,
                    "mouse_code": gt.mouse_code,
                    "test_date": gt.test_date,
                    "strain": gt.strain,
                    "parents": gt.parents,
                    "genotype_1": gt.genotype_1,
                    "genotype_2": gt.genotype_2,
                    "genotype_3": gt.genotype_3,
                    "op_record": gt.op_record,
                    "notes": gt.notes
                }],
                "transfer_logs": [],
                "owner_id": None,
                "owner_name": None,
                "status": "出笼",
                "claim_date": None,
                "claim_purpose": None,
                "source_room": None,
                "notes": gt.notes
            }
        raise HTTPException(status_code=404, detail=f"未找到耳标 [{mouse_code}] 的小鼠档案")
    return enrich_mouse_response(mouse, db=db)

@router.get("/{mouse_id}")
def get_mouse(
    mouse_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    mouse = (
        db.query(Mouse)
        .options(
            joinedload(Mouse.cage),
            selectinload(Mouse.genotype_records)
        )
        .filter(Mouse.id == mouse_id)
        .first()
    )
    if not mouse:
        raise HTTPException(status_code=404, detail="小鼠未找到")
    return enrich_mouse_response(mouse, db=db)

@router.post("", response_model=Dict[str, Any])
def create_mouse(data: MouseCreate, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    requested_code = data.mouse_code.strip()
    mouse_code = next_available_mouse_code(db, requested_code)

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
        notes=data.notes
    )
    db.add(mouse)
    db.flush()
    db.query(GenotypeRecord).filter(
        GenotypeRecord.mouse_code == mouse.mouse_code,
        GenotypeRecord.mouse_id.is_(None),
    ).update({"mouse_id": mouse.id}, synchronize_session="fetch")
    db.commit()
    db.refresh(mouse)
    result = enrich_mouse_response(mouse)
    if mouse_code != requested_code:
        result["renamed_from"] = requested_code
        result["message"] = f"耳标编号 [{requested_code}] 已存在，已自动更名为 [{mouse_code}]"
    return result

@router.post("/batch-create")
def batch_create_mice(
    data: MouseBatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    raw_codes = []
    for item in data.mouse_codes:
        parts = re.split(r'[,，\s\n\r]+', str(item).strip())
        for p in parts:
            c = p.strip()
            if c and c not in raw_codes:
                raw_codes.append(c)

    if not raw_codes:
        raise HTTPException(status_code=400, detail="未检测到有效的小鼠耳标编号")

    occupied_codes = {row[0] for row in db.query(Mouse.mouse_code).all()}

    owner_id = None
    owner_name = data.owner_name.strip() if data.owner_name else None
    if owner_name:
        claimer = db.query(Claimer).filter(Claimer.name == owner_name).first()
        if not claimer:
            claimer = Claimer(name=owner_name)
            db.add(claimer)
            db.flush()
        owner_id = claimer.id

    cage_id = None
    if data.cage_code and data.source_room:
        cage = db.query(Cage).filter(Cage.cage_code == data.cage_code.strip(), Cage.room == data.source_room.strip()).first()
        if not cage:
            cage = Cage(cage_code=data.cage_code.strip(), room=data.source_room.strip(), strain=data.strain or "")
            db.add(cage)
            db.flush()
        cage_id = cage.id

    canonical_strain = normalize_strain_name(db, data.strain)
    canonical_parents = normalize_parents_pedigree(db, data.parents)

    requested_status = "死亡" if is_euthanasia_owner(owner_name) else data.status or ("在笼" if cage_id else "出笼")
    if not cage_id and requested_status in {"在笼", "已领用"}:
        requested_status = "出笼"
    try:
        status = ensure_mouse_status(db, requested_status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    created_mice = []
    renamed_mice = []
    for requested_code in raw_codes:
        code = next_available_mouse_code(db, requested_code, occupied_codes)
        if code != requested_code:
            renamed_mice.append({"original_code": requested_code, "new_code": code})
        occupied_codes.add(code)
        m = Mouse(
            mouse_code=code,
            strain=canonical_strain,
            gender=data.gender or "M",
            dob=data.dob,
            parents=canonical_parents,
            genotype_1=data.genotype_1,
            cage_id=cage_id if not status.removes_from_cage else None,
            source_room=data.source_room,
            owner_id=owner_id,
            owner_name=owner_name,
            status=status.name,
            notes=data.notes
        )
        db.add(m)
        created_mice.append(code)

    db.commit()

    msg = f"成功批量新增 {len(created_mice)} 只小鼠"
    if renamed_mice:
        rename_details = ", ".join(f"{item['original_code']} → {item['new_code']}" for item in renamed_mice)
        msg += f"（重复耳标已自动更名: {rename_details}）"

    return {
        "success": True,
        "created_count": len(created_mice),
        "created_codes": created_mice,
        "skipped_codes": [],
        "renamed_codes": renamed_mice,
        "message": msg
    }

@router.put("/{mouse_id}", response_model=Dict[str, Any])
def update_mouse(mouse_id: int, data: MouseUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    mouse = db.query(Mouse).filter(Mouse.id == mouse_id).first()
    if not mouse:
        raise HTTPException(status_code=404, detail="小鼠未找到")

    update_dict = data.model_dump(exclude_unset=True)

    if "mouse_code" in update_dict and update_dict["mouse_code"]:
        new_code = update_dict["mouse_code"].strip()
        if new_code != mouse.mouse_code:
            conflict = db.query(Mouse).filter(Mouse.mouse_code == new_code).first()
            if conflict:
                raise HTTPException(status_code=400, detail=f"耳标编号 [{new_code}] 已存在")
            old_code = mouse.mouse_code
            mouse.mouse_code = new_code
            # Also synchronize GenotypeRecord with new mouse_code
            db.query(GenotypeRecord).filter(GenotypeRecord.mouse_id == mouse.id).update({"mouse_code": new_code})
            db.query(GenotypeRecord).filter(GenotypeRecord.mouse_code == old_code).update({"mouse_code": new_code})

    if "strain" in update_dict and update_dict["strain"]:
        update_dict["strain"] = normalize_strain_name(db, update_dict["strain"])

    if "parents" in update_dict and update_dict["parents"]:
        update_dict["parents"] = normalize_parents_pedigree(db, update_dict["parents"])

    if "cage_code" in update_dict:
        cage_code_str = update_dict["cage_code"]
        if cage_code_str and cage_code_str.strip():
            room_name = update_dict.get("source_room") or mouse.source_room or (mouse.cage.room if mouse.cage else "默认鼠房")
            cage = db.query(Cage).filter(Cage.cage_code == cage_code_str.strip(), Cage.room == room_name).first()
            if not cage:
                cage = Cage(cage_code=cage_code_str.strip(), room=room_name, strain=mouse.strain or "")
                db.add(cage)
                db.flush()
            mouse.cage_id = cage.id
        else:
            mouse.cage_id = None

    if "owner_name" in update_dict:
        name = update_dict["owner_name"]
        if name and name.strip():
            claimer = db.query(Claimer).filter(Claimer.name == name.strip()).first()
            if not claimer:
                claimer = Claimer(name=name.strip())
                db.add(claimer)
                db.flush()
            mouse.owner_id = claimer.id
            mouse.owner_name = claimer.name
        else:
            mouse.owner_id = None
            mouse.owner_name = None
    elif "owner_id" in update_dict:
        claimer = db.get(Claimer, update_dict["owner_id"]) if update_dict["owner_id"] else None
        if update_dict["owner_id"] and not claimer:
            raise HTTPException(status_code=400, detail="领取人不存在")
        mouse.owner_id = claimer.id if claimer else None
        mouse.owner_name = claimer.name if claimer else None

    requested_status = update_dict.get("status")
    for k, v in update_dict.items():
        if k not in ["owner_name", "owner_id", "mouse_code", "cage_code", "status"]:
            setattr(mouse, k, v)

    if requested_status:
        try:
            apply_mouse_status(db, mouse, requested_status)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    elif "cage_code" in update_dict and mouse.cage_id is None:
        mouse.status = "出笼"
    elif "cage_code" in update_dict and mouse.cage_id is not None and mouse.status == "出笼":
        mouse.status = "已领用" if mouse.owner_id or mouse.owner_name else "在笼"
    apply_owner_status(db, mouse)

    db.commit()
    db.refresh(mouse)
    return enrich_mouse_response(mouse, db=db)

@router.delete("/{mouse_id}")
def delete_mouse(mouse_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    mouse = db.query(Mouse).filter(Mouse.id == mouse_id).first()
    if not mouse:
        raise HTTPException(status_code=404, detail="小鼠未找到")
    db.delete(mouse)
    db.commit()
    return {"message": "删除成功"}

# --- BATCH OPERATIONS ---
@router.post("/batch-update-fields")
def batch_update_fields(data: MouseBatchUpdateFields, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    mouse_ids = list(dict.fromkeys(data.mouse_ids))
    if not mouse_ids:
        raise HTTPException(status_code=400, detail="请至少选择一只小鼠")
    if len(mouse_ids) > 500:
        raise HTTPException(status_code=400, detail="每次最多批量编辑 500 只小鼠")

    updates = data.model_dump(exclude_unset=True, exclude={"mouse_ids"})
    if not updates:
        raise HTTPException(status_code=400, detail="请至少选择一个要修改的字段")
    if "gender" in updates and updates["gender"] not in {"M", "F", "未知"}:
        raise HTTPException(status_code=400, detail="请选择有效的性别")
    if "dob" in updates and updates["dob"]:
        try:
            datetime.date.fromisoformat(updates["dob"])
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="出生日期格式无效") from exc

    mice = db.query(Mouse).filter(Mouse.id.in_(mouse_ids)).all()
    if len(mice) != len(mouse_ids):
        raise HTTPException(status_code=404, detail="部分小鼠不存在，请刷新后重试")

    normalized_strain = None
    if "strain" in updates:
        raw_strain = str(updates["strain"] or "").strip()
        normalized_strain = normalize_strain_name(db, raw_strain) if raw_strain else ""

    for mouse in mice:
        if "dob" in updates:
            mouse.dob = updates["dob"] or None
        if "gender" in updates:
            mouse.gender = updates["gender"]
        if "strain" in updates:
            mouse.strain = normalized_strain
    db.commit()
    return {
        "success": True,
        "affected_count": len(mice),
        "message": f"成功批量更新 {len(mice)} 只小鼠",
    }

@router.post("/batch-set-owner")
def batch_set_owner(data: MouseBatchSetOwner, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    clean_owner = data.owner_name.strip()
    if not clean_owner:
        raise HTTPException(status_code=400, detail="领取人姓名不能为空")

    claimer = db.query(Claimer).filter(Claimer.name == clean_owner).first()
    if not claimer:
        claimer = Claimer(name=clean_owner, default_room=data.target_room)
        db.add(claimer)
        db.flush()

    query = db.query(Mouse)
    if data.mouse_ids:
        query = query.filter(Mouse.id.in_(data.mouse_ids))
    elif data.mouse_codes:
        query = query.filter(Mouse.mouse_code.in_(data.mouse_codes))
    else:
        raise HTTPException(status_code=400, detail="请至少提供小鼠ID或耳标编号")

    mice = query.all()
    if not mice:
        raise HTTPException(status_code=404, detail="未找到匹配的小鼠")

    today_str = data.claim_date or datetime.date.today().strftime("%Y-%m-%d")
    target_cage = None
    if data.target_cage_code and data.target_room:
        target_cage = db.query(Cage).filter(
            Cage.cage_code == data.target_cage_code.strip(),
            Cage.room == data.target_room.strip()
        ).first()
        if not target_cage:
            target_cage = Cage(
                cage_code=data.target_cage_code.strip(),
                room=data.target_room.strip(),
                strain=mice[0].strain if mice else "",
                gender=mice[0].gender if mice else "M"
            )
            db.add(target_cage)
            db.flush()

    affected_codes = []
    source_rooms = set()
    source_cages = set()

    for m in mice:
        if m.cage:
            source_cages.add(m.cage.cage_code)
            source_rooms.add(m.cage.room)
        elif m.source_room:
            source_rooms.add(m.source_room)

        m.owner_id = claimer.id
        m.owner_name = claimer.name
        m.claim_date = today_str
        if data.claim_purpose:
            m.claim_purpose = data.claim_purpose
        if target_cage:
            m.cage_id = target_cage.id
        if data.status:
            try:
                apply_mouse_status(db, m, data.status)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        apply_owner_status(db, m)
        if data.target_room:
            m.source_room = data.target_room

        affected_codes.append(m.mouse_code)

    log = TransferLog(
        action_type="设置领取人",
        mouse_codes=", ".join(affected_codes),
        mouse_count=len(affected_codes),
        claimer_name=claimer.name,
        source_room=", ".join(source_rooms) if source_rooms else "未知",
        target_room=data.target_room or (target_cage.room if target_cage else ", ".join(source_rooms)),
        source_cage=", ".join(source_cages) if source_cages else None,
        target_cage=data.target_cage_code or None,
        operator=current_user.display_name or current_user.username,
        date=today_str,
        status="已完成",
        notes=f"批量指派领取人: {claimer.name}; 目的: {data.claim_purpose or '无'}"
    )
    db.add(log)
    db.commit()

    return {
        "success": True,
        "message": f"成功为 {len(affected_codes)} 只小鼠指定领取人 [{claimer.name}]",
        "affected_count": len(affected_codes),
        "affected_codes": affected_codes
    }

@router.post("/batch-transfer")
def batch_transfer(data: MouseBatchTransfer, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    query = db.query(Mouse)
    if data.mouse_ids:
        query = query.filter(Mouse.id.in_(data.mouse_ids))
    elif data.mouse_codes:
        query = query.filter(Mouse.mouse_code.in_(data.mouse_codes))
    else:
        raise HTTPException(status_code=400, detail="请至少提供小鼠ID或耳标编号")

    mice = query.all()
    if not mice:
        raise HTTPException(status_code=404, detail="未找到匹配的小鼠")

    target_cage = None
    if data.target_cage_code:
        target_cage = db.query(Cage).filter(
            Cage.cage_code == data.target_cage_code.strip(),
            Cage.room == data.target_room.strip()
        ).first()
        if not target_cage:
            target_cage = Cage(
                cage_code=data.target_cage_code.strip(),
                room=data.target_room.strip(),
                strain=mice[0].strain if mice else "",
                gender=mice[0].gender if mice else "M"
            )
            db.add(target_cage)
            db.flush()

    affected_codes = []
    source_rooms = set()
    source_cages = set()

    for m in mice:
        if m.cage:
            source_cages.add(m.cage.cage_code)
            source_rooms.add(m.cage.room)
        elif m.source_room:
            source_rooms.add(m.source_room)

        if target_cage:
            m.cage_id = target_cage.id
        m.source_room = data.target_room
        if data.status:
            try:
                apply_mouse_status(db, m, data.status)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        affected_codes.append(m.mouse_code)

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    log = TransferLog(
        action_type="转房/换笼",
        mouse_codes=", ".join(affected_codes),
        mouse_count=len(affected_codes),
        source_room=", ".join(source_rooms) if source_rooms else "未知",
        target_room=data.target_room,
        source_cage=", ".join(source_cages) if source_cages else None,
        target_cage=data.target_cage_code,
        operator=current_user.display_name or current_user.username,
        date=today_str,
        status="已完成",
        notes=data.notes or f"转移至 {data.target_room}"
    )
    db.add(log)
    db.commit()

    return {
        "success": True,
        "message": f"成功转移 {len(affected_codes)} 只小鼠至 {data.target_room}" + (f" ({data.target_cage_code})" if data.target_cage_code else ""),
        "affected_count": len(affected_codes)
    }


@router.post("/batch-split-transfer")
def batch_split_transfer(data: MouseBatchSplitTransfer, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    if not data.groups:
        raise HTTPException(status_code=400, detail="请至少设置一个分笼目标")

    all_ids = [mouse_id for group in data.groups for mouse_id in group.mouse_ids]
    if not all_ids:
        raise HTTPException(status_code=400, detail="请至少选择一只小鼠")
    if len(all_ids) != len(set(all_ids)):
        raise HTTPException(status_code=400, detail="同一只小鼠不能分配到多个目标笼位")
    if len(all_ids) > 500:
        raise HTTPException(status_code=400, detail="每次最多批量换笼 500 只小鼠")

    mice_by_id = {mouse.id: mouse for mouse in db.query(Mouse).filter(Mouse.id.in_(all_ids)).all()}
    if len(mice_by_id) != len(all_ids):
        raise HTTPException(status_code=404, detail="部分小鼠不存在，请刷新后重试")

    operator = current_user.display_name or current_user.username
    total = 0
    for group in data.groups:
        if not group.mouse_ids:
            raise HTTPException(status_code=400, detail="每个目标笼位至少需要一只小鼠")
        room = group.target_room.strip()
        cage_code = group.target_cage_code.strip()
        if not room or not cage_code:
            raise HTTPException(status_code=400, detail="每组都必须指定目标鼠房和笼位")
        group_mice = [mice_by_id[mouse_id] for mouse_id in group.mouse_ids]
        if any(mouse.cage and mouse.cage.room == room and mouse.cage.cage_code == cage_code for mouse in group_mice):
            raise HTTPException(status_code=400, detail=f"目标笼位 {room} · {cage_code} 不能与小鼠当前笼位相同")
        target_cage = db.query(Cage).filter(Cage.room == room, Cage.cage_code == cage_code).first()
        if not target_cage:
            target_cage = Cage(cage_code=cage_code, room=room, strain=group_mice[0].strain or "", gender=group_mice[0].gender or "M")
            db.add(target_cage)
            db.flush()

        source_rooms = set()
        source_cages = set()
        for mouse in group_mice:
            if mouse.cage:
                source_rooms.add(mouse.cage.room)
                source_cages.add(mouse.cage.cage_code)
            elif mouse.source_room:
                source_rooms.add(mouse.source_room)
            mouse.cage_id = target_cage.id
            mouse.source_room = room

        codes = [mouse.mouse_code for mouse in group_mice]
        db.add(TransferLog(
            action_type="批量换笼",
            mouse_codes=", ".join(codes),
            mouse_count=len(codes),
            source_room=", ".join(source_rooms) if source_rooms else "未知",
            target_room=room,
            source_cage=", ".join(source_cages) if source_cages else None,
            target_cage=cage_code,
            operator=operator,
            date=datetime.date.today().strftime("%Y-%m-%d"),
            status="已完成",
            notes=data.notes or "生鼠批次满21天批量换笼",
        ))
        total += len(codes)

    db.commit()
    return {"success": True, "message": f"成功将 {total} 只小鼠分配到 {len(data.groups)} 个目标笼位", "affected_count": total}

@router.post("/batch-update-status")
def batch_update_status(data: MouseBatchUpdateStatus, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    mice = db.query(Mouse).filter(Mouse.id.in_(data.mouse_ids)).all()
    if not mice:
        raise HTTPException(status_code=404, detail="未找到匹配的小鼠")

    try:
        status = ensure_mouse_status(db, data.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    affected_codes = []
    source_groups = {}
    for m in mice:
        # Snapshot the original location before the status clears cage_id.
        source = (m.cage.room, m.cage.cage_code) if m.cage else (m.source_room, None)
        source_groups.setdefault(source, []).append(m.mouse_code)
        apply_mouse_status(db, m, status.name)
        if data.notes:
            m.notes = ((m.notes or "") + f" [{datetime.date.today()} {data.status}: {data.notes}]").strip()
        affected_codes.append(m.mouse_code)

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    for (source_room, source_cage), codes in source_groups.items():
        log = TransferLog(
            action_type="状态变更",
            mouse_codes=", ".join(codes),
            mouse_count=len(codes),
            source_room=source_room,
            source_cage=source_cage,
            operator=current_user.display_name or current_user.username,
            date=today_str,
            status="已完成",
            notes=f"批量将状态变更为: {data.status}. {data.notes or ''}"
        )
        db.add(log)
    db.commit()

    return {
        "success": True,
        "message": f"成功更新 {len(affected_codes)} 只小鼠状态为 [{data.status}]",
        "affected_count": len(affected_codes)
    }
