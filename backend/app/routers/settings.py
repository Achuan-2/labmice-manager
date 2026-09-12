from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from backend.app.auth import require_admin, require_auth
from backend.app.auth_database import get_auth_db
from backend.app.models.models import User
from backend.app.services.settings_service import (
    get_public_settings, get_transfer_rooms, set_system_name, set_transfer_rooms,
)


router = APIRouter(prefix="/api/settings", tags=["Settings"])


class SettingsUpdate(BaseModel):
    system_name: Annotated[str, Field(min_length=1, max_length=64)]

    @field_validator("system_name")
    @classmethod
    def validate_system_name(cls, value: str) -> str:
        clean_value = value.strip()
        if not clean_value:
            raise ValueError("系统名称不能为空")
        return clean_value


class TransferRoomUpdate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=64)]

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        clean_value = value.strip()
        if not clean_value:
            raise ValueError("鼠房名称不能为空")
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
    return set_system_name(db, data.system_name)


@router.post("/transfer-rooms")
def add_transfer_room(
    data: TransferRoomUpdate,
    db: Session = Depends(get_auth_db),
    current_user: User = Depends(require_auth),
):
    rooms = get_transfer_rooms(db)
    if data.name not in rooms:
        rooms.append(data.name)
        rooms = set_transfer_rooms(db, rooms)
    return {"transfer_rooms": rooms}


@router.put("/transfer-rooms/{room_name:path}")
def rename_transfer_room(
    room_name: str,
    data: TransferRoomUpdate,
    db: Session = Depends(get_auth_db),
    current_user: User = Depends(require_admin),
):
    old_name = room_name.strip()
    rooms = get_transfer_rooms(db)
    if old_name not in rooms:
        raise HTTPException(status_code=404, detail="转入鼠房选项未找到")
    if data.name != old_name and data.name in rooms:
        raise HTTPException(status_code=409, detail="该转入鼠房选项已存在")
    rooms[rooms.index(old_name)] = data.name
    return {"transfer_rooms": set_transfer_rooms(db, rooms)}


@router.delete("/transfer-rooms/{room_name:path}")
def delete_transfer_room(
    room_name: str,
    db: Session = Depends(get_auth_db),
    current_user: User = Depends(require_admin),
):
    name = room_name.strip()
    rooms = get_transfer_rooms(db)
    if name not in rooms:
        raise HTTPException(status_code=404, detail="转入鼠房选项未找到")
    if len(rooms) == 1:
        raise HTTPException(status_code=400, detail="至少保留一个转入鼠房选项")
    rooms.remove(name)
    return {"transfer_rooms": set_transfer_rooms(db, rooms)}
