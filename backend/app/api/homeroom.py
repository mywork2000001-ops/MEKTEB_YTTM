"""Dərs sayı, müvəffəqiyyət və sinif rəhbəri.

Sinif rəhbəri (qərarlar):
- hər bütöv sinfin bir rəhbəri olur; admin təyin edir, müəllim rəhbəri olmayan sinfi özü götürə və özünü çıxara bilər;
- rəhbər sinfin BÜTÜN fənləri üzrə yalnız yekun göstəriciləri görür (dərs sayı, fənn qiyməti, müvəffəqiyyət,
  davamiyyət) – başqa müəllimin jurnal qeydlərini, şərhlərini, valideyn qeydlərini, fərdi planlarını və çatlarını görmür;
- valideyn əlaqə məlumatı (ad, telefon) yalnız rəhbər və admin üçündür;
- sinif rəhbərinin jurnalı: valideyn iclası, sinif saatı, tədbir, ekskursiya (iştirak etməyənlər ilə)."""
from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import staff
from ..domain.rules import ABSENCE_WARN_PCT, absence_warning
from ..models import (Attendance, ClassEvent, JournalEntry, Role, SchoolClass, Student, TeachingAssignment, User)
from ..performance import CATEGORIES, category, lesson_counts, metrics, subject_grades
from ..services import own_assignment, plan_ctx, roster, today
from .common import audit, get_or_404, settings_unlocked

router = APIRouter(prefix='/api', tags=['homeroom'])


# ---------------------------------------------------------------- öz fənnim üzrə: dərs sayı və müvəffəqiyyət
def _sem(v: int | None) -> int | None:
    if v not in (None, 1, 2):
        raise HTTPException(400, 'yarımil: 1 və ya 2')
    return v


@router.get('/analytics/{ta_id}/lessons')
def my_lesson_counts(ta_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    ctx = plan_ctx(db, own_assignment(db, user, ta_id))
    t = today()
    return {'class_name': ctx.cls.name, 'subject': ctx.ta.subject, 'today': t,
            'year': lesson_counts(db, ctx, t), 'semesters': [lesson_counts(db, ctx, t, 1), lesson_counts(db, ctx, t, 2)]}


@router.get('/analytics/{ta_id}/performance')
def my_performance(ta_id: int, semester: int | None = None, user: User = Depends(staff), db: Session = Depends(get_db)):
    ctx = plan_ctx(db, own_assignment(db, user, ta_id))
    studs = roster(db, ctx.ta)
    g = subject_grades(db, ctx, _sem(semester), [s.id for s in studs])
    rows = [{'student_id': s.id, 'full_name': s.full_name, **g[s.id]} for s in studs]
    return {'class_name': ctx.cls.name, 'subject': ctx.ta.subject, 'semester': semester,
            'summary': metrics([r['grade'] for r in rows]), 'students': rows}


# ---------------------------------------------------------------- sinif rəhbəri: təyin
def _whole_class(db: Session, user: User, cid: int) -> SchoolClass:
    c = get_or_404(db, SchoolClass, cid, 'Sinif')
    if c.school_id != user.school_id or c.archived_at:
        raise HTTPException(404, 'Sinif tapılmadı')
    if c.kind == 'qrup':
        raise HTTPException(400, 'Sinif rəhbəri yalnız bütöv sinfə təyin olunur (qrupa yox)')
    return c


class HomeroomIn(BaseModel):
    teacher_id: int | None = None           # None – rəhbəri götür


@router.put('/classes/{cid}/homeroom')
def set_homeroom(cid: int, body: HomeroomIn, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    c = _whole_class(db, user, cid)
    if user.role != Role.admin:
        # müəllim: yalnız özünü boş sinfə təyin edə və ya özünü çıxara bilər
        if body.teacher_id not in (None, user.id) or (body.teacher_id is None and c.homeroom_id != user.id) \
                or (body.teacher_id == user.id and c.homeroom_id not in (None, user.id)):
            raise HTTPException(403, 'Sinif rəhbərini admin dəyişir (siz yalnız rəhbəri olmayan sinfi götürə bilərsiniz)')
    if body.teacher_id is not None:
        t = db.get(User, body.teacher_id)
        if not t or t.archived_at or t.role == Role.student or t.school_id != c.school_id:
            raise HTTPException(404, 'Müəllim tapılmadı')
    c.homeroom_id = body.teacher_id
    audit(db, user, 'update', 'homeroom', c.id, teacher_id=body.teacher_id)
    db.commit()
    return {'ok': True, 'homeroom': _hr(db, c)}


def _hr(db: Session, c: SchoolClass):
    u = db.get(User, c.homeroom_id) if c.homeroom_id else None
    return u and {'id': u.id, 'name': u.full_name}


# ---------------------------------------------------------------- sinif rəhbəri: siniflərim
def homeroom_class(db: Session, user: User, cid: int) -> SchoolClass:
    c = _whole_class(db, user, cid)
    if user.role != Role.admin and c.homeroom_id != user.id:
        raise HTTPException(403, 'Siz bu sinfin rəhbəri deyilsiniz')
    return c


@router.get('/homeroom')
def my_homerooms(all: bool = False, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Rəhbəri olduğum siniflər. Admin «all=1» ilə məktəbin bütün bütöv siniflərinə baxa bilər
    (defolt – yalnız özününkü, başqa müəllimin sinfi «mənim sinfim» kimi görünməsin)."""
    st = select(SchoolClass).where(SchoolClass.school_id == user.school_id, SchoolClass.archived_at.is_(None),
                                   SchoolClass.kind != 'qrup')
    if not (all and user.role == Role.admin):
        st = st.where(SchoolClass.homeroom_id == user.id)
    return [{'id': c.id, 'name': c.name, 'homeroom': _hr(db, c), 'mine': c.homeroom_id == user.id}
            for c in db.scalars(st.order_by(SchoolClass.name))]


def _assignments(db: Session, c: SchoolClass) -> list[TeachingAssignment]:
    """Sinfin bütün fənləri: bütöv sinfə və onun qruplarına bağlılıqlar."""
    groups = list(db.scalars(select(SchoolClass.id).where(SchoolClass.parent_id == c.id, SchoolClass.archived_at.is_(None))))
    return list(db.scalars(select(TeachingAssignment).where(
        TeachingAssignment.class_id.in_([c.id, *groups]), TeachingAssignment.archived_at.is_(None))
        .order_by(TeachingAssignment.subject)))


@router.get('/homeroom/{cid}')
def homeroom_summary(cid: int, semester: int | None = None, user: User = Depends(staff), db: Session = Depends(get_db)):
    c = homeroom_class(db, user, cid)
    sem = _sem(semester)
    t = today()
    studs = list(db.scalars(select(Student).where(Student.class_id == c.id, Student.archived_at.is_(None))
                            .order_by(Student.full_name)))
    sids = {s.id for s in studs}
    subjects, grid = [], {s.id: {} for s in studs}
    entries_by_ta: dict[int, dict[int, JournalEntry]] = {}
    for ta in _assignments(db, c):
        ctx = plan_ctx(db, ta)
        members = [s.id for s in roster(db, ta) if s.id in sids]
        g = subject_grades(db, ctx, sem, members)
        for sid in members:
            grid[sid][ta.id] = g[sid]['grade']
        teacher = db.get(User, ta.teacher_id)
        label = ta.subject + (f' ({ctx.cls.name})' if ctx.cls.id != c.id else '')
        subjects.append({'ta_id': ta.id, 'subject': ta.subject, 'label': label, 'teacher': teacher.full_name,
                         'group': ctx.cls.name if ctx.cls.id != c.id else None, 'students': len(members),
                         'lessons': lesson_counts(db, ctx, t, sem),
                         'performance': metrics([g[sid]['grade'] for sid in members])})
        a, b = (ctx.year.start, ctx.year.end) if sem is None else \
            ((ctx.year.start, ctx.year.sem1_end) if sem == 1 else (ctx.year.sem2_start, ctx.year.end))
        entries_by_ta[ta.id] = {e.id: e for e in db.scalars(select(JournalEntry).where(
            JournalEntry.assignment_id == ta.id, JournalEntry.date >= a, JournalEntry.date <= b))}
    # davamiyyət – bütün fənlər üzrə
    all_entries = {eid: (ta, e) for ta, es in entries_by_ta.items() for eid, e in es.items()}
    att: dict[int, list[tuple[str, dt.date]]] = {s: [] for s in sids}
    for x in db.scalars(select(Attendance).where(Attendance.entry_id.in_(list(all_entries)),
                                                 Attendance.student_id.in_(list(sids)))):
        att[x.student_id].append((x.status, all_entries[x.entry_id][1].date))
    rows = []
    for s in studs:
        gl = [grid[s.id].get(sub['ta_id']) for sub in subjects]
        a = att[s.id]
        missed = sum(st in ('yox', 'üzrlü') for st, _ in a)
        known = [x for x in gl if x is not None]
        rows.append({'student_id': s.id, 'full_name': s.full_name, 'portal_code': s.portal_code,
                     'birth_date': s.birth_date, 'grades': {str(k): v for k, v in grid[s.id].items()},
                     'avg': round(sum(known) / len(known), 2) if known else None, 'category': category(gl),
                     'lessons': len(a), 'missed': missed, 'unexcused': sum(st == 'yox' for st, _ in a),
                     'excused': sum(st == 'üzrlü' for st, _ in a), 'late': sum(st == 'gecikdi' for st, _ in a),
                     'missed_pct': round(missed * 100 / len(a), 1) if a else None,
                     'absence_warning': absence_warning(missed, len(a)),
                     'absent_today': any(st in ('yox', 'üzrlü') and d == t for st, d in a),
                     'guardians': s.guardians or []})
    graded = [r for r in rows if r['category']]
    cats = {k: sum(r['category'] == k for r in rows) for k in CATEGORIES}
    n = len(graded)
    all_grades = [v for r in rows for v in r['grades'].values()]
    return {
        'class': {'id': c.id, 'name': c.name, 'utis_class': c.utis_class, 'exam_date': c.exam_date,
                  'homeroom': _hr(db, c)},
        'semester': sem, 'today': t, 'subjects': subjects, 'students': rows,
        'summary': {
            'students': len(rows), 'subjects': len(subjects),
            'weekly_hours': sum(sub['lessons']['weekly_hours'] for sub in subjects if not sub['group']) +
                            max([sub['lessons']['weekly_hours'] for sub in subjects if sub['group']] or [0]),
            'lessons_due': sum(sub['lessons']['due'] for sub in subjects),
            'lessons_written': sum(sub['lessons']['written'] for sub in subjects),
            'lessons_missing': sum(sub['lessons']['missing'] for sub in subjects),
            'categories': cats, 'graded': n, 'not_graded': len(rows) - n,
            # sinif üzrə: «2»-si olmayan şagirdlər / qiymətləndirilənlər; keyfiyyət – əlaçı + zərbəçi
            'success_pct': round((n - cats['Geridə qalan']) * 100 / n, 1) if n else None,
            'quality_pct': round((cats['Əlaçı'] + cats['Zərbəçi']) * 100 / n, 1) if n else None,
            'grades': metrics(all_grades),
            'attendance_pct': round(100 - sum(r['missed'] for r in rows) * 100 / max(1, sum(r['lessons'] for r in rows)), 1)
                              if any(r['lessons'] for r in rows) else None,
            'absence_warnings': sum(r['absence_warning'] for r in rows), 'absence_limit_pct': ABSENCE_WARN_PCT,
            'absent_today': [r['full_name'] for r in rows if r['absent_today']],
        },
    }


# ---------------------------------------------------------------- valideyn məlumatı (yalnız rəhbər/admin)
class GuardianIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    relation: Literal['ana', 'ata', 'qəyyum', 'nənə', 'baba', 'digər'] = 'ana'
    phone: str | None = Field(None, max_length=30, pattern=r'^[0-9+()\- ]*$')


@router.put('/homeroom/{cid}/students/{sid}/guardians')
def set_guardians(cid: int, sid: int, body: list[GuardianIn], user: User = Depends(staff), db: Session = Depends(get_db)):
    c = homeroom_class(db, user, cid)
    s = get_or_404(db, Student, sid, 'Şagird')
    if s.class_id != c.id:
        raise HTTPException(404, 'Şagird bu sinifdə deyil')
    if len(body) > 4:
        raise HTTPException(400, 'Ən çox 4 valideyn/qəyyum')
    s.guardians = [g.model_dump() for g in body] or None
    audit(db, user, 'update', 'guardians', sid, count=len(body))       # telefon audit-ə yazılmır
    db.commit()
    return {'ok': True, 'guardians': s.guardians or []}


# ---------------------------------------------------------------- sinif rəhbərinin jurnalı
EVENT_KINDS = ('valideyn iclası', 'sinif saatı', 'tədbir', 'ekskursiya', 'fərdi söhbət', 'digər')


class EventIn(BaseModel):
    date: dt.date
    kind: Literal['valideyn iclası', 'sinif saatı', 'tədbir', 'ekskursiya', 'fərdi söhbət', 'digər']
    title: str = Field(min_length=2, max_length=300)
    note: str | None = Field(None, max_length=5000)
    absent_ids: list[int] = Field(default_factory=list)


def event_out(e: ClassEvent, names: dict[int, str]):
    return {'id': e.id, 'date': e.date, 'kind': e.kind, 'title': e.title, 'note': e.note,
            'absent_ids': e.absent_ids or [], 'absent': [names.get(i, '?') for i in e.absent_ids or []]}


def _names(db: Session, c: SchoolClass) -> dict[int, str]:
    return dict(db.execute(select(Student.id, Student.full_name).where(Student.class_id == c.id)).all())


@router.get('/homeroom/{cid}/events')
def events(cid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    c = homeroom_class(db, user, cid)
    names = _names(db, c)
    rows = db.scalars(select(ClassEvent).where(ClassEvent.class_id == c.id).order_by(ClassEvent.date.desc(), ClassEvent.id.desc()))
    return {'kinds': EVENT_KINDS, 'events': [event_out(e, names) for e in rows]}


def _check_ids(names: dict[int, str], ids: list[int]):
    bad = [i for i in ids if i not in names]
    if bad:
        raise HTTPException(400, 'Şagird bu sinifdə deyil')


@router.post('/homeroom/{cid}/events')
def add_event(cid: int, body: EventIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    c = homeroom_class(db, user, cid)
    names = _names(db, c)
    _check_ids(names, body.absent_ids)
    e = ClassEvent(class_id=c.id, teacher_id=user.id, **body.model_dump())
    db.add(e)
    db.flush()
    audit(db, user, 'create', 'class_event', e.id, kind=e.kind)
    db.commit()
    return event_out(e, names)


@router.put('/homeroom/{cid}/events/{eid}')
def upd_event(cid: int, eid: int, body: EventIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    c = homeroom_class(db, user, cid)
    e = db.get(ClassEvent, eid)
    if not e or e.class_id != c.id:
        raise HTTPException(404, 'Qeyd tapılmadı')
    names = _names(db, c)
    _check_ids(names, body.absent_ids)
    for k, v in body.model_dump().items():
        setattr(e, k, v)
    audit(db, user, 'update', 'class_event', e.id)
    db.commit()
    return event_out(e, names)


@router.delete('/homeroom/{cid}/events/{eid}')
def del_event(cid: int, eid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    c = homeroom_class(db, user, cid)
    e = db.get(ClassEvent, eid)
    if not e or e.class_id != c.id:
        raise HTTPException(404, 'Qeyd tapılmadı')
    db.delete(e)
    audit(db, user, 'delete', 'class_event', eid)
    db.commit()
    return {'ok': True}
