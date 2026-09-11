from sqlalchemy.orm import Session

from backend.app.models.models import Claimer, Mouse
from backend.app.services.mouse_status_service import apply_mouse_status


EUTHANASIA_OWNER_NAME = "安乐死"
EUTHANASIA_OWNER_COLOR = "#6b7280"


def is_euthanasia_owner(name) -> bool:
    return str(name or "").strip() == EUTHANASIA_OWNER_NAME


def ensure_euthanasia_owner(db: Session) -> Claimer:
    owner = db.query(Claimer).filter(Claimer.name == EUTHANASIA_OWNER_NAME).first()
    if owner is None:
        owner = Claimer(
            name=EUTHANASIA_OWNER_NAME,
            role="其他",
            color=EUTHANASIA_OWNER_COLOR,
            notes="系统默认领取人；选择后小鼠状态自动变为死亡",
        )
        db.add(owner)
        db.flush()
    return owner


def apply_owner_status(db: Session, mouse: Mouse) -> bool:
    if not is_euthanasia_owner(mouse.owner_name):
        return False
    owner = ensure_euthanasia_owner(db)
    mouse.owner_id = owner.id
    mouse.owner_name = owner.name
    apply_mouse_status(db, mouse, "死亡")
    return True


def sync_euthanasia_owner(db: Session) -> Claimer:
    owner = ensure_euthanasia_owner(db)
    mice = db.query(Mouse).filter(
        (Mouse.owner_id == owner.id) | (Mouse.owner_name == EUTHANASIA_OWNER_NAME)
    ).all()
    for mouse in mice:
        mouse.owner_id = owner.id
        mouse.owner_name = owner.name
        apply_mouse_status(db, mouse, "死亡")
    return owner
