import datetime
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import case, func, or_

from backend.app.database import get_db
from backend.app.models.models import GenotypeRecord, Mouse, User
from backend.app.schemas.schemas import (
    GenotypeRecordCreate, GenotypeRecordUpdate, GenotypeRecordResponse
)
from backend.app.auth import require_auth, require_admin
from backend.app.services.genotype_service import sync_mouse_genotype_summary as _sync_mouse_genotype_summary

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
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    query = db.query(GenotypeRecord)
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

    # Order so tested records with valid test_date and parents appear first
    order_date = case((or_(GenotypeRecord.test_date.is_(None), GenotypeRecord.test_date == ""), 1), else_=0)
    order_clauses.extend([order_date, GenotypeRecord.test_date.desc(), GenotypeRecord.id.desc()])
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

@router.post("", response_model=GenotypeRecordResponse)
def create_genotype_record(
    data: GenotypeRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    gt = _add_genotype_record(data, db, current_user)
    db.commit()
    db.refresh(gt)
    return gt


def _add_genotype_record(data, db, current_user):
    clean_code = data.mouse_code.strip()
    if not clean_code or any(separator in clean_code for separator in (",", "，", "、", "\n")):
        raise HTTPException(status_code=422, detail="每条鉴定记录需提供一个有效耳标编号")
    mouse = db.query(Mouse).filter(Mouse.mouse_code == clean_code).first()
    
    gt = GenotypeRecord(
        mouse_code=clean_code,
        mouse_id=mouse.id if mouse else None,
        test_date=data.test_date or datetime.date.today().strftime("%Y-%m-%d"),
        strain=data.strain or (mouse.strain if mouse else ""),
        dob=data.dob or (mouse.dob if mouse else None),
        gender=data.gender or (mouse.gender if mouse else None),
        parents=data.parents or (mouse.parents if mouse else None),
        genotype_1=data.genotype_1,
        genotype_2=data.genotype_2,
        genotype_3=data.genotype_3,
        op_record=data.op_record or current_user.display_name or current_user.username,
        notes=data.notes
    )
    db.add(gt)

    # Sync to mouse record
    if mouse:
        if data.dob:
            mouse.dob = data.dob
        if data.gender and mouse.gender == "未知":
            mouse.gender = data.gender
        db.flush()
        _sync_mouse_genotype_summary(mouse, db)

    return gt


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
        records = [_add_genotype_record(item, db, current_user) for item in data]
        db.commit()
    except Exception:
        db.rollback()
        raise
    for record in records:
        db.refresh(record)
    return records

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

    update_dict = data.model_dump(exclude_unset=True)
    for k, v in update_dict.items():
        setattr(gt, k, v)

    db.flush()
    mouse = gt.mouse or db.query(Mouse).filter(Mouse.mouse_code == gt.mouse_code).first()
    if mouse and "dob" in update_dict:
        mouse.dob = update_dict["dob"] or None
    _sync_mouse_genotype_summary(mouse, db)
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
    mouse = gt.mouse or db.query(Mouse).filter(Mouse.mouse_code == gt.mouse_code).first()
    db.delete(gt)
    db.flush()
    _sync_mouse_genotype_summary(mouse, db)
    db.commit()
    return {"message": "鉴定记录已删除"}
