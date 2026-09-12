from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.app.auth_database import get_auth_db
from backend.app.models.models import User
from backend.app.schemas.schemas import (
    Token, UserCreate, UserLogin, UserResponse, UserUpdateDisplayName, UserUpdatePassword,
)
from backend.app.auth import verify_password, get_password_hash, create_access_token, get_current_user, require_admin

from sqlalchemy import func

router = APIRouter(prefix="/api/auth", tags=["Auth"])

@router.post("/login", response_model=Token)
def login(form_data: UserLogin, db: Session = Depends(get_auth_db)):
    clean_username = form_data.username.strip() if form_data.username else ""
    clean_password = form_data.password.strip() if form_data.password else ""

    # Case-insensitive username matching
    user = db.query(User).filter(func.lower(User.username) == clean_username.lower()).first()

    if not user or not verify_password(clean_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该账号已被停用",
        )

    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

@router.get("/me")
def get_me(user: Optional[User] = Depends(get_current_user)):
    if not user:
        return {
            "role": "guest",
            "username": "游客",
            "display_name": "访客模式 (只读)",
            "is_authenticated": False
        }
    return {
        "id": user.id,
        "role": user.role,
        "username": user.username,
        "display_name": user.display_name or user.username,
        "is_authenticated": True
    }

@router.get("/admins", response_model=List[UserResponse])
def list_admins(db: Session = Depends(get_auth_db), current_user: User = Depends(require_admin)):
    return db.query(User).all()

@router.post("/admins", response_model=UserResponse)
def create_admin(data: UserCreate, db: Session = Depends(get_auth_db), current_user: User = Depends(require_admin)):
    username = data.username.strip()
    password = data.password.strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="账号和密码不能为空")
    if data.role not in ("admin", "guest"):
        raise HTTPException(status_code=400, detail="请选择管理员或普通用户角色")
    existing = db.query(User).filter(func.lower(User.username) == username.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="该用户名已存在")
    
    new_user = User(
        username=username,
        hashed_password=get_password_hash(password),
        role=data.role,
        display_name=data.display_name or username,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.put("/admins/{admin_id}/password")
def update_admin_password(admin_id: int, data: UserUpdatePassword, db: Session = Depends(get_auth_db), current_user: User = Depends(require_admin)):
    target_user = db.query(User).filter(User.id == admin_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="用户未找到")
    
    if data.old_password and not verify_password(data.old_password, target_user.hashed_password):
        raise HTTPException(status_code=400, detail="原密码不正确")

    target_user.hashed_password = get_password_hash(data.new_password)
    db.commit()
    return {"message": "密码修改成功"}

@router.put("/admins/{admin_id}/display-name", response_model=UserResponse)
def update_user_display_name(
    admin_id: int,
    data: UserUpdateDisplayName,
    db: Session = Depends(get_auth_db),
    current_user: User = Depends(require_admin),
):
    target_user = db.query(User).filter(User.id == admin_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="用户未找到")

    display_name = data.display_name.strip()
    if not display_name:
        raise HTTPException(status_code=400, detail="用户名称不能为空")
    if len(display_name) > 64:
        raise HTTPException(status_code=400, detail="用户名称不能超过64个字符")

    target_user.display_name = display_name
    db.commit()
    db.refresh(target_user)
    return target_user

@router.delete("/admins/{admin_id}")
def delete_admin(admin_id: int, db: Session = Depends(get_auth_db), current_user: User = Depends(require_admin)):
    target_user = db.query(User).filter(User.id == admin_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="用户未找到")
    if target_user.role == "admin" and db.query(User).filter(User.role == "admin").count() <= 1:
        raise HTTPException(status_code=400, detail="系统必须保留至少一个管理员账号")
    
    if target_user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除当前正在登录的管理员账号")

    db.delete(target_user)
    db.commit()
    return {"message": "删除成功"}
