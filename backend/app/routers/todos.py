import datetime
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.auth import require_admin, require_auth
from backend.app.database import get_db
from backend.app.models.models import Cage, Mouse, TodoReminder, User
from backend.app.schemas.schemas import TodoReminderCreate, TodoReminderUpdate


router = APIRouter(prefix="/api/todos", tags=["Todo reminders"])
MIXED_GENDERS = {"M/F", "混合"}


def parse_date(value: Optional[str]) -> Optional[datetime.date]:
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def validate_due_at(value: Optional[str]) -> Optional[str]:
    value = str(value or "").strip() or None
    if value:
        try:
            datetime.datetime.fromisoformat(value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="待办时间格式无效") from exc
    return value


def normalize_relation_ids(values, legacy_id=None):
    source = values if values is not None else ([legacy_id] if legacy_id else [])
    result = []
    for value in source:
        try:
            relation_id = int(value)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="关联记录编号无效") from exc
        if relation_id < 1:
            raise HTTPException(status_code=400, detail="关联记录编号无效")
        if relation_id not in result:
            result.append(relation_id)
    return result


def validate_relation_ids(db: Session, model, ids, label):
    if ids and db.query(model.id).filter(model.id.in_(ids)).count() != len(ids):
        raise HTTPException(status_code=400, detail=f"关联{label}不存在")


def sync_automatic_todos(db: Session) -> None:
    today = datetime.date.today()
    active = {}
    mixed_cages = db.query(Cage).filter(Cage.gender.in_(MIXED_GENDERS)).all()

    for cage in mixed_cages:
        birth_dates = cage.litter_birth_dates if isinstance(cage.litter_birth_dates, list) else []
        if not birth_dates and cage.litter_birth_date:
            birth_dates = [cage.litter_birth_date]
        for birth_date_value in birth_dates:
            birth_date = parse_date(birth_date_value)
            if not birth_date:
                continue
            due_date = birth_date + datetime.timedelta(days=21)
            key = f"litter-weaning:{cage.id}:{birth_date.isoformat()}"
            active[key] = {
                "title": f"笼位 {cage.room} · {cage.cage_code}：生鼠满21天，请进行分笼",
                "due_at": due_date.isoformat(),
                "notes": f"生鼠日期：{birth_date.isoformat()}。请检查幼鼠并完成断奶、分笼及档案更新。",
                "cage_id": cage.id,
                "cage_ids": [cage.id],
                "source": "litter_weaning",
            }

    aged_by_cage = defaultdict(list)
    for mouse in db.query(Mouse).join(Cage, Mouse.cage_id == Cage.id).filter(Cage.gender.in_(MIXED_GENDERS)).all():
        dob = parse_date(mouse.dob)
        if dob and (today - dob).days > 280:
            aged_by_cage[mouse.cage_id].append((mouse, (today - dob).days / 7))

    cages_by_id = {cage.id: cage for cage in mixed_cages}
    for cage_id, aged_mice in aged_by_cage.items():
        cage = cages_by_id.get(cage_id)
        if not cage:
            continue
        key = f"mixed-aged:{cage.id}"
        codes = "、".join(mouse.mouse_code for mouse, _ in aged_mice)
        max_weeks = max(weeks for _, weeks in aged_mice)
        active[key] = {
            "title": f"笼位 {cage.room} · {cage.cage_code}：混笼小鼠超过40周",
            "due_at": today.isoformat(),
            "notes": f"超过40周的小鼠：{codes}；最大周龄约 {max_weeks:.1f} 周。请检查并处理该混笼。",
            "cage_id": cage.id,
            "cage_ids": [cage.id],
            "source": "mixed_aged",
        }

    existing = {todo.auto_key: todo for todo in db.query(TodoReminder).filter(TodoReminder.auto_key.isnot(None)).all()}
    for key, values in active.items():
        todo = existing.get(key)
        if not todo:
            db.add(TodoReminder(auto_key=key, status="pending", **values))
        elif todo.status == "pending":
            for field, value in values.items():
                setattr(todo, field, value)

    for key, todo in existing.items():
        if todo.status == "pending" and key not in active:
            todo.status = "completed"
            todo.completed_at = datetime.datetime.utcnow()
    db.commit()


def serialize_todo(todo: TodoReminder, db: Session):
    cage_ids = normalize_relation_ids(todo.cage_ids, todo.cage_id)
    mouse_ids = normalize_relation_ids(todo.mouse_ids, todo.mouse_id)
    cage_map = {cage.id: cage for cage in db.query(Cage).filter(Cage.id.in_(cage_ids)).all()} if cage_ids else {}
    mouse_map = {mouse.id: mouse for mouse in db.query(Mouse).filter(Mouse.id.in_(mouse_ids)).all()} if mouse_ids else {}
    cages = [cage_map[cage_id] for cage_id in cage_ids if cage_id in cage_map]
    mice = [mouse_map[mouse_id] for mouse_id in mouse_ids if mouse_id in mouse_map]
    cage_ids = [cage.id for cage in cages]
    mouse_ids = [mouse.id for mouse in mice]
    cage_views = [{"id": cage.id, "room": cage.room, "cage_code": cage.cage_code} for cage in cages]
    mouse_views = [{"id": mouse.id, "mouse_code": mouse.mouse_code} for mouse in mice]
    return {
        "id": todo.id,
        "title": todo.title,
        "due_at": todo.due_at,
        "notes": todo.notes,
        "cage_id": cage_ids[0] if cage_ids else None,
        "mouse_id": mouse_ids[0] if mouse_ids else None,
        "cage_ids": cage_ids,
        "mouse_ids": mouse_ids,
        "source": todo.source,
        "auto_key": todo.auto_key,
        "status": todo.status,
        "completed_at": todo.completed_at,
        "created_at": todo.created_at,
        "updated_at": todo.updated_at,
        "cage": cage_views[0] if cage_views else None,
        "mouse": mouse_views[0] if mouse_views else None,
        "cages": cage_views,
        "mice": mouse_views,
    }


@router.get("")
def list_todos(
    bucket: str = Query("today", pattern="^(today|future|inbox|all)$"),
    include_completed: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    sync_automatic_todos(db)
    query = db.query(TodoReminder)
    if not include_completed:
        query = query.filter(TodoReminder.status == "pending")
    todos = query.order_by(TodoReminder.due_at.asc().nullslast(), TodoReminder.id.desc()).all()
    today = datetime.date.today().isoformat()
    if bucket == "today":
        todos = [todo for todo in todos if todo.due_at and todo.due_at[:10] <= today]
    elif bucket == "future":
        todos = [todo for todo in todos if todo.due_at and todo.due_at[:10] > today]
    elif bucket == "inbox":
        todos = [todo for todo in todos if not todo.due_at or todo.due_at[:10] > today]
    return [serialize_todo(todo, db) for todo in todos]


@router.post("")
def create_todo(data: TodoReminderCreate, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    title = data.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="请输入待办内容")
    cage_ids = normalize_relation_ids(data.cage_ids, data.cage_id)
    mouse_ids = normalize_relation_ids(data.mouse_ids, data.mouse_id)
    validate_relation_ids(db, Cage, cage_ids, "笼位")
    validate_relation_ids(db, Mouse, mouse_ids, "小鼠")
    todo = TodoReminder(
        title=title,
        due_at=validate_due_at(data.due_at),
        notes=data.notes,
        cage_id=cage_ids[0] if cage_ids else None,
        mouse_id=mouse_ids[0] if mouse_ids else None,
        cage_ids=cage_ids,
        mouse_ids=mouse_ids,
        source="manual",
        status="pending",
    )
    db.add(todo)
    db.commit()
    db.refresh(todo)
    return serialize_todo(todo, db)


@router.put("/{todo_id}")
def update_todo(todo_id: int, data: TodoReminderUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    todo = db.get(TodoReminder, todo_id)
    if not todo:
        raise HTTPException(status_code=404, detail="待办不存在")
    updates = data.model_dump(exclude_unset=True)
    if "title" in updates:
        updates["title"] = str(updates["title"] or "").strip()
        if not updates["title"]:
            raise HTTPException(status_code=400, detail="请输入待办内容")
    if "due_at" in updates:
        updates["due_at"] = validate_due_at(updates["due_at"])
    if "status" in updates:
        if updates["status"] not in {"pending", "completed"}:
            raise HTTPException(status_code=400, detail="待办状态无效")
        todo.completed_at = datetime.datetime.utcnow() if updates["status"] == "completed" else None
    if "cage_ids" in updates or "cage_id" in updates:
        cage_ids = normalize_relation_ids(updates.pop("cage_ids", None), updates.pop("cage_id", None))
        validate_relation_ids(db, Cage, cage_ids, "笼位")
        updates["cage_ids"] = cage_ids
        updates["cage_id"] = cage_ids[0] if cage_ids else None
    if "mouse_ids" in updates or "mouse_id" in updates:
        mouse_ids = normalize_relation_ids(updates.pop("mouse_ids", None), updates.pop("mouse_id", None))
        validate_relation_ids(db, Mouse, mouse_ids, "小鼠")
        updates["mouse_ids"] = mouse_ids
        updates["mouse_id"] = mouse_ids[0] if mouse_ids else None
    for field, value in updates.items():
        setattr(todo, field, value)
    db.commit()
    db.refresh(todo)
    return serialize_todo(todo, db)


@router.delete("/{todo_id}")
def delete_todo(todo_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    todo = db.get(TodoReminder, todo_id)
    if not todo:
        raise HTTPException(status_code=404, detail="待办不存在")
    if todo.auto_key:
        todo.status = "completed"
        todo.completed_at = datetime.datetime.utcnow()
    else:
        db.delete(todo)
    db.commit()
    return {"message": "自动提醒已忽略" if todo.auto_key else "待办已删除"}
