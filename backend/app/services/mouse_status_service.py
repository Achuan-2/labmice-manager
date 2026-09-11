from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from backend.app.models.models import Mouse, MouseStatus


DEFAULT_MOUSE_STATUSES = [
    {"name": "在笼", "is_system": True, "removes_from_cage": False},
    {"name": "已领用", "is_system": True, "removes_from_cage": False},
    {"name": "繁育中", "is_system": False, "removes_from_cage": False},
    {"name": "实验中", "is_system": False, "removes_from_cage": False},
    {"name": "待鉴定", "is_system": False, "removes_from_cage": False},
    {"name": "出笼", "is_system": True, "removes_from_cage": True},
    {"name": "死亡", "is_system": False, "removes_from_cage": True},
]

DEFAULT_STATUS_SORT_ORDER = {
    "在笼": 0,
    "已领用": 1,
    "繁育中": 2,
    "实验中": 3,
    "待鉴定": 4,
    "出笼": 10000,
    "死亡": 10001,
}

REMOVED_MOUSE_STATUSES = {"淘汰", "档案记录"}


def clean_status_name(name: str) -> str:
    clean_name = (name or "").strip()
    if not clean_name:
        raise ValueError("状态名称不能为空")
    if len(clean_name) > 32:
        raise ValueError("状态名称不能超过 32 个字符")
    if clean_name in REMOVED_MOUSE_STATUSES:
        raise ValueError(f"“{clean_name}”状态已移除，请使用“出笼”或创建其他状态")
    return clean_name


def sync_mouse_statuses(db: Session) -> None:
    """初始化状态字典，并将旧版内部状态统一归并为“出笼”。"""
    db.query(Mouse).filter(Mouse.status.in_(REMOVED_MOUSE_STATUSES)).update(
        {Mouse.status: "出笼"}, synchronize_session=False
    )
    db.query(Mouse).filter(
        Mouse.status == "在笼",
        Mouse.cage_id.isnot(None),
        or_(
            Mouse.owner_id.isnot(None),
            and_(Mouse.owner_name.isnot(None), Mouse.owner_name != ""),
        ),
    ).update(
        {Mouse.status: "已领用"}, synchronize_session=False
    )
    db.query(Mouse).filter(Mouse.status == "已领用", Mouse.cage_id.is_(None)).update(
        {Mouse.status: "出笼"}, synchronize_session=False
    )
    db.query(MouseStatus).filter(MouseStatus.name.in_(REMOVED_MOUSE_STATUSES)).delete(
        synchronize_session=False
    )

    existing = {item.name: item for item in db.query(MouseStatus).all()}
    is_initial_setup = not existing
    for item in DEFAULT_MOUSE_STATUSES:
        status = existing.get(item["name"])
        if status is None:
            if not is_initial_setup and not item["is_system"]:
                continue
            status = MouseStatus(
                name=item["name"],
                is_system=item["is_system"],
                removes_from_cage=item["removes_from_cage"],
                sort_order=DEFAULT_STATUS_SORT_ORDER[item["name"]],
            )
            db.add(status)
            existing[item["name"]] = status
        else:
            status.sort_order = DEFAULT_STATUS_SORT_ORDER[item["name"]]
            if item["is_system"]:
                status.is_system = True
                status.removes_from_cage = item["removes_from_cage"]

    default_names = {item["name"] for item in DEFAULT_MOUSE_STATUSES}
    custom_statuses = sorted(
        (status for status in existing.values() if status.name not in default_names),
        key=lambda status: (status.sort_order, status.id or 0),
    )
    custom_start_order = 5
    for index, status in enumerate(custom_statuses, start=custom_start_order):
        status.sort_order = index

    known_names = set(existing)
    used_names = [
        row[0].strip()
        for row in db.query(Mouse.status).filter(Mouse.status.isnot(None), Mouse.status != "").distinct().all()
        if row[0] and row[0].strip() and row[0].strip() not in REMOVED_MOUSE_STATUSES
    ]
    next_order = custom_start_order + len(custom_statuses)
    for name in sorted(set(used_names) - known_names):
        db.add(MouseStatus(name=name, sort_order=next_order))
        next_order += 1

    db.commit()


def ensure_mouse_status(db: Session, name: str) -> MouseStatus:
    clean_name = clean_status_name(name)
    status = db.query(MouseStatus).filter(MouseStatus.name == clean_name).first()
    if status is None:
        next_order = db.query(MouseStatus).count()
        status = MouseStatus(name=clean_name, sort_order=next_order)
        db.add(status)
        db.flush()
    return status


def apply_mouse_status(db: Session, mouse: Mouse, name: str) -> str:
    status = ensure_mouse_status(db, name)
    if status.name == "已领用" and mouse.cage_id is None:
        status = ensure_mouse_status(db, "出笼")
    mouse.status = status.name
    if status.removes_from_cage:
        mouse.cage_id = None
    return status.name
