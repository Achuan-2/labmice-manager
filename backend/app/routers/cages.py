import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func

from backend.app.database import get_db
from backend.app.models.models import Cage, Mouse, User, Room
from backend.app.schemas.schemas import CageCreate, CageUpdate, CageResponse, CageDetailResponse, RoomCreate
from backend.app.routers.mice import enrich_mouse_response
from backend.app.auth import require_auth, require_admin

router = APIRouter(prefix="/api/cages", tags=["Cages"])

ROOM_CATEGORIES = ("繁育鼠房", "临时鼠房", "实验鼠房")


def normalize_litter_birth_dates(values=None, legacy=None):
    candidates = values if isinstance(values, list) else ([legacy] if legacy else [])
    normalized = []
    for value in candidates:
        value = str(value or "").strip()
        if not value:
            continue
        try:
            datetime.date.fromisoformat(value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="生鼠日期格式无效") from exc
        if value not in normalized:
            normalized.append(value)
    return sorted(normalized, reverse=True)


def normalize_room_category(category: Optional[str]) -> Optional[str]:
    """Keep old room records compatible with the renamed category."""
    return "实验鼠房" if category == "使用鼠房" else category


def default_room_category(name: str) -> str:
    if "实验动物楼" in name or "江湾发育所" in name:
        return "繁育鼠房"
    if "东四" in name:
        return "临时鼠房"
    return "实验鼠房"


@router.get("/rooms")
def list_rooms(
    include_categories: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    cage_rooms = db.query(Cage.room).distinct().all()
    room_table = db.query(Room.name).distinct().all()
    all_rooms = set([r[0] for r in cage_rooms if r[0]]) | \
                set([r[0] for r in room_table if r[0]])

    rooms = sorted(list(all_rooms))
    if include_categories:
        categories = {room.name: normalize_room_category(room.category) for room in db.query(Room).all()}
        cage_counts = dict(db.query(Cage.room, func.count(Cage.id)).group_by(Cage.room).all())
        mouse_counts = dict(db.query(Cage.room, func.count(Mouse.id)).join(Mouse, Mouse.cage_id == Cage.id).group_by(Cage.room).all())
        return [{"name": name, "category": categories.get(name) or default_room_category(name),
                 "cage_count": cage_counts.get(name, 0), "mouse_count": mouse_counts.get(name, 0)} for name in rooms]
    return rooms


@router.delete("/rooms/{room_name:path}")
def delete_room(
    room_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    room = db.query(Room).filter(Room.name == room_name).first()
    cages = db.query(Cage).filter(Cage.room == room_name)
    if not room and not cages.count():
        raise HTTPException(status_code=404, detail="鼠房未找到")
    mouse_count = db.query(Mouse).join(Cage, Mouse.cage_id == Cage.id).filter(Cage.room == room_name).count()
    if mouse_count:
        raise HTTPException(status_code=400, detail=f"该鼠房还有 {mouse_count} 只小鼠，请先将全部小鼠转移后再删除")
    # Only empty cages may be deleted, including if occupancy changed since the check.
    cages.filter(~Cage.mice.any()).delete(synchronize_session=False)
    if cages.count():
        db.rollback()
        raise HTTPException(status_code=400, detail="鼠房内仍有小鼠，请先将全部小鼠转移后再删除")
    if room:
        db.delete(room)
    db.commit()
    return {"message": "鼠房及空笼位已删除"}

@router.post("/rooms")
def create_room(
    data: RoomCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="鼠房名称不能为空")
    category = normalize_room_category(data.category) or default_room_category(name)
    if category not in ROOM_CATEGORIES:
        raise HTTPException(status_code=400, detail="请选择有效的鼠房分类")
    
    existing = db.query(Room).filter(Room.name == name).first()
    if not existing:
        r = Room(name=name, description=data.description, category=category)
        db.add(r)
        db.commit()
    elif data.category:
        existing.category = category
        db.commit()
    
    return {"success": True, "name": name, "message": f"成功添加鼠房 [{name}]"}

@router.get("")
def list_cages(
    room: Optional[str] = None,
    cage_code: Optional[str] = None,
    strain: Optional[str] = None,
    gender: Optional[str] = None,
    only_with_mice: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    query = db.query(Cage)
    if room:
        query = query.filter(Cage.room == room)
    if cage_code:
        query = query.filter(Cage.cage_code.ilike(f"%{cage_code.strip()}%"))
    if strain:
        query = query.filter(Cage.strain == strain)
    if gender:
        query = query.filter(Cage.gender == gender)

    cages = (
        query.options(
            selectinload(Cage.mice).joinedload(Mouse.cage),
            selectinload(Cage.mice).selectinload(Mouse.genotype_records)
        )
        .order_by(Cage.room.asc(), Cage.cage_code.asc())
        .all()
    )

    result = []
    for c in cages:
        mice_in_cage = [enrich_mouse_response(m) for m in c.mice]
        litter_birth_dates = normalize_litter_birth_dates(c.litter_birth_dates, c.litter_birth_date)
        if only_with_mice and len(mice_in_cage) == 0:
            continue
        result.append({
            "id": c.id,
            "cage_code": c.cage_code,
            "room": c.room,
            "strain": c.strain,
            "gender": c.gender,
            "capacity": c.capacity,
            "mating_date": c.mating_date,
            "litter_birth_date": c.litter_birth_date,
            "litter_birth_dates": litter_birth_dates,
            "observation": c.observation,
            "notes": c.notes,
            "mouse_count": len(mice_in_cage),
            "mice": mice_in_cage,
            "created_at": c.created_at,
            "updated_at": c.updated_at
        })

    return result

@router.get("/{cage_id}")
def get_cage(
    cage_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    cage = (
        db.query(Cage)
        .options(
            selectinload(Cage.mice).joinedload(Mouse.cage),
            selectinload(Cage.mice).selectinload(Mouse.genotype_records)
        )
        .filter(Cage.id == cage_id)
        .first()
    )
    if not cage:
        raise HTTPException(status_code=404, detail="笼位未找到")

    mice_in_cage = [enrich_mouse_response(m) for m in cage.mice]
    litter_birth_dates = normalize_litter_birth_dates(cage.litter_birth_dates, cage.litter_birth_date)
    return {
        "id": cage.id,
        "cage_code": cage.cage_code,
        "room": cage.room,
        "strain": cage.strain,
        "gender": cage.gender,
        "capacity": cage.capacity,
        "mating_date": cage.mating_date,
        "litter_birth_date": cage.litter_birth_date,
        "litter_birth_dates": litter_birth_dates,
        "observation": cage.observation,
        "notes": cage.notes,
        "mouse_count": len(mice_in_cage),
        "mice": mice_in_cage,
        "created_at": cage.created_at,
        "updated_at": cage.updated_at
    }

@router.post("")
def create_cage(data: CageCreate, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    clean_code = data.cage_code.strip()
    clean_room = data.room.strip() if data.room else "默认鼠房"
    existing = db.query(Cage).filter(Cage.cage_code == clean_code, Cage.room == clean_room).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"鼠房 [{clean_room}] 中已存在笼位 [{clean_code}]")

    litter_birth_dates = normalize_litter_birth_dates(data.litter_birth_dates, data.litter_birth_date)
    cage = Cage(
        cage_code=clean_code,
        room=clean_room,
        strain=data.strain or "",
        gender=data.gender or "M",
        capacity=data.capacity or 5,
        mating_date=data.mating_date,
        litter_birth_date=litter_birth_dates[0] if litter_birth_dates else None,
        litter_birth_dates=litter_birth_dates,
        observation=data.observation,
        notes=data.notes
    )
    db.add(cage)
    db.commit()
    db.refresh(cage)
    return CageResponse.model_validate(cage)

@router.put("/{cage_id}")
def update_cage(cage_id: int, data: CageUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    cage = db.query(Cage).filter(Cage.id == cage_id).first()
    if not cage:
        raise HTTPException(status_code=404, detail="笼位未找到")

    update_dict = data.model_dump(exclude_unset=True, exclude={"merge_existing"})
    if "litter_birth_dates" in update_dict:
        litter_birth_dates = normalize_litter_birth_dates(update_dict["litter_birth_dates"])
        removed_dates = set(normalize_litter_birth_dates(cage.litter_birth_dates, cage.litter_birth_date)) - set(litter_birth_dates)
        if removed_dates and db.query(Mouse).filter(Mouse.cage_id == cage.id, Mouse.dob.in_(removed_dates)).count():
            raise HTTPException(status_code=400, detail="生鼠批次已绑定在笼小鼠，请先修改小鼠出生日期或移出本笼")
        update_dict["litter_birth_dates"] = litter_birth_dates
        update_dict["litter_birth_date"] = litter_birth_dates[0] if litter_birth_dates else None
    elif "litter_birth_date" in update_dict:
        litter_birth_dates = normalize_litter_birth_dates(None, update_dict["litter_birth_date"])
        removed_dates = set(normalize_litter_birth_dates(cage.litter_birth_dates, cage.litter_birth_date)) - set(litter_birth_dates)
        if removed_dates and db.query(Mouse).filter(Mouse.cage_id == cage.id, Mouse.dob.in_(removed_dates)).count():
            raise HTTPException(status_code=400, detail="生鼠批次已绑定在笼小鼠，请先修改小鼠出生日期或移出本笼")
        update_dict["litter_birth_dates"] = litter_birth_dates
        update_dict["litter_birth_date"] = litter_birth_dates[0] if litter_birth_dates else None
    clean_code = str(update_dict.get("cage_code", cage.cage_code) or "").strip()
    clean_room = str(update_dict.get("room", cage.room) or "默认鼠房").strip()
    if not clean_code:
        raise HTTPException(status_code=400, detail="笼位号不能为空")
    update_dict["cage_code"] = clean_code
    update_dict["room"] = clean_room

    existing = db.query(Cage).filter(
        Cage.cage_code == clean_code,
        Cage.room == clean_room,
        Cage.id != cage.id,
    ).first()
    if existing:
        existing_mouse_count = db.query(Mouse).filter(Mouse.cage_id == existing.id).count()
        if existing_mouse_count > 0 and not data.merge_existing:
            raise HTTPException(
                status_code=409,
                detail=f"目标笼位 [{clean_room} · {clean_code}] 已有 {existing_mouse_count} 只小鼠。确认合并后，两笼小鼠将进入目标笼位，原笼位 [{cage.room} · {cage.cage_code}] 将保留为空笼。",
            )
        db.query(Mouse).filter(Mouse.cage_id == cage.id).update(
            {"cage_id": existing.id}, synchronize_session=False
        )
        for key, value in update_dict.items():
            setattr(existing, key, value)
        db.commit()
        db.refresh(existing)
        return CageResponse.model_validate(existing)

    for k, v in update_dict.items():
        setattr(cage, k, v)

    db.commit()
    db.refresh(cage)
    return CageResponse.model_validate(cage)

@router.delete("/{cage_id}")
def delete_cage(cage_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    cage = db.query(Cage).filter(Cage.id == cage_id).first()
    if not cage:
        raise HTTPException(status_code=404, detail="笼位未找到")

    for m in cage.mice:
        m.cage_id = None
    db.flush()

    db.delete(cage)
    db.commit()
    return {"message": "笼位删除成功"}
