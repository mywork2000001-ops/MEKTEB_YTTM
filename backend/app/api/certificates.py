"""Sertifikatlar: şagird (öz sertifikatları, nailiyyətlər), müəllim (siyahı, əl ilə vermək, ləğv, hədlər), açıq yoxlama.
Sertifikat şagirdin hesabına bağlıdır – ad sertifikatda tətbiqdəki adla avtomatik göstərilir (docs/sertifikat-ve-motivasiya-promtu.md)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..certificates import DEFAULT_RULES, achievements, give, rules
from ..db import get_db
from ..deps import require, staff
from ..models import Certificate, Role, SchoolClass, Student, TeachingAssignment, User, now
from ..services import own_assignment, roster
from .common import audit

router = APIRouter(prefix='/api', tags=['certificates'])
student_only = require(Role.student)


def cert_out(c: Certificate, s: Student | None) -> dict:
    return {'id': c.id, 'code': c.code, 'kind': c.kind, 'title': c.title, 'details': {k: v for k, v in (c.details or {}).items()
                                                                                       if k != 'student_code'},
            'issued_at': c.issued_at, 'revoked': c.revoked_at is not None, 'new': c.seen_at is None,
            'student': s.full_name if s else None}


# ---------------------------------------------------------------- şagird
def _me(db: Session, user: User) -> Student:
    s = db.scalar(select(Student).where(Student.user_id == user.id))
    if not s:
        raise HTTPException(404, 'Şagird tapılmadı')
    return s


@router.get('/portal/certificates')
def my_certificates(user: User = Depends(student_only), db: Session = Depends(get_db)):
    s = _me(db, user)
    rows = db.scalars(select(Certificate).where(Certificate.student_id == s.id, Certificate.revoked_at.is_(None))
                      .order_by(Certificate.issued_at.desc()))
    return [cert_out(c, s) for c in rows]


@router.post('/portal/certificates/seen')
def mark_seen(user: User = Depends(student_only), db: Session = Depends(get_db)):
    """Yeni sertifikat pəncərəsi göstərildi – bir də açılmasın."""
    s = _me(db, user)
    for c in db.scalars(select(Certificate).where(Certificate.student_id == s.id, Certificate.seen_at.is_(None))):
        c.seen_at = now()
    db.commit()
    return {'ok': True}


@router.get('/portal/achievements')
def my_achievements(user: User = Depends(student_only), db: Session = Depends(get_db)):
    return achievements(db, _me(db, user))


# ---------------------------------------------------------------- müəllim
@router.get('/certificates')
def list_certificates(ta_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    ids = [s.id for s in roster(db, ta)]
    studs = {s.id: s for s in db.scalars(select(Student).where(Student.id.in_(ids or [0])))}
    rows = db.scalars(select(Certificate).where(Certificate.student_id.in_(ids or [0]),
                                                (Certificate.assignment_id == ta.id) | Certificate.assignment_id.is_(None))
                      .order_by(Certificate.issued_at.desc()))
    return {'rules': rules(ta), 'defaults': DEFAULT_RULES, 'items': [cert_out(c, studs.get(c.student_id)) for c in rows]}


class ManualIn(BaseModel):
    ta_id: int
    student_ids: list[int] | None = Field(None, max_length=60)     # None – bütün sinif/qrup
    title: str = Field(min_length=3, max_length=300)
    note: str | None = Field(None, max_length=300)


@router.post('/certificates')
def manual_certificate(body: ManualIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, body.ta_id)
    mine = {s.id: s for s in roster(db, ta)}
    sids = list(mine) if body.student_ids is None else body.student_ids
    if not sids or set(sids) - set(mine):
        raise HTTPException(400, 'Şagirdlər bu sinifdən/qrupdan seçilməlidir')
    stamp = now().strftime('%Y%m%d%H%M%S')
    made = 0
    for sid in sids:
        c = give(db, mine[sid], ta, 'manual', f'manual:{stamp}', body.title, {'note': body.note}, by=user.id)
        if c:
            audit(db, user, 'create', 'certificate', c.id, kind='manual', student=sid)
            made += 1
    db.commit()
    return {'created': made}


@router.post('/certificates/{cid}/revoke')
def revoke(cid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    c = db.get(Certificate, cid)
    if not c or not c.assignment_id:
        raise HTTPException(404, 'Sertifikat tapılmadı')
    own_assignment(db, user, c.assignment_id)
    c.revoked_at = c.revoked_at or now()
    audit(db, user, 'update', 'certificate', c.id, revoked=True)
    db.commit()
    return {'ok': True}


class RulesIn(BaseModel):
    enabled: bool = True
    movzu: int = Field(90, ge=50, le=100)
    sinaq_pct: int = Field(80, ge=50, le=100)
    sinaq_top: int = Field(3, ge=0, le=10)
    seriya: int = Field(80, ge=50, le=100)


@router.put('/certificates/rules/{ta_id}')
def set_rules(ta_id: int, body: RulesIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    ta.cert_rules = body.model_dump()
    audit(db, user, 'update', 'teaching_assignment', ta.id, cert_rules=ta.cert_rules)
    db.commit()
    return rules(ta)


# ---------------------------------------------------------------- açıq yoxlama (girişsiz)
@router.get('/verify/{code}')
def verify(code: str, db: Session = Depends(get_db)):
    c = db.scalar(select(Certificate).where(Certificate.code == code.strip().upper()))
    if not c:
        raise HTTPException(404, 'Belə sertifikat yoxdur')
    s = db.get(Student, c.student_id)
    parts = (s.full_name if s else '').split()
    short = ' '.join(parts[:2]) if len(parts) <= 2 else f'{parts[0]} {parts[1]} {parts[2][0]}.'
    d = c.details or {}
    return {'code': c.code, 'title': c.title, 'kind': c.kind, 'student': short, 'issued_at': c.issued_at,
            'valid': c.revoked_at is None, 'school': d.get('school'), 'teacher': d.get('teacher'), 'subject': d.get('subject'),
            'pct': d.get('pct'), 'place': d.get('place'), 'of': d.get('of')}
