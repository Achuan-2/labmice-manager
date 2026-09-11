from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from backend.app.auth import require_admin
from backend.app.auth_database import get_auth_db
from backend.app.models.models import User
from backend.app.services.settings_service import get_public_settings, set_group_name


router = APIRouter(prefix="/api/settings", tags=["Settings"])


class SettingsUpdate(BaseModel):
    group_name: Annotated[str, Field(min_length=1, max_length=64)]

    @field_validator("group_name")
    @classmethod
    def validate_group_name(cls, value: str) -> str:
        clean_value = value.strip()
        if not clean_value:
            raise ValueError("课题组名称不能为空")
        return clean_value


@router.get("/public")
def read_public_settings(db: Session = Depends(get_auth_db)):
    return get_public_settings(db)


@router.put("")
def update_settings(
    data: SettingsUpdate,
    db: Session = Depends(get_auth_db),
    current_user: User = Depends(require_admin),
):
    return set_group_name(db, data.group_name)
