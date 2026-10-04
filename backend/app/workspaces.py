"""Məkanlar (docs/ferdi-sinif-promtu.md): əsas məktəb və müəllimin fərdi (repetitor) məkanı.

Fərdi məkan – `schools.kind = 'private'`, `owner_id` – sahibi. Məktəb axtarışında, admin siyahılarında, məktəb hesabatında görünmür.
Aktiv məkan – `users.active_school_id`; sorğu boyu istifadəçinin `school_id`-si aktiv məkana bərabər götürülür (bazada dəyişmir,
`set_committed_value`), beləliklə məktəbə bağlı bütün mövcud kod fərdi məkanda da eyni işləyir, məlumatlar isə qarışmır."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from .models import AcademicYear, Holiday, Role, School, User


def private_of(db: Session, user: User) -> School | None:
    return db.scalar(select(School).where(School.kind == 'private', School.owner_id == user.id, School.archived_at.is_(None)))


def main_school_id(user: User) -> int | None:
    return getattr(user, 'main_school_id', user.school_id)


def apply_active(db: Session, user: User) -> None:
    """Sorğu üçün: aktiv məkan sahibinin fərdi məkanıdırsa – istifadəçinin school_id-si onunla əvəzlənir (bazaya yazılmır)."""
    user.main_school_id = user.school_id                    # xəritələnməmiş atribut – yalnız bu sorğu üçün
    aid = user.active_school_id
    if not aid or aid == user.school_id or user.role == Role.student:
        return
    s = db.get(School, aid)
    if s and s.kind == 'private' and s.owner_id == user.id and not s.archived_at:
        set_committed_value(user, 'school_id', s.id)


def ensure_private(db: Session, user: User) -> School:
    """Fərdi məkan (bir dənə): yoxdursa yaradılır – ad, zənglər, cari tədris ili və bayramlar əsas məktəbdən köçürülür."""
    s = private_of(db, user)
    if s:
        return s
    main = db.get(School, main_school_id(user)) if main_school_id(user) else None
    s = School(name=f'{user.full_name} – fərdi hazırlıq', kind='private', owner_id=user.id,
               bells=dict(main.bells) if main and main.bells else None)
    db.add(s)
    db.flush()
    src = db.scalar(select(AcademicYear).where(AcademicYear.school_id == main.id, AcademicYear.is_current.is_(True))) if main else None
    if src:
        y = AcademicYear(school_id=s.id, name=src.name, start=src.start, sem1_end=src.sem1_end, sem2_start=src.sem2_start,
                         end=src.end, is_current=True)
        db.add(y)
        db.flush()
        copy_holidays(db, src.id, y.id)
    else:
        from .domain.calendar import YEAR_END, YEAR_START
        db.add(AcademicYear(school_id=s.id, name=f'{YEAR_START.year}–{YEAR_END.year}', start=YEAR_START,
                            sem1_end=YEAR_START.replace(year=YEAR_START.year + 1, month=1, day=26),
                            sem2_start=YEAR_START.replace(year=YEAR_START.year + 1, month=2, day=2), end=YEAR_END, is_current=True))
    db.flush()
    return s


def workspaces(db: Session, user: User) -> list[dict]:
    out = []
    mid = main_school_id(user)
    if mid:
        m = db.get(School, mid)
        out.append({'id': m.id, 'name': m.name, 'kind': 'school', 'active': user.school_id == m.id})
    p = private_of(db, user)
    if p:
        out.append({'id': p.id, 'name': p.name, 'kind': 'private', 'active': user.school_id == p.id})
    return out


def copy_holidays(db: Session, src_year: int, dst_year: int) -> None:
    """Məktəbin bayramlarını fərdi məkana köçürür. Məktəbdə həftəsonu qeyd olunmur, fərdi qrupda isə şənbə/bazar dərsi ola bilər –
    ona görə eyni adlı tətilin içindəki həftəsonu günləri də tətilə əlavə olunur (məs. qış tətili 30.12–06.01)."""
    hs = list(db.scalars(select(Holiday).where(Holiday.year_id == src_year).order_by(Holiday.date)))
    days = {h.date: h.name for h in hs}
    for a, b in zip(hs, hs[1:]):
        if a.name == b.name and 1 < (b.date - a.date).days <= 3:
            d = a.date + dt.timedelta(days=1)
            while d < b.date:
                days.setdefault(d, a.name)
                d += dt.timedelta(days=1)
    db.add_all(Holiday(year_id=dst_year, date=d, name=n) for d, n in sorted(days.items()))
