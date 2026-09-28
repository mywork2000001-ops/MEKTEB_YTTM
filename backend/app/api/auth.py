"""Giriş / çıxış. Müəllim: login + parol; şagird: portal kodu (XE-001) + 4 rəqəmli PIN."""
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import current_user
from ..models import AuditLog, Role, User
from ..security import (LOCK_MINUTES, MAX_FAILED, SESSION_COOKIE, SESSION_MAX_AGE, hash_password, is_locked,
                        make_session, verify_password)

router = APIRouter(prefix='/api/auth', tags=['auth'])


class LoginIn(BaseModel):
    login: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class MeOut(BaseModel):
    weak_password: bool = False
    id: int
    role: Role
    login: str
    full_name: str
    school_id: int | None
    language: str
    theme: str | None


def _me(u: User) -> MeOut:
    return MeOut(id=u.id, role=u.role, login=u.login, full_name=u.full_name, school_id=u.school_id,
                 language=u.language, theme=u.theme)


def _set_cookie(response: Response, u: User):
    response.set_cookie(SESSION_COOKIE, make_session(u.id, u.password_hash), max_age=SESSION_MAX_AGE,
                        httponly=True, samesite='lax', secure=settings().cookie_secure)


@router.post('/login', response_model=MeOut)
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(func.lower(User.login) == body.login.strip().lower(), User.archived_at.is_(None)))
    if u and is_locked(u.locked_until):
        raise HTTPException(429, f'Çox səhv cəhd. {LOCK_MINUTES} dəqiqədən sonra yenidən yoxlayın')
    if not u or not verify_password(u.password_hash, body.password):
        if u:
            u.failed_logins += 1
            if u.failed_logins >= MAX_FAILED:
                u.locked_until = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=LOCK_MINUTES)
                u.failed_logins = 0
            db.commit()
        raise HTTPException(401, 'Login və ya parol səhvdir')
    u.failed_logins, u.locked_until = 0, None
    db.add(AuditLog(user_id=u.id, action='login', entity='user', entity_id=str(u.id)))
    db.commit()
    _set_cookie(response, u)
    out = _me(u)
    out.weak_password = u.role != Role.student and len(body.password) < 8   # müəllim/admin üçün xəbərdarlıq
    return out


@router.post('/logout')
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE)
    return {'ok': True}


@router.get('/me', response_model=MeOut)
def me(user: User = Depends(current_user)):
    return _me(user)


class PasswordIn(BaseModel):
    old: str
    new: str = Field(min_length=4, max_length=128)


@router.post('/password')
def change_password(body: PasswordIn, response: Response, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    """Şagird PIN-i (4 rəqəm), müəllim parolu (ən azı 8 simvol) dəyişir."""
    if not verify_password(user.password_hash, body.old):
        raise HTTPException(400, 'Köhnə parol səhvdir')
    if user.role == Role.student and not (body.new.isdigit() and len(body.new) == 4):
        raise HTTPException(400, 'PIN 4 rəqəmdən ibarət olmalıdır')
    if user.role != Role.student and len(body.new) < 8:
        raise HTTPException(400, 'Parol ən azı 8 simvol olmalıdır')
    user.password_hash = hash_password(body.new)
    db.add(AuditLog(user_id=user.id, action='update', entity='password', entity_id=str(user.id)))
    db.commit()
    _set_cookie(response, user)
    return {'ok': True}


class PrefsIn(BaseModel):
    language: str | None = Field(None, pattern='^(az|en|ru)$')
    theme: str | None = Field(None, max_length=20)


@router.patch('/prefs', response_model=MeOut)
def prefs(body: PrefsIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Dil (AZ/EN/RU) və rəng çaları – hər istifadəçi özü üçün (şagird də)."""
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(user, k, v)
    db.commit()
    return _me(user)
