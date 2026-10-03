"""Sinif rəhbərinin davamiyyət jurnalı: sinfin dərs cədvəli (1–8-ci saat), gündəlik qeyd, aylıq cədvəl.

Qaydalar (docs/sinif-rehberi-davamiyyet-promtu.md):
- sistemdə müəllimi olan dərslər onun bağlılığından (cədvəl yuvaları) gəlir və kilidlidir; qalan fənləri rəhbər yazır;
- fənn müəlliminin jurnalındakı davamiyyət əsasdır – rəhbər onu dəyişmir (yalnız görür); rəhbər qalan saatları qeyd edir;
- bölünən qrupun jurnalı yalnız qrup üzvlərinə aiddir;
- gələcək tarix, həftəsonu, bayram/tətil – qeyd yoxdur."""
from __future__ import annotations

import calendar as cal
import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import staff
from ..domain.calendar import ordinal
from ..domain.rules import ABSENCE_WARN_PCT, absence_warning
from ..models import (AcademicYear, Attendance, ClassLesson, Holiday, HomeroomAttendance, JournalEntry, SchoolClass,
                      Student, User)
from ..services import roster, today
from .common import audit
from .homeroom import _assignments, homeroom_class
from .plan import WEEKDAYS, bell

router = APIRouter(prefix='/api/homeroom', tags=['homeroom'])
PERIODS = range(0, 9)                      # 0 – XI peşə kimi erkən saat; adətən 1–8
OUT = ('yox', 'üzrlü')
CONSECUTIVE_DAYS = 3


# ---------------------------------------------------------------- dərs cədvəli
def _system(db: Session, c: SchoolClass) -> dict[tuple[int, int], list[dict]]:
    """(həftə günü, saat) → sistemdəki dərslər: fənn, müəllim, bağlılıq, qrup üzvləri (bütöv sinif – None)."""
    out: dict[tuple[int, int], list[dict]] = {}
    for ta in _assignments(db, c):
        g = db.get(SchoolClass, ta.class_id)
        members = None if g.id == c.id else {s.id for s in roster(db, ta)}
        t = db.get(User, ta.teacher_id)
        for wd, ps in (ta.slots or {}).items():
            for p in ps:
                out.setdefault((int(wd), p), []).append({'subject': ta.subject + (' (qrup)' if members is not None else ''),
                                                         'teacher': t.full_name if t else None, 'ta_id': ta.id,
                                                         'members': members, 'source': 'sistem'})
    return out


def _manual(db: Session, c: SchoolClass) -> dict[tuple[int, int], ClassLesson]:
    return {(x.weekday, x.period): x for x in db.scalars(select(ClassLesson).where(ClassLesson.class_id == c.id))}


@router.get('/{cid}/timetable')
def timetable(cid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    c = homeroom_class(db, user, cid)
    sysl, man = _system(db, c), _manual(db, c)
    used = {p for (_, p) in sysl} | {p for (_, p) in man}
    periods = sorted(set(range(1, 9)) | used)
    cells = []
    for wd in range(5):
        for p in periods:
            for x in sysl.get((wd, p), []):
                cells.append({'weekday': wd, 'period': p, 'subject': x['subject'], 'teacher': x['teacher'], 'locked': True})
            m = man.get((wd, p))
            if m:
                cells.append({'weekday': wd, 'period': p, 'subject': m.subject, 'teacher': m.teacher, 'locked': False})
    return {'class': c.name, 'weekdays': WEEKDAYS, 'periods': [{'period': p, 'time': bell(db, c, p)} for p in periods],
            'cells': cells}


class CellIn(BaseModel):
    weekday: int = Field(ge=0, le=4)
    period: int = Field(ge=0, le=8)
    subject: str = Field('', max_length=80)
    teacher: str | None = Field(None, max_length=120)


@router.put('/{cid}/timetable')
def save_timetable(cid: int, body: list[CellIn], user: User = Depends(staff), db: Session = Depends(get_db)):
    """Rəhbərin yazdığı dərslər (tam siyahı – göndərilməyən əl ilə yazılmış xanalar silinir)."""
    c = homeroom_class(db, user, cid)
    sysl = _system(db, c)
    keep = set()
    for x in body:
        subj = ' '.join(x.subject.split())
        if not subj:
            continue
        k = (x.weekday, x.period)
        if k in sysl and all(s['members'] is None for s in sysl[k]):
            raise HTTPException(400, f'{WEEKDAYS[x.weekday]} {ordinal(x.period)} saat sistemdəki müəllimin dərsidir '
                                     '(dəyişmək üçün həmin müəllim öz cədvəlini dəyişir)')
        keep.add(k)
        db.merge(ClassLesson(class_id=c.id, weekday=x.weekday, period=x.period, subject=subj,
                             teacher=' '.join((x.teacher or '').split()) or None))
    for k, m in _manual(db, c).items():
        if k not in keep:
            db.delete(m)
    audit(db, user, 'update', 'class_timetable', c.id, cells=len(keep))
    db.commit()
    return timetable(cid, user, db)


# ---------------------------------------------------------------- gün və birləşmiş davamiyyət
def _year(db: Session, c: SchoolClass) -> AcademicYear:
    return db.get(AcademicYear, c.year_id)


def _off(db: Session, y: AcademicYear) -> dict[dt.date, str]:
    return {h.date: h.name for h in db.scalars(select(Holiday).where(Holiday.year_id == y.id))}


def _periods_of(d: dt.date, sysl, man, off, y) -> list[int]:
    if d.weekday() > 4 or d in off or not y.start <= d <= y.end:
        return []
    wd = d.weekday()
    return sorted({p for (w, p) in sysl if w == wd} | {p for (w, p) in man if w == wd})


def _journal(db: Session, c: SchoolClass, sysl, a: dt.date, b: dt.date) -> dict[tuple[dt.date, int, int], str]:
    """Fənn müəllimlərinin jurnalı: (tarix, saat, şagird) → status (yalnız həmin dərsin şagirdləri)."""
    tas = {x['ta_id']: x['members'] for v in sysl.values() for x in v}
    out = {}
    if not tas:
        return out
    entries = {e.id: e for e in db.scalars(select(JournalEntry).where(
        JournalEntry.assignment_id.in_(list(tas)), JournalEntry.date >= a, JournalEntry.date <= b))}
    for x in db.scalars(select(Attendance).where(Attendance.entry_id.in_(list(entries)))):
        e = entries[x.entry_id]
        mem = tas[e.assignment_id]
        if mem is None or x.student_id in mem:
            out[(e.date, e.period, x.student_id)] = x.status
    return out


def _written(db: Session, sysl, a: dt.date, b: dt.date) -> set[tuple[dt.date, int, int]]:
    """Jurnalı yazılmış dərslər: (tarix, saat, bağlılıq)."""
    tas = [x['ta_id'] for v in sysl.values() for x in v]
    return {(e.date, e.period, e.assignment_id) for e in db.scalars(select(JournalEntry).where(
        JournalEntry.assignment_id.in_(tas), JournalEntry.date >= a, JournalEntry.date <= b,
        JournalEntry.auto.is_(False)))} if tas else set()


def _students(db: Session, c: SchoolClass) -> list[Student]:
    return list(db.scalars(select(Student).where(Student.class_id == c.id, Student.archived_at.is_(None))
                           .order_by(Student.full_name)))


def merged(db: Session, c: SchoolClass, a: dt.date, b: dt.date):
    """Birləşmiş davamiyyət: jurnal əsasdır, qalanı rəhbərin qeydi. → (günlər {tarix: [saatlar]}, {(tarix, saat, şagird): (status, mənbə, səbəb)})."""
    y = _year(db, c)
    sysl, man, off = _system(db, c), _manual(db, c), _off(db, y)
    b = min(b, today())
    days = {}
    d = a
    while d <= b:
        ps = _periods_of(d, sysl, man, off, y)
        if ps:
            days[d] = ps
        d += dt.timedelta(days=1)
    rec = {(r.date, r.period, r.student_id): (r.status, 'rəhbər', r.reason) for r in db.scalars(select(HomeroomAttendance).where(
        HomeroomAttendance.class_id == c.id, HomeroomAttendance.date >= a, HomeroomAttendance.date <= b))}
    for k, st in _journal(db, c, sysl, a, b).items():
        rec[k] = (st, 'jurnal', None)
    return days, rec


@router.get('/{cid}/attendance/day')
def att_day(cid: int, date: dt.date | None = None, user: User = Depends(staff), db: Session = Depends(get_db)):
    c = homeroom_class(db, user, cid)
    d = date or today()
    y = _year(db, c)
    sysl, man, off = _system(db, c), _manual(db, c), _off(db, y)
    ps = _periods_of(d, sysl, man, off, y)
    reason = ('Həftəsonu' if d.weekday() > 4 else off.get(d) or ('Tədris ilindən kənar' if not y.start <= d <= y.end else None))
    wd = d.weekday()
    _, rec = merged(db, c, d, d) if d <= today() else ({}, {})
    written = _written(db, sysl, d, d)
    periods = []
    for p in ps:
        les = [{'subject': x['subject'], 'teacher': x['teacher'], 'source': 'sistem',
                'written': (d, p, x['ta_id']) in written, 'group': x['members'] is not None} for x in sysl.get((wd, p), [])]
        if (wd, p) in man:
            les.append({'subject': man[(wd, p)].subject, 'teacher': man[(wd, p)].teacher, 'source': 'rəhbər',
                        'written': False, 'group': False})
        periods.append({'period': p, 'time': bell(db, c, p), 'lessons': les})
    studs = []
    for s in _students(db, c):
        cells = {}
        for p in ps:
            r = rec.get((d, p, s.id))
            cells[str(p)] = {'status': r[0], 'source': r[1], 'reason': r[2]} if r else None
        studs.append({'id': s.id, 'full_name': s.full_name, 'cells': cells,
                      'phones': [g.get('phone') for g in (s.guardians or []) if g.get('phone')]})
    return {'date': d, 'weekday': WEEKDAYS[wd] if wd < 5 else None, 'off_reason': None if ps else reason,
            'future': d > today(), 'periods': periods, 'students': studs}


class MarkIn(BaseModel):
    period: int = Field(ge=0, le=8)
    student_id: int
    status: Literal['var', 'yox', 'üzrlü', 'gecikdi'] | None = None       # None – qeydi sil
    reason: str | None = Field(None, max_length=120)


class DayIn(BaseModel):
    date: dt.date
    marks: list[MarkIn] = Field(max_length=2000)


@router.put('/{cid}/attendance/day')
def save_day(cid: int, body: DayIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    c = homeroom_class(db, user, cid)
    if body.date > today():
        raise HTTPException(400, 'Gələcək günə davamiyyət yazılmır')
    y = _year(db, c)
    sysl, man, off = _system(db, c), _manual(db, c), _off(db, y)
    ps = set(_periods_of(body.date, sysl, man, off, y))
    if not ps:
        raise HTTPException(400, 'Bu gün sinfin dərsi yoxdur (həftəsonu, bayram və ya tətil)')
    sids = {s.id for s in _students(db, c)}
    journal = _journal(db, c, sysl, body.date, body.date)
    saved = locked = 0
    for m in body.marks:
        if m.period not in ps:
            raise HTTPException(400, f'{ordinal(m.period)} saatda bu gün dərs yoxdur')
        if m.student_id not in sids:
            raise HTTPException(400, 'Şagird bu sinifdə deyil')
        if (body.date, m.period, m.student_id) in journal:
            locked += 1                                   # fənn müəlliminin jurnalı əsasdır
            continue
        key = (c.id, body.date, m.period, m.student_id)
        r = db.get(HomeroomAttendance, key)
        if m.status is None:
            if r:
                db.delete(r)
        else:
            r = r or HomeroomAttendance(class_id=c.id, date=body.date, period=m.period, student_id=m.student_id)
            r.status, r.marked_by = m.status, user.id
            r.reason = (m.reason or None) if m.status == 'üzrlü' else None
            db.merge(r)
        saved += 1
    audit(db, user, 'update', 'homeroom_attendance', c.id, date=str(body.date), saved=saved, locked=locked)
    db.commit()
    return {'saved': saved, 'locked': locked, **att_day(cid, body.date, user, db)}


# ---------------------------------------------------------------- aylıq cədvəl və xəbərdarlıqlar
def student_stats(days, rec, sid) -> dict:
    lessons = missed = unexc = exc = late = 0
    streak = best = 0
    per_day = {}
    for d in sorted(days):
        st = [rec.get((d, p, sid)) for p in days[d]]
        known = [x[0] for x in st if x]
        m = sum(x in OUT for x in known)
        per_day[d] = {'marked': len(known), 'missed': m, 'unexcused': known.count('yox'), 'late': known.count('gecikdi')}
        lessons += len(known); missed += m; unexc += known.count('yox'); exc += known.count('üzrlü'); late += known.count('gecikdi')
        whole = bool(known) and m == len(known)
        streak = streak + 1 if whole else (streak if not known else 0)
        best = max(best, streak)
    return {'lessons': lessons, 'missed': missed, 'unexcused': unexc, 'excused': exc, 'late': late,
            'missed_pct': round(missed * 100 / lessons, 1) if lessons else None,
            'absence_warning': absence_warning(missed, lessons), 'max_absent_days': best,
            'consecutive_warning': best >= CONSECUTIVE_DAYS, 'days': per_day}


@router.get('/{cid}/attendance/month')
def att_month(cid: int, month: str | None = None, user: User = Depends(staff), db: Session = Depends(get_db)):
    c = homeroom_class(db, user, cid)
    try:
        yy, mm = map(int, (month or today().strftime('%Y-%m')).split('-'))
        a = dt.date(yy, mm, 1)
    except ValueError:
        raise HTTPException(400, 'ay: YYYY-MM')
    b = dt.date(yy, mm, cal.monthrange(yy, mm)[1])
    days, rec = merged(db, c, a, b)
    rows = []
    for s in _students(db, c):
        st = student_stats(days, rec, s.id)
        rows.append({'student_id': s.id, 'full_name': s.full_name,
                     'phones': [g.get('phone') for g in (s.guardians or []) if g.get('phone')],
                     **{k: v for k, v in st.items() if k != 'days'},
                     'cells': [st['days'][d] for d in sorted(days)]})
    unmarked = sum(1 for d, ps in days.items() for p in ps for s in rows if (d, p, s['student_id']) not in rec)
    return {'month': f'{a:%Y-%m}', 'class': c.name, 'days': [{'date': d, 'weekday': WEEKDAYS[d.weekday()],
                                                              'lessons': len(days[d])} for d in sorted(days)],
            'rows': rows, 'limit_pct': ABSENCE_WARN_PCT, 'consecutive_days': CONSECUTIVE_DAYS, 'unmarked': unmarked,
            'totals': {'lessons': sum(r['lessons'] for r in rows), 'missed': sum(r['missed'] for r in rows),
                       'unexcused': sum(r['unexcused'] for r in rows), 'excused': sum(r['excused'] for r in rows),
                       'late': sum(r['late'] for r in rows)}}
