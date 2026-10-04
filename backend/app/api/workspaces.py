"""Məkanlar: əsas məktəb və fərdi (repetitor) məkan – siyahı, yaratma, aktiv məkanı dəyişmə, fərdi məkanın adı və zəngləri."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import staff
from ..models import AcademicYear, Holiday, School, User
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


# ---------------------------------------------------------------- fərdi məkanın təqvimi: tədris ili və bayramlar
def _private_year(db: Session, user: User) -> tuple[School, AcademicYear]:
    s = private_of(db, user)
    if not s:
        raise HTTPException(404, 'Fərdi məkan yoxdur')
    y = db.scalar(select(AcademicYear).where(AcademicYear.school_id == s.id, AcademicYear.is_current.is_(True)))
    if not y:
        raise HTTPException(404, 'Tədris ili tapılmadı')
    return s, y


def _calendar(db: Session, y: AcademicYear) -> dict:
    return {'year': {'id': y.id, 'name': y.name, 'start': y.start, 'sem1_end': y.sem1_end, 'sem2_start': y.sem2_start, 'end': y.end},
            'holidays': [{'id': h.id, 'date': h.date, 'name': h.name}
                         for h in db.scalars(select(Holiday).where(Holiday.year_id == y.id).order_by(Holiday.date))]}


@router.get('/private/calendar')
def private_calendar(user: User = Depends(staff), db: Session = Depends(get_db)):
    _, y = _private_year(db, user)
    return _calendar(db, y)


class YearIn(BaseModel):
    name: str = Field(min_length=4, max_length=20)
    start: dt.date
    sem1_end: dt.date
    sem2_start: dt.date
    end: dt.date

    @model_validator(mode='after')
    def _order(self):
        if not (self.start < self.sem1_end < self.sem2_start <= self.end):
            raise ValueError('Ardıcıllıq: başlanğıc < I yarımilin sonu < II yarımilin başlanğıcı ≤ ilin sonu')
        if (self.end - self.start).days > 400:
            raise ValueError('Tədris ili 400 gündən uzun ola bilməz')
        return self


@router.put('/private/year')
def set_private_year(body: YearIn, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    """Fərdi məkanın tədris ili (məs. yay hazırlığı): perspektiv plan, jurnal günləri, yarımil hesabları yeni tarixlərlə işləyir."""
    _, y = _private_year(db, user)
    y.name, y.start, y.sem1_end, y.sem2_start, y.end = body.name.strip(), body.start, body.sem1_end, body.sem2_start, body.end
    audit(db, user, 'update', 'private_year', y.id, start=str(body.start), end=str(body.end))
    db.commit()
    return _calendar(db, y)


class HolidayIn(BaseModel):
    date: dt.date
    to: dt.date | None = None                   # tətil aralığı (daxil)
    name: str = Field(min_length=2, max_length=120)

    @model_validator(mode='after')
    def _range(self):
        if self.to and (self.to < self.date or (self.to - self.date).days > 120):
            raise ValueError('Aralıq: son tarix başlanğıcdan sonra və 120 gündən qısa olmalıdır')
        return self


@router.post('/private/holidays')
def add_private_holiday(body: HolidayIn, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    """Bayram və ya tətil (aralıq): bu günlərdə dərs yoxdur – plan növbəti dərs gününə sürüşür."""
    _, y = _private_year(db, user)
    have = {h.date for h in db.scalars(select(Holiday).where(Holiday.year_id == y.id))}
    d, last, n = body.date, body.to or body.date, 0
    while d <= last:
        if d not in have and d.weekday() < 5:
            db.add(Holiday(year_id=y.id, date=d, name=body.name.strip()))
            n += 1
        d += dt.timedelta(days=1)
    if not n:
        raise HTTPException(400, 'Əlavə olunacaq iş günü yoxdur (həftəsonu və ya artıq qeyd olunub)')
    audit(db, user, 'create', 'private_holiday', y.id, date=str(body.date), to=str(body.to) if body.to else None, days=n)
    db.commit()
    return _calendar(db, y)


@router.delete('/private/holidays/{hid}')
def del_private_holiday(hid: int, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    _, y = _private_year(db, user)
    h = db.get(Holiday, hid)
    if not h or h.year_id != y.id:
        raise HTTPException(404, 'Bayram tapılmadı')
    db.delete(h)
    audit(db, user, 'delete', 'private_holiday', hid)
    db.commit()
    return _calendar(db, y)


@router.post('/private/calendar/reset')
def reset_private_calendar(user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    """Məktəbin təqvimini yenidən köçür: tədris ili tarixləri və bayramlar məktəbinki ilə əvəzlənir."""
    _, y = _private_year(db, user)
    mid = main_school_id(user)
    src = db.scalar(select(AcademicYear).where(AcademicYear.school_id == mid, AcademicYear.is_current.is_(True))) if mid else None
    if not src:
        raise HTTPException(404, 'Məktəbin cari tədris ili tapılmadı')
    y.name, y.start, y.sem1_end, y.sem2_start, y.end = src.name, src.start, src.sem1_end, src.sem2_start, src.end
    for h in db.scalars(select(Holiday).where(Holiday.year_id == y.id)):
        db.delete(h)
    db.flush()
    db.add_all(Holiday(year_id=y.id, date=h.date, name=h.name) for h in db.scalars(select(Holiday).where(Holiday.year_id == src.id)))
    audit(db, user, 'update', 'private_year', y.id, reset=True)
    db.commit()
    return _calendar(db, y)
