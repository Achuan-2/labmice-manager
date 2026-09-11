from sqlalchemy.orm import Session

from backend.app.models.models import SystemSetting


DEFAULT_GROUP_NAME = "课题组"
GROUP_NAME_KEY = "group_name"


def get_group_name(db: Session) -> str:
    setting = db.query(SystemSetting).filter(SystemSetting.key == GROUP_NAME_KEY).first()
    return setting.value if setting and setting.value.strip() else DEFAULT_GROUP_NAME


def get_public_settings(db: Session) -> dict:
    group_name = get_group_name(db)
    return {
        "group_name": group_name,
        "system_name": f"{group_name}小鼠管理系统",
    }


def set_group_name(db: Session, group_name: str) -> dict:
    clean_name = group_name.strip()
    setting = db.query(SystemSetting).filter(SystemSetting.key == GROUP_NAME_KEY).first()
    if setting:
        setting.value = clean_name
    else:
        db.add(SystemSetting(key=GROUP_NAME_KEY, value=clean_name))
    db.commit()
    return get_public_settings(db)
