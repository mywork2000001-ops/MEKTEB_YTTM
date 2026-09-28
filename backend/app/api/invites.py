"""Şagirdin özünü qeydiyyatdan keçirmə linki.
Müəllim sinif üçün link yaradır (müddət, say limiti, istənilən vaxt bağlana bilər). Şagird linki açır, ad + doğum tarixi
yazır → təkrar yoxlanılır (ad + doğum tarixi) → giriş kodu və 4 rəqəmli PIN avtomatik yaradılır və YALNIZ bir dəfə göstərilir.
Rəsmi İD-lər soruşulmur və saxlanmır."""
from __future__ import annotations

import datetime as dt
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import staff
from ..models import AuditLog, InviteLink, School, SchoolClass, Student, User, now
from ..seed import add_students
from .common import audit, can_see_class, get_or_404

router = APIRouter(prefix='/api', tags=['invites'])
_attempts: dict[str, list[float]] = {}          # IP üzrə sadə sürət limiti (qeydiyyat)


def aware(t: dt.datetime) -> dt.datetime:
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def _valid(link: InviteLink | None) -> bool:
    return bool(link and link.active and link.uses < link.max_uses and aware(link.expires_at) > now())


def link_out(l: InviteLink, db: Session) -> dict:
    regs = db.scalars(select(AuditLog).where(AuditLog.action == 'self_register', AuditLog.entity == 'invite',
                                             AuditLog.entity_id == str(l.id)).order_by(AuditLog.id.desc())).all()
    return {'id': l.id, 'token': l.token, 'url': f'/join/{l.token}', 'expires_at': aware(l.expires_at),
            'max_uses': l.max_uses, 'uses': l.uses, 'active': _valid(l),
            'registered': [(r.details or {}).get('name') for r in regs]}


class InviteIn(BaseModel):
    days: int = Field(7, ge=1, le=60)
    max_uses: int = Field(40, ge=1, le=200)


@router.post('/classes/{cid}/invites')
def create_invite(cid: int, body: InviteIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    c = get_or_404(db, SchoolClass, cid, 'Sinif')
    if c.kind == 'qrup' or not can_see_class(db, user, c) or c.archived_at:
        raise HTTPException(403, 'Link yalnız öz (ana) sinifləriniz üçün yaradılır')
    l = InviteLink(token=secrets.token_urlsafe(18), class_id=c.id, created_by=user.id, max_uses=body.max_uses,
                   expires_at=now() + dt.timedelta(days=body.days))
    db.add(l)
    db.flush()
    audit(db, user, 'create', 'invite', l.id, class_id=c.id)
    db.commit()
    return link_out(l, db)


@router.get('/classes/{cid}/invites')
def list_invites(cid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    c = get_or_404(db, SchoolClass, cid, 'Sinif')
    if not can_see_class(db, user, c):
        raise HTTPException(403, 'Bu sinif sizin siniflərinizdən deyil')
    return [link_out(l, db) for l in db.scalars(select(InviteLink).where(InviteLink.class_id == cid)
                                                 .order_by(InviteLink.id.desc()))]


@router.post('/invites/{iid}/revoke')
def revoke(iid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    l = get_or_404(db, InviteLink, iid, 'Link')
    if not can_see_class(db, user, db.get(SchoolClass, l.class_id)):
        raise HTTPException(403, 'Bu sinif sizin siniflərinizdən deyil')
    l.active = False
    audit(db, user, 'update', 'invite', l.id, active=False)
    db.commit()
    return {'ok': True}


# ---------------------------------------------------------------- açıq (girişsiz) hissə
@router.get('/join/{token}')
def join_info(token: str, db: Session = Depends(get_db)):
    l = db.scalar(select(InviteLink).where(InviteLink.token == token))
    if not _valid(l):
        raise HTTPException(410, 'Link etibarsızdır və ya müddəti bitib – müəlliminizdən yeni link istəyin')
    c = db.get(SchoolClass, l.class_id)
    return {'school': db.get(School, c.school_id).name, 'class_name': c.name}


class JoinIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    full_name: str = Field(min_length=5, max_length=200)
    birth_date: dt.date
    gender: str | None = Field(None, pattern='^(Qız|Oğlan)$')


@router.post('/join/{token}')
def join(token: str, body: JoinIn, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else '?'
    t = now().timestamp()
    hits = [x for x in _attempts.get(ip, []) if t - x < 600]
    if len(hits) >= 10:
        raise HTTPException(429, 'Çox cəhd – 10 dəqiqədən sonra yenidən yoxlayın')
    _attempts[ip] = hits + [t]
    l = db.scalar(select(InviteLink).where(InviteLink.token == token).with_for_update())
    if not _valid(l):
        raise HTTPException(410, 'Link etibarsızdır və ya müddəti bitib – müəlliminizdən yeni link istəyin')
    name = ' '.join(body.full_name.split())
    if len(name.split()) < 3:
        raise HTTPException(400, 'Soyadı, adı və ata adını tam yazın (məs. Əliyeva Aysel Rəşad qızı)')
    if not dt.date(1990, 1, 1) <= body.birth_date <= dt.date.today():
        raise HTTPException(400, 'Doğum tarixi düzgün deyil')
    c = db.get(SchoolClass, l.class_id)
    if db.scalar(select(Student).where(Student.school_id == c.school_id, Student.full_name.ilike(name),
                                       Student.birth_date == body.birth_date)):
        raise HTTPException(409, 'Siz artıq qeydiyyatdasınız – giriş kodunuzu və PIN-i müəlliminizdən soruşun')

    class _S:                                   # add_students() gözlədiyi forma
        pass
    s = _S()
    s.name, s.birth_date, s.gender = name, body.birth_date, body.gender
    s.score_language = s.score_math = s.score_foreign = None
    rows = add_students(db, c, [s], None)
    if not rows:
        raise HTTPException(409, 'Siz artıq qeydiyyatdasınız – müəlliminizə müraciət edin')
    l.uses += 1
    db.add(AuditLog(action='self_register', entity='invite', entity_id=str(l.id), details={'name': name, 'class': c.name}))
    db.commit()
    _, _, code, pin = rows[0]
    return {'full_name': name, 'class_name': c.name, 'portal_code': code, 'pin': pin}
