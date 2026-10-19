import datetime
from typing import Annotated, List, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import case, func, or_

from backend.app.database import get_db
from backend.app.models.models import GenotypeRecord, Mouse, User
from backend.app.schemas.schemas import (
    GenotypeBatchFill, GenotypeEntryCheck, GenotypeRecordCreate, GenotypeRecordUpdate, GenotypeRecordResponse,
    MouseCreate,
)
from backend.app.auth import require_auth, require_admin
from backend.app.services.genotype_service import (
    genotype_result_condition, has_genotype_result, normalize_genotype_value,
    next_genotype_entry_order,
    sync_mouse_genotype_summary as _sync_mouse_genotype_summary,
    sync_mouse_genotyping_status,
)
from backend.app.services.mouse_creation import create_mouse_in_session

router = APIRouter(prefix="/api/genotypes", tags=["Genotypes"])


@router.get("")
def list_genotypes(
    page: Optional[int] = None,
    page_size: Optional[int] = Query(50, ge=1, le=500),
    keyword: Optional[str] = None,
    mouse_code: Optional[str] = None,
    strain: Optional[str] = None,
    genotype_1: Optional[str] = None,
    genotype_1_values: Annotated[Optional[List[str]], Query()] = None,
    genotype_2_values: Annotated[Optional[List[str]], Query()] = None,
    genotype_3_values: Annotated[Optional[List[str]], Query()] = None,
    parents: Optional[str] = None,
    test_status: Optional[Literal["pending", "tested"]] = None,
    sort_by: Literal["added", "test_date"] = "added",
    sort_order: Literal["asc", "desc"] = "desc",
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    query = db.query(GenotypeRecord)
    if test_status:
        condition = genotype_result_condition()
        query = query.filter(condition if test_status == "tested" else ~condition)
    if keyword:
        k = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                GenotypeRecord.mouse_code.ilike(k),
                GenotypeRecord.strain.ilike(k),
                GenotypeRecord.parents.ilike(k),
                GenotypeRecord.genotype_1.ilike(k),
                GenotypeRecord.genotype_2.ilike(k),
                GenotypeRecord.genotype_3.ilike(k),
                GenotypeRecord.notes.ilike(k)
            )
        )
    if mouse_code:
        query = query.filter(GenotypeRecord.mouse_code.ilike(f"%{mouse_code.strip()}%"))
    if strain:
        query = query.filter(GenotypeRecord.strain == strain)
    if genotype_1:
        query = query.filter(GenotypeRecord.genotype_1 == genotype_1)
    # Match any selected value within a column, and require all selected columns.
    # Empty selection values include NULL and blank records shown as “未填写”.
    for column, values in (
        (GenotypeRecord.genotype_1, genotype_1_values),
        (GenotypeRecord.genotype_2, genotype_2_values),
        (GenotypeRecord.genotype_3, genotype_3_values),
    ):
        if values:
            query = query.filter(func.coalesce(func.trim(column), "").in_([value.strip() for value in values]))
    if parents:
        query = query.filter(GenotypeRecord.parents.ilike(f"%{parents.strip()}%"))

    order_clauses = []
    if keyword:
        kw = keyword.strip()
        k = f"%{kw}%"
        k_prefix = f"{kw}%"
        relevance = case(
            (GenotypeRecord.mouse_code.ilike(kw), 1),
            (GenotypeRecord.mouse_code.ilike(k_prefix), 2),
            (GenotypeRecord.mouse_code.ilike(k), 3),
            (
                or_(
                    GenotypeRecord.strain.ilike(k),
                    GenotypeRecord.genotype_1.ilike(k),
                    GenotypeRecord.genotype_2.ilike(k),
                    GenotypeRecord.genotype_3.ilike(k),
                    GenotypeRecord.notes.ilike(k),
                ),
                4
            ),
            (GenotypeRecord.parents.ilike(k), 5),
            else_=6
        )
        order_clauses.append(relevance)

    # A separate order allows recovering Excel row order without renumbering IDs.
    if sort_by == "test_date":
        missing_date = func.coalesce(func.trim(GenotypeRecord.test_date), "") == ""
        order_clauses.append(case((missing_date, 1), else_=0))
        order_clauses.append(
            GenotypeRecord.test_date.asc() if sort_order == "asc" else GenotypeRecord.test_date.desc()
        )
    entry_order = func.coalesce(GenotypeRecord.entry_order, GenotypeRecord.id)
    order_clauses.extend([
        entry_order.asc() if sort_order == "asc" else entry_order.desc(),
        GenotypeRecord.id.asc() if sort_order == "asc" else GenotypeRecord.id.desc(),
    ])
    query = query.order_by(*order_clauses)

    if page is not None:
        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        result_items = []
        for gt in items:
            p = gt.parents
            if (not p or p.strip() == "") and gt.mouse and gt.mouse.parents:
                p = gt.mouse.parents
            result_items.append({
                "id": gt.id,
                "mouse_id": gt.mouse_id or (gt.mouse.id if gt.mouse else None),
                "mouse_code": gt.mouse_code,
                "test_date": gt.test_date,
                "strain": gt.strain or (gt.mouse.strain if gt.mouse else ""),
                "dob": gt.mouse.dob if gt.mouse else gt.dob,
                "gender": gt.gender or (gt.mouse.gender if gt.mouse else None),
                "parents": p,
                "genotype_1": gt.genotype_1,
                "genotype_2": gt.genotype_2,
                "genotype_3": gt.genotype_3,
                "op_record": gt.op_record,
                "notes": gt.notes,
                "created_at": gt.created_at
            })
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": result_items
        }

    items = query.limit(limit).all()
    result_items = []
    for gt in items:
        p = gt.parents
        if (not p or p.strip() == "") and gt.mouse and gt.mouse.parents:
            p = gt.mouse.parents
        result_items.append({
            "id": gt.id,
            "mouse_id": gt.mouse_id or (gt.mouse.id if gt.mouse else None),
            "mouse_code": gt.mouse_code,
            "test_date": gt.test_date,
            "strain": gt.strain or (gt.mouse.strain if gt.mouse else ""),
            "dob": gt.mouse.dob if gt.mouse else gt.dob,
            "gender": gt.gender or (gt.mouse.gender if gt.mouse else None),
            "parents": p,
            "genotype_1": gt.genotype_1,
            "genotype_2": gt.genotype_2,
            "genotype_3": gt.genotype_3,
            "op_record": gt.op_record,
            "notes": gt.notes,
            "created_at": gt.created_at
        })
    return result_items

@router.get("/filter-options")
def get_genotype_filter_options(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Return distinct values from all records, independently of pagination."""
    options = {}
    for field in ("genotype_1", "genotype_2", "genotype_3"):
        value = func.coalesce(func.trim(getattr(GenotypeRecord, field)), "")
        rows = db.query(value).distinct().order_by(value).all()
        options[field] = [row[0] for row in rows]
    return options


@router.get("/by-mouse/{mouse_code}", response_model=List[GenotypeRecordResponse])
def get_genotypes_by_mouse(
    mouse_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    return db.query(GenotypeRecord).filter(GenotypeRecord.mouse_code == mouse_code.strip()).order_by(GenotypeRecord.id.desc()).all()


@router.post("/entry-check")
def check_genotype_entry(
    data: GenotypeEntryCheck,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Check exact codes in one batch, including history without a mouse archive."""
    codes = list(dict.fromkeys(code.strip() for code in data.mouse_codes))
    if any(not code for code in codes):
        raise HTTPException(status_code=422, detail="耳标编号不能为空")
    mice = {mouse.mouse_code: mouse for mouse in db.query(Mouse).filter(Mouse.mouse_code.in_(codes)).all()}
    history = {code: [] for code in codes}
    records = (
        db.query(GenotypeRecord)
        .filter(GenotypeRecord.mouse_code.in_(codes))
        .order_by(GenotypeRecord.test_date.desc(), GenotypeRecord.id.desc())
        .all()
    )
    for record in records:
        history[record.mouse_code].append(record)

    entries = []
    for code in codes:
        mouse = mice.get(code)
        records = history[code]
        tested = [record for record in records if has_genotype_result(
            record.genotype_1, record.genotype_2, record.genotype_3,
        )]
        # Older imports may store results only in the mouse archive.
        if not tested and mouse and has_genotype_result(mouse.genotype_1, mouse.genotype_2):
            tested = [mouse]
        source = mouse or (records[0] if records else None)
        entries.append({
            "mouse_code": code,
            "mouse_id": mouse.id if mouse else None,
            **{field: getattr(source, field, None) for field in ("strain", "parents", "gender", "dob")},
            "tested_records": [
                {
                    "test_date": record.test_date,
                    **{field: getattr(record, field, None) for field in (
                        "genotype_1", "genotype_2", "genotype_3", "op_record", "notes",
                    )},
                }
                for record in tested
            ],
            "pending_count": sum(not has_genotype_result(
                record.genotype_1, record.genotype_2, record.genotype_3,
            ) for record in records),
        })
    return entries


@router.post("", response_model=GenotypeRecordResponse)
def create_genotype_record(
    data: GenotypeRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    try:
        gt = _add_genotype_record(data, db, current_user)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(gt)
    return gt


def _add_genotype_record(
    data: GenotypeRecordCreate, db: Session, current_user: User, occupied_codes: Optional[set[str]] = None,
) -> GenotypeRecord:
    clean_code = data.mouse_code.strip()
    if not clean_code or any(separator in clean_code for separator in (",", "，", "、", "\n")):
        raise HTTPException(status_code=422, detail="每条鉴定记录需提供一个有效耳标编号")
    mouse = db.query(Mouse).filter(Mouse.mouse_code == clean_code).first()
    if not data.create_new_mouse and not data.confirm_existing:
        existing_record = db.query(GenotypeRecord.id).filter(GenotypeRecord.mouse_code == clean_code).first()
        if existing_record or (mouse and has_genotype_result(mouse.genotype_1, mouse.genotype_2)):
            raise HTTPException(status_code=409, detail=f"小鼠 [{clean_code}] 已有鉴定记录或结果，请核对并确认再次登记")

    mouse_created = data.create_new_mouse or mouse is None
    if mouse_created:
        source = None
        if not data.create_new_mouse:
            source = db.query(GenotypeRecord).filter(GenotypeRecord.mouse_code == clean_code).order_by(
                GenotypeRecord.test_date.desc(), GenotypeRecord.id.desc(),
            ).first()
        if data.create_new_mouse and occupied_codes is None:
            occupied_codes = _occupied_mouse_codes(db)
        mouse = create_mouse_in_session(MouseCreate(
            mouse_code=clean_code,
            strain=data.strain or (source.strain if source else ""),
            dob=data.dob or (source.dob if source else None),
            gender=data.gender or (source.gender if source else None),
            parents=data.parents or (source.parents if source else None),
            notes=data.notes,
        ), db, current_user, occupied_codes=occupied_codes if data.create_new_mouse else None)
        if occupied_codes is not None:
            occupied_codes.add(mouse.mouse_code)

    gt = GenotypeRecord(
        entry_order=next_genotype_entry_order(db),
        mouse_code=mouse.mouse_code,
        mouse_id=mouse.id,
        test_date=data.test_date or (
            datetime.date.today().isoformat()
            if has_genotype_result(data.genotype_1, data.genotype_2, data.genotype_3) else None
        ),
        strain=mouse.strain if mouse_created else data.strain or mouse.strain,
        dob=data.dob or mouse.dob,
        gender=data.gender or mouse.gender,
        parents=mouse.parents if mouse_created else data.parents or mouse.parents,
        genotype_1=data.genotype_1,
        genotype_2=data.genotype_2,
        genotype_3=data.genotype_3,
        op_record=data.op_record or current_user.display_name or current_user.username,
        notes=data.notes
    )
    # Response-only fields tell the caller which archives and codes were created.
    gt.mouse_created = mouse_created
    gt.renamed_from = clean_code if mouse.mouse_code != clean_code else None
    db.add(gt)

    # Sync to mouse record
    if data.dob:
        mouse.dob = data.dob
    if data.gender and mouse.gender == "未知":
        mouse.gender = data.gender
    db.flush()
    if mouse_created or has_genotype_result(gt.genotype_1, gt.genotype_2, gt.genotype_3):
        _sync_mouse_genotype_summary(mouse, db)
    else:
        sync_mouse_genotyping_status(mouse, db)

    return gt


def _occupied_mouse_codes(db: Session) -> set[str]:
    """New animals must not inherit history belonging to an unarchived mouse."""
    return {row[0] for row in db.query(Mouse.mouse_code).all()} | {
        row[0] for row in db.query(GenotypeRecord.mouse_code).distinct().all()
    }


@router.post("/batch", response_model=List[GenotypeRecordResponse])
def create_genotype_records(
    data: List[GenotypeRecordCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    if not data or len(data) > 500:
        raise HTTPException(status_code=422, detail="每次请录入 1–500 个耳标编号")
    codes = [item.mouse_code.strip() for item in data]
    if len(codes) != len(set(codes)):
        raise HTTPException(status_code=422, detail="耳标编号不能重复")
    try:
        occupied_codes = _occupied_mouse_codes(db) if any(item.create_new_mouse for item in data) else None
        records = [_add_genotype_record(item, db, current_user, occupied_codes) for item in data]
        db.commit()
    except Exception:
        db.rollback()
        raise
    for record in records:
        db.refresh(record)
    return records

@router.put("/batch-fill")
def fill_genotype_records(
    data: GenotypeBatchFill,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Fill one result column atomically, preserving all other record fields."""
    ids = set(data.record_ids)
    records = db.query(GenotypeRecord).filter(GenotypeRecord.id.in_(ids)).all()
    if len(records) != len(ids):
        raise HTTPException(status_code=404, detail="部分鉴定记录不存在，请刷新后重试")
    value = normalize_genotype_value(data.value)
    codes = set()
    try:
        for record in records:
            was_tested = has_genotype_result(record.genotype_1, record.genotype_2, record.genotype_3)
            setattr(record, data.field, value)
            is_tested = has_genotype_result(record.genotype_1, record.genotype_2, record.genotype_3)
            if was_tested or is_tested:
                codes.add(record.mouse_code)
            if not was_tested and is_tested and not record.test_date:
                record.test_date = datetime.date.today().isoformat()
        db.flush()
        affected_codes = {record.mouse_code for record in records}
        for mouse in db.query(Mouse).filter(Mouse.mouse_code.in_(affected_codes)).all():
            if mouse.mouse_code in codes:
                _sync_mouse_genotype_summary(mouse, db)
            else:
                sync_mouse_genotyping_status(mouse, db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {
        "updated": len(records),
        "items": [
            {
                "id": record.id, "test_date": record.test_date,
                "genotype_1": record.genotype_1, "genotype_2": record.genotype_2,
                "genotype_3": record.genotype_3,
            }
            for record in records
        ],
    }


@router.put("/{genotype_id}", response_model=GenotypeRecordResponse)
def update_genotype_record(
    genotype_id: int,
    data: GenotypeRecordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    gt = db.query(GenotypeRecord).filter(GenotypeRecord.id == genotype_id).first()
    if not gt:
        raise HTTPException(status_code=404, detail="鉴定记录未找到")

    was_tested = has_genotype_result(gt.genotype_1, gt.genotype_2, gt.genotype_3)
    update_dict = data.model_dump(exclude_unset=True)
    for k, v in update_dict.items():
        setattr(gt, k, v)

    is_tested = has_genotype_result(gt.genotype_1, gt.genotype_2, gt.genotype_3)
    if not was_tested and is_tested and not gt.test_date:
        gt.test_date = datetime.date.today().isoformat()
    db.flush()
    mouse = gt.mouse or db.query(Mouse).filter(Mouse.mouse_code == gt.mouse_code).first()
    if mouse and "dob" in update_dict:
        mouse.dob = update_dict["dob"] or None
    if was_tested or is_tested:
        _sync_mouse_genotype_summary(mouse, db)
    else:
        sync_mouse_genotyping_status(mouse, db)
    db.commit()
    db.refresh(gt)
    return gt

@router.delete("/{genotype_id}")
def delete_genotype_record(
    genotype_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    gt = db.query(GenotypeRecord).filter(GenotypeRecord.id == genotype_id).first()
    if not gt:
        raise HTTPException(status_code=404, detail="鉴定记录未找到")
    was_tested = has_genotype_result(gt.genotype_1, gt.genotype_2, gt.genotype_3)
    mouse = gt.mouse or db.query(Mouse).filter(Mouse.mouse_code == gt.mouse_code).first()
    db.delete(gt)
    db.flush()
    if was_tested:
        _sync_mouse_genotype_summary(mouse, db)
    else:
        sync_mouse_genotyping_status(mouse, db)
    db.commit()
    return {"message": "鉴定记录已删除"}
