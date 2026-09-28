"""FastAPI asılılıqları: cari istifadəçi və rol yoxlaması."""
from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .db import get_db
from .models import Role, User
from .security import SESSION_COOKIE, read_session


def current_user(db: Session = Depends(get_db), token: str | None = Cookie(None, alias=SESSION_COOKIE)) -> User:
    data = read_session(token)
    user = db.get(User, data['u']) if data else None
    if not user or user.archived_at or user.password_hash[-12:] != data.get('p'):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Daxil olun')
    return user


def require(*roles: Role):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, 'Bu bölmə sizin üçün deyil')
        return user
    return dep


admin_only = require(Role.admin)
staff = require(Role.admin, Role.teacher)
