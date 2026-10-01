"""API üçün ortaq köməkçilər: audit, arxiv təsdiqi, görünmə hüquqları, Tənzimləmələr kilidi."""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import staff
from ..models import AcademicYear, AuditLog, GroupMember, Role, SchoolClass, Student, TeachingAssignment, User

SETTINGS_TTL = 15 * 60          # Tənzimləmələr 15 dəqiqə açıq qalır


def audit(db: Session, user: User | None, action: str, entity: str, entity_id=None, **details):
    db.add(AuditLog(user_id=user.id if user else None, action=action, entity=entity,
                    entity_id=str(entity_id) if entity_id is not None else None, details=details or None))


class ConfirmIn(BaseModel):
    confirm: str                 # silmək üçün adı yazmaq lazımdır


def check_confirm(expected: str, got: str):
    if ' '.join(got.split()).casefold() != ' '.join(expected.split()).casefold():
        raise HTTPException(400, f'Təsdiq üçün adı dəqiq yazın: «{expected}»')


def need_school(user: User) -> int:
    if not user.school_id:
        raise HTTPException(409, 'Əvvəlcə Tənzimləmələrdə məktəbinizi seçin')
    return user.school_id


def current_year(db: Session, school_id: int) -> AcademicYear:
    y = db.scalar(select(AcademicYear).where(AcademicYear.school_id == school_id, AcademicYear.is_current.is_(True)))
    if not y:
        raise HTTPException(409, 'Cari tədris ili təyin edilməyib')
    return y


def my_class_ids(db: Session, user: User) -> set[int] | None:
    """Müəllimin dərs dediyi siniflər (qrupların ana sinfi daxil). Admin üçün None = məktəbin hamısı."""
    if user.role == Role.admin:
        return None
    ids = set(db.scalars(select(TeachingAssignment.class_id).where(TeachingAssignment.teacher_id == user.id,
                                                                   TeachingAssignment.archived_at.is_(None))))
    parents = set(db.scalars(select(SchoolClass.parent_id).where(SchoolClass.id.in_(ids),
                                                                 SchoolClass.parent_id.is_not(None))))
    return ids | parents


def can_see_class(db: Session, user: User, cls: SchoolClass) -> bool:
    if cls.school_id != user.school_id:
        return False
    ids = my_class_ids(db, user)
    return ids is None or cls.id in ids


def can_see_student(db: Session, user: User, s: Student) -> bool:
    """Şagird kartı: öz sinfi müəllimin sinfidir və ya şagird müəllimin dərs dediyi qrupun (tədris qrupu) üzvüdür."""
    if s.school_id != user.school_id:
        return False
    ids = my_class_ids(db, user)
    if ids is None or s.class_id in ids:
        return True
    return bool(db.scalar(select(GroupMember.group_id).where(GroupMember.student_id == s.id,
                                                             GroupMember.group_id.in_(ids)).limit(1)))


# ---------------------------------------------------------------- Tənzimləmələr kilidi
def _ser():
    return URLSafeTimedSerializer(settings().secret_key, salt='mk-settings')


def settings_token(user: User) -> str:
    return _ser().dumps({'u': user.id})


def settings_unlocked(user: User = Depends(staff),
                      x_settings_token: str | None = Header(None)) -> User:
    """Redaktə əməliyyatları üçün: parol qoyulubsa, 15 dəqiqəlik açar tələb olunur; boşdursa – sərbəst."""
    if not user.settings_password_hash:
        return user
    try:
        data = _ser().loads(x_settings_token or '', max_age=SETTINGS_TTL)
    except (BadSignature, SignatureExpired):
        raise HTTPException(423, 'Tənzimləmələr kilidlidir – parolu daxil edin')
    if data.get('u') != user.id:
        raise HTTPException(423, 'Tənzimləmələr kilidlidir – parolu daxil edin')
    return user


def admin_only_unlocked(user: User = Depends(settings_unlocked)) -> User:
    if user.role != Role.admin:
        raise HTTPException(403, 'Yalnız admin')
    return user


def get_or_404(db: Session, model, id_, what='Qeyd'):
    obj = db.get(model, id_)
    if obj is None:
        raise HTTPException(404, f'{what} tapılmadı')
    return obj


__all__ = ['audit', 'ConfirmIn', 'check_confirm', 'need_school', 'current_year', 'my_class_ids', 'can_see_class',
           'settings_token', 'settings_unlocked', 'get_or_404', 'get_db']
