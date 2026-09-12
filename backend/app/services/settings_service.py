import json

from sqlalchemy.orm import Session

from backend.app.models.models import SystemSetting


DEFAULT_SYSTEM_NAME = "课题组小鼠管理系统"
SYSTEM_NAME_KEY = "system_name"
# 兼容升级前已经保存的课题组名称。
GROUP_NAME_KEY = "group_name"
DEFAULT_TRANSFER_ROOMS = ["东五", "东四"]
TRANSFER_ROOMS_KEY = "transfer_rooms"


def _normalize_transfer_rooms(values) -> list[str]:
    rooms = []
    for value in values if isinstance(values, list) else []:
        name = str(value or "").strip()
        if name and len(name) <= 64 and name not in rooms:
            rooms.append(name)
    return rooms


def get_transfer_rooms(db: Session) -> list[str]:
    setting = db.query(SystemSetting).filter(SystemSetting.key == TRANSFER_ROOMS_KEY).first()
    if not setting:
        return DEFAULT_TRANSFER_ROOMS.copy()
    try:
        rooms = _normalize_transfer_rooms(json.loads(setting.value))
    except (TypeError, ValueError):
        rooms = []
    return rooms or DEFAULT_TRANSFER_ROOMS.copy()


def set_transfer_rooms(db: Session, rooms: list[str]) -> list[str]:
    normalized = _normalize_transfer_rooms(rooms)
    if not normalized:
        raise ValueError("至少保留一个转入鼠房选项")
    value = json.dumps(normalized, ensure_ascii=False)
    setting = db.query(SystemSetting).filter(SystemSetting.key == TRANSFER_ROOMS_KEY).first()
    if setting:
        setting.value = value
    else:
        db.add(SystemSetting(key=TRANSFER_ROOMS_KEY, value=value))
    db.commit()
    return normalized


def get_system_name(db: Session) -> str:
    setting = db.query(SystemSetting).filter(SystemSetting.key == SYSTEM_NAME_KEY).first()
    if setting and setting.value.strip():
        return setting.value.strip()

    legacy_setting = db.query(SystemSetting).filter(SystemSetting.key == GROUP_NAME_KEY).first()
    if legacy_setting and legacy_setting.value.strip():
        return f"{legacy_setting.value.strip()}小鼠管理系统"
    return DEFAULT_SYSTEM_NAME


def get_public_settings(db: Session) -> dict:
    return {
        "system_name": get_system_name(db),
        "transfer_rooms": get_transfer_rooms(db),
    }


def set_system_name(db: Session, system_name: str) -> dict:
    clean_name = system_name.strip()
    setting = db.query(SystemSetting).filter(SystemSetting.key == SYSTEM_NAME_KEY).first()
    if setting:
        setting.value = clean_name
    else:
        db.add(SystemSetting(key=SYSTEM_NAME_KEY, value=clean_name))
    db.commit()
    return get_public_settings(db)
