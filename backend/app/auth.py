import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from backend.app.auth_database import get_auth_db
from backend.app.models.models import User

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "mouse-secret-key-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(token: Optional[str] = Depends(oauth2_scheme), db: Session = Depends(get_auth_db)) -> Optional[User]:
    """Returns User if token is valid, otherwise None"""
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
    except JWTError:
        return None
    
    user = db.query(User).filter(User.username == username, User.is_active == True).first()
    return user

def require_auth(user: Optional[User] = Depends(get_current_user)) -> User:
    """Dependency that enforces authentication for all data viewing (guest or admin)"""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="系统数据受保护，请先登录账号后再查看",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

def require_admin(user: User = Depends(require_auth)) -> User:
    """Dependency that enforces admin role"""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，仅管理员可执行该修改/管理操作",
        )
    return user

def init_default_admin(db: Session):
    """Seed the initial administrator if it does not exist."""
    existing_admin = db.query(User).filter(User.username == "admin").first()
    if not existing_admin:
        default_admin = User(
            username="admin",
            hashed_password=get_password_hash(os.getenv("ADMIN_PASSWORD", "admin123")),
            role="admin",
            display_name="系统管理员",
            is_active=True
        )
        db.add(default_admin)

    db.commit()
