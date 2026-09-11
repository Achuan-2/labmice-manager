import random
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.models import Claimer, Mouse, User
from backend.app.schemas.schemas import ClaimerCreate, ClaimerUpdate, ClaimerResponse
from backend.app.routers.mice import enrich_mouse_response
from backend.app.auth import require_auth, require_admin
from backend.app.services.owner_service import EUTHANASIA_OWNER_NAME, apply_owner_status

router = APIRouter(tags=["Members"])

PRESET_COLORS = [
    "#2563eb",  # 宝石蓝
    "#059669",  # 翠绿
    "#d97706",  # 琥珀橙
    "#7c3aed",  # 罗兰紫
    "#db2777",  # 玫红
    "#0891b2",  # 青绿
    "#ea580c",  # 烈焰橙
    "#4f46e5",  # 靛青
    "#16a34a",  # 鲜绿
    "#c026d3",  # 兰花紫
    "#e11d48",  # 胭脂红
    "#0d9488",  # 蓝绿
    "#6366f1",  # 丁香紫
    "#b45309",  # 棕黄
    "#0284c7",  # 天蓝
    "#be185d",  # 樱桃红
]

def normalize_role(role: Optional[str]) -> str:
    if not role:
        return "学生"
    role = role.strip()
    if role == "实验管家":
        return "管家"
    return role

def pick_random_color(db: Session) -> str:
    used_colors = set(c[0] for c in db.query(Claimer.color).all() if c[0])
    unused = [c for c in PRESET_COLORS if c not in used_colors]
    if unused:
        return random.choice(unused)
    return random.choice(PRESET_COLORS)

@router.get("")
def list_claimers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    claimers = db.query(Claimer).order_by(
        case((Claimer.name == EUTHANASIA_OWNER_NAME, 1), else_=0),
        Claimer.name.asc(),
    ).all()
    results = []
    for c in claimers:
        mice_count = db.query(Mouse).filter(Mouse.owner_id == c.id).count()
        results.append({
            "id": c.id,
            "name": c.name,
            "role": normalize_role(c.role),
            "email": c.email,
            "phone": c.phone,
            "color": c.color or "#2563eb",
            "default_room": c.default_room,
            "notes": c.notes,
            "mouse_count": mice_count,
            "created_at": c.created_at
        })
    return results

@router.get("/{claimer_id}/mice")
def get_claimer_mice(
    claimer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    claimer = db.query(Claimer).filter(Claimer.id == claimer_id).first()
    if not claimer:
        raise HTTPException(status_code=404, detail="成员未找到")

    mice = db.query(Mouse).filter(Mouse.owner_id == claimer_id).all()
    return {
        "claimer": {
            "id": claimer.id,
            "name": claimer.name,
            "role": normalize_role(claimer.role),
            "color": claimer.color or "#2563eb",
            "mouse_count": len(mice)
        },
        "items": [enrich_mouse_response(m) for m in mice]
    }

@router.post("")
def create_claimer(data: ClaimerCreate, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    clean_name = data.name.strip()
    existing = db.query(Claimer).filter(Claimer.name == clean_name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"成员 [{clean_name}] 已存在")

    chosen_color = data.color.strip() if (data.color and data.color.strip()) else pick_random_color(db)

    claimer = Claimer(
        name=clean_name,
        role=normalize_role(data.role),
        email=data.email,
        phone=data.phone,
        color=chosen_color,
        default_room=data.default_room,
        notes=data.notes
    )
    db.add(claimer)
    db.commit()
    db.refresh(claimer)
    return claimer

@router.put("/{claimer_id}")
def update_claimer(
    claimer_id: int,
    data: ClaimerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    claimer = db.query(Claimer).filter(Claimer.id == claimer_id).first()
    if not claimer:
        raise HTTPException(status_code=404, detail="成员未找到")

    update_dict = data.model_dump(exclude_unset=True)
    if "role" in update_dict:
        update_dict["role"] = normalize_role(update_dict["role"])

    if current_user.role != "admin":
        if "name" in update_dict and update_dict["name"] != claimer.name:
            raise HTTPException(status_code=403, detail="普通成员不可修改姓名，如需更名请联系管理员")
        if "role" in update_dict and update_dict["role"] != claimer.role:
            raise HTTPException(status_code=403, detail="普通成员不可修改身份角色，如需调整请联系管理员")
    else:
        if "name" in update_dict:
            new_name = update_dict["name"].strip()
            if claimer.name == EUTHANASIA_OWNER_NAME and new_name != EUTHANASIA_OWNER_NAME:
                raise HTTPException(status_code=400, detail="系统默认领取人“安乐死”不可改名")
            db.query(Mouse).filter(Mouse.owner_id == claimer_id).update({"owner_name": new_name})
            claimer.name = new_name
            if new_name == EUTHANASIA_OWNER_NAME:
                for mouse in db.query(Mouse).filter(Mouse.owner_id == claimer_id).all():
                    apply_owner_status(db, mouse)

    for k, v in update_dict.items():
        if k != "name":
            setattr(claimer, k, v)

    db.commit()
    db.refresh(claimer)
    return claimer

@router.delete("/{claimer_id}")
def delete_claimer(claimer_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    claimer = db.query(Claimer).filter(Claimer.id == claimer_id).first()
    if not claimer:
        raise HTTPException(status_code=404, detail="领取人未找到")
    if claimer.name == EUTHANASIA_OWNER_NAME:
        raise HTTPException(status_code=400, detail="系统默认领取人“安乐死”不可删除")

    db.query(Mouse).filter(Mouse.owner_id == claimer_id).update({
        "owner_id": None,
        "owner_name": None
    })

    db.delete(claimer)
    db.commit()
    return {"message": "领取人删除成功，关联小鼠已置为空闲"}
