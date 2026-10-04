"""Məkanlar: əsas məktəb və fərdi (repetitor) məkan – siyahı, yaratma, aktiv məkanı dəyişmə, fərdi məkanın adı və zəngləri."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import staff
from ..models import School, User
from ..workspaces import ensure_private, main_school_id, private_of, workspaces
from .common import audit, settings_unlocked

router = APIRouter(prefix='/api/workspaces', tags=['workspaces'])


@router.get('')
def list_ws(user: User = Depends(staff), db: Session = Depends(get_db)):
    return workspaces(db, user)


@router.post('/private')
def create_private(user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    """Fərdi məkan (yoxdursa) – məktəbə aid deyil, yalnız sizə görünür."""
    s = ensure_private(db, user)
    audit(db, user, 'create', 'workspace', s.id)
    db.commit()
    return workspaces(db, user)


class ActiveIn(BaseModel):
    school_id: int


@router.put('/active')
def set_active(body: ActiveIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Aktiv məkan: yalnız öz əsas məktəbiniz və ya öz fərdi məkanınız (başqasınınkı – 404)."""
    main = main_school_id(user)
    p = private_of(db, user)
    if body.school_id == main:
        user.active_school_id = None
    elif p and body.school_id == p.id:
        user.active_school_id = p.id
    else:
        raise HTTPException(404, 'Məkan tapılmadı')
    db.commit()
    return {'ok': True}


class PrivateIn(BaseModel):
    name: str = Field(min_length=3, max_length=300)
    bells: dict[str, str] | None = None


@router.patch('/private')
def update_private(body: PrivateIn, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    s = private_of(db, user)
    if not s:
        raise HTTPException(404, 'Fərdi məkan yoxdur')
    s.name = body.name.strip()
    if body.bells is not None:
        s.bells = {k: v for k, v in body.bells.items() if v}
    audit(db, user, 'update', 'workspace', s.id)
    db.commit()
    return workspaces(db, user)


def is_private(db: Session, user: User) -> bool:
    s = db.get(School, user.school_id) if user.school_id else None
    return bool(s and s.kind == 'private')
