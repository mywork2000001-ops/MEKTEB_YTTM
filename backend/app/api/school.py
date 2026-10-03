"""Məktəblər (UTİS), müəllim hesabları, Tənzimləmələr kilidi.
- Məktəbi və UTİS kodunu ADMIN yazır; müəllim məktəbi adına görə tapıb seçir.
- Eyni məktəbə qoşulan müəllimlər ortaq sinif/şagird siyahısını görür (təkrar yaranmır)."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import admin_only, staff
from ..models import Role, School, User
from ..security import hash_password, new_password, verify_password
from .common import ConfirmIn, audit, check_confirm, get_or_404, settings_token, settings_unlocked

router = APIRouter(prefix='/api', tags=['school'])


def school_out(s: School, full: bool = True):
    d = {'id': s.id, 'name': s.name, 'short_name': s.short_name, 'region': s.region}
    if full:
        d.update(utis=s.utis, bells=s.bells, doc_settings=s.doc_settings or {})
    return d


@router.get('/school')
def my_school(user: User = Depends(staff), db: Session = Depends(get_db)):
    if not user.school_id:
        return None
    return school_out(db.get(School, user.school_id))


@router.get('/schools')
def search_schools(q: str = '', user: User = Depends(staff), db: Session = Depends(get_db)):
    """Müəllim məktəbini adına görə tapır (ən azı 2 hərf)."""
    st = select(School).where(School.archived_at.is_(None))
    if user.role != Role.admin:
        if len(q.strip()) < 2:
            return []
        st = st.where(func.lower(School.name).contains(q.strip().lower()))
    elif q:
        st = st.where(func.lower(School.name).contains(q.strip().lower()))
    return [school_out(s, full=user.role == Role.admin) for s in db.scalars(st.order_by(School.name).limit(30))]


class SchoolIn(BaseModel):
    name: str = Field(min_length=3, max_length=300)
    utis: str | None = Field(None, max_length=32)
    short_name: str | None = Field(None, max_length=120)
    region: str | None = Field(None, max_length=120)
    bells: dict[str, str] | None = None
    doc_settings: dict[str, str | None] | None = None      # {'deputy': ad, 'director': ad} – rəsmi sənəd imzaları


def _check_utis(db: Session, utis: str | None, exclude_id: int | None = None):
    if utis:
        if not utis.isdigit():
            raise HTTPException(400, 'UTİS kodu yalnız rəqəmlərdən ibarət olmalıdır')
        other = db.scalar(select(School).where(School.utis == utis))
        if other and other.id != exclude_id:
            raise HTTPException(409, f'Bu UTİS kodu artıq «{other.name}» məktəbinə aiddir')


@router.post('/schools')
def create_school(body: SchoolIn, user: User = Depends(admin_only), db: Session = Depends(get_db),
                  _: User = Depends(settings_unlocked)):
    _check_utis(db, body.utis)
    s = School(**body.model_dump())
    db.add(s)
    db.flush()
    audit(db, user, 'create', 'school', s.id, name=s.name, utis=s.utis)
    db.commit()
    return school_out(s)


@router.patch('/schools/{school_id}')
def update_school(school_id: int, body: SchoolIn, user: User = Depends(admin_only), db: Session = Depends(get_db),
                  _: User = Depends(settings_unlocked)):
    s = get_or_404(db, School, school_id, 'Məktəb')
    _check_utis(db, body.utis, s.id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    audit(db, user, 'update', 'school', s.id, **body.model_dump(exclude_unset=True))
    db.commit()
    return school_out(s)


class JoinSchoolIn(BaseModel):
    school_id: int


@router.post('/me/school')
def join_school(body: JoinSchoolIn, user: User = Depends(staff), db: Session = Depends(get_db),
                _: User = Depends(settings_unlocked)):
    s = get_or_404(db, School, body.school_id, 'Məktəb')
    if s.archived_at:
        raise HTTPException(409, 'Məktəb arxivdədir')
    user.school_id = s.id
    audit(db, user, 'update', 'user_school', user.id, school_id=s.id)
    db.commit()
    return school_out(s, full=user.role == Role.admin)


# ---------------------------------------------------------------- müəllim hesabları (admin)
class TeacherIn(BaseModel):
    login: str | None = Field(None, max_length=64)       # köhnə uyğunluq üçün; ID avtomatik verilir (M-002, …)
    full_name: str = Field(min_length=3, max_length=200)
    subjects: list[str] = Field(default_factory=list)
    school_id: int | None = None


def next_teacher_id(db: Session) -> str:
    """Müəllim ID-si: M-001, M-002, … (giriş bu ID ilə)."""
    nums = [int(x[2:]) for x in db.scalars(select(User.login).where(User.login.like('M-%'))) if x[2:].isdigit()]
    return f'M-{max(nums, default=0) + 1:03d}'


def teacher_out(u: User):
    return {'id': u.id, 'login': u.login, 'full_name': u.full_name, 'subjects': u.subjects or [],
            'school_id': u.school_id, 'role': u.role, 'archived': u.archived_at is not None}


@router.get('/teachers')
def list_teachers(user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return [teacher_out(u) for u in db.scalars(select(User).where(User.role.in_((Role.admin, Role.teacher)))
                                                .order_by(User.full_name))]


@router.post('/teachers')
def create_teacher(body: TeacherIn, user: User = Depends(admin_only), db: Session = Depends(get_db),
                   _: User = Depends(settings_unlocked)):
    pw = new_password()
    t = User(role=Role.teacher, login=next_teacher_id(db), full_name=body.full_name, subjects=body.subjects,
             school_id=body.school_id, password_hash=hash_password(pw))
    db.add(t)
    db.flush()
    audit(db, user, 'create', 'teacher', t.id, login=t.login)
    db.commit()
    return {**teacher_out(t), 'initial_password': pw}      # yalnız bir dəfə göstərilir


@router.post('/teachers/{uid}/reset-password')
def reset_teacher_password(uid: int, user: User = Depends(admin_only), db: Session = Depends(get_db),
                           _: User = Depends(settings_unlocked)):
    t = get_or_404(db, User, uid, 'Müəllim')
    if t.role != Role.teacher:
        raise HTTPException(400, 'Yalnız müəllim hesabı')
    pw = new_password()
    t.password_hash = hash_password(pw)
    audit(db, user, 'update', 'teacher_password', t.id)
    db.commit()
    return {'initial_password': pw}


@router.post('/teachers/{uid}/archive')
def archive_teacher(uid: int, body: ConfirmIn, user: User = Depends(admin_only), db: Session = Depends(get_db),
                    _: User = Depends(settings_unlocked)):
    t = get_or_404(db, User, uid, 'Müəllim')
    if t.role != Role.teacher:
        raise HTTPException(400, 'Admin hesabı arxivə göndərilə bilməz')
    check_confirm(t.full_name, body.confirm)
    t.archived_at = dt.datetime.now(dt.timezone.utc)
    audit(db, user, 'archive', 'teacher', t.id)
    db.commit()
    return teacher_out(t)


@router.post('/teachers/{uid}/restore')
def restore_teacher(uid: int, user: User = Depends(admin_only), db: Session = Depends(get_db),
                    _: User = Depends(settings_unlocked)):
    t = get_or_404(db, User, uid, 'Müəllim')
    t.archived_at = None
    audit(db, user, 'restore', 'teacher', t.id)
    db.commit()
    return teacher_out(t)


# ---------------------------------------------------------------- Tənzimləmələr kilidi
class UnlockIn(BaseModel):
    password: str = ''


@router.get('/settings/lock')
def lock_state(user: User = Depends(staff)):
    return {'has_password': bool(user.settings_password_hash), 'ttl_minutes': 15}


@router.post('/settings/unlock')
def unlock(body: UnlockIn, user: User = Depends(staff)):
    if user.settings_password_hash and not verify_password(user.settings_password_hash, body.password):
        raise HTTPException(401, 'Parol səhvdir')
    return {'token': settings_token(user), 'ttl_minutes': 15}


class SettingsPasswordIn(BaseModel):
    new: str | None = Field(None, max_length=64)       # None / '' – parolu götür


@router.put('/settings/password')
def set_settings_password(body: SettingsPasswordIn, user: User = Depends(settings_unlocked),
                          db: Session = Depends(get_db)):
    user.settings_password_hash = hash_password(body.new) if body.new else None
    audit(db, user, 'update', 'settings_password', user.id, enabled=bool(body.new))
    db.commit()
    return {'has_password': bool(body.new)}
