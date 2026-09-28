"""Perspektiv plan: dərslərim, işçi plan (gün/həftə/ay/yarımil), rəsmi plan, import, «Mövzunu saxla»,
həftəlik cədvəl (sütun – gün, sətir – dərs saatı, içində mövzu)."""
from __future__ import annotations

import datetime as dt
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import staff
from ..domain.plan import slot_at, view_range
from ..models import PlanHold, School, SchoolClass, TeachingAssignment, User
from ..services import lesson_out, own_assignment, plan_ctx, today
from .common import audit, settings_unlocked

router = APIRouter(prefix='/api', tags=['plan'])
WEEKDAYS = ['B.e.', 'Ç.a.', 'Ç.', 'C.a.', 'C.']


def bell(db: Session, cls: SchoolClass, period: int) -> str | None:
    if cls.bells and str(period) in cls.bells:
        return cls.bells[str(period)]
    s = db.get(School, cls.school_id)
    return (s.bells or {}).get(str(period)) if s else None


@router.get('/my/lessons')
def my_lessons(user: User = Depends(staff), db: Session = Depends(get_db)):
    rows = db.execute(select(TeachingAssignment, SchoolClass).join(SchoolClass)
                      .where(TeachingAssignment.teacher_id == user.id, TeachingAssignment.archived_at.is_(None),
                             SchoolClass.archived_at.is_(None)).order_by(SchoolClass.name))
    out = []
    for ta, c in rows:
        ctx = plan_ctx(db, ta)
        cur = next((s for s in ctx.slots if s.date >= today()), None)
        out.append({'id': ta.id, 'class_id': c.id, 'class_name': c.name, 'kind': c.kind, 'subject': ta.subject,
                    'weekly_hours': ta.weekly_hours, 'slots': ta.slots, 'has_summative': ta.has_summative,
                    'split_with': c.split_with, 'plan_lessons': len(ctx.lessons),
                    'lag': cur.shift if cur else 0, 'unfit': len(ctx.unfit)})
    return out


@router.get('/plan/{ta_id}')
def plan_view(ta_id: int, view: str = 'week', date: dt.date | None = None, user: User = Depends(staff),
              db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    ctx = plan_ctx(db, ta)
    d = date or today()
    try:
        a, b = view_range(view, d, ctx.year.sem1_end, ctx.year.sem2_start, ctx.year.start, ctx.year.end)
    except ValueError:
        raise HTTPException(400, 'görünüş: day, week, month, semester')
    items = [{'date': s.date, 'weekday': WEEKDAYS[s.date.weekday()], 'period': s.period,
              'time': bell(db, ctx.cls, s.period), 'held': s.held, 'shift': s.shift,
              'lesson': lesson_out(ctx.lesson_for(s))} for s in ctx.slots if a <= s.date <= b]
    return {'class_name': ctx.cls.name, 'subject': ta.subject, 'from': a, 'to': b, 'items': items,
            'unfit': [lesson_out(ctx.lessons[i]) for i in ctx.unfit], 'has_plan': bool(ctx.lessons)}


@router.get('/plan/{ta_id}/official')
def official(ta_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    ctx = plan_ctx(db, own_assignment(db, user, ta_id))
    return [lesson_out(pl) for pl in ctx.lessons]


@router.post('/plan/{ta_id}/import')
def import_plan_file(ta_id: int, file: UploadFile = File(...), user: User = Depends(settings_unlocked),
                     db: Session = Depends(get_db)):
    from ..services import import_plan
    ta = own_assignment(db, user, ta_id)
    if not (file.filename or '').lower().endswith('.docx'):
        raise HTTPException(400, 'Word (.docx) faylı seçin')
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / 'plan.docx'
        p.write_bytes(file.file.read())
        try:
            rep = import_plan(db, ta, p)
        except ValueError as e:
            raise HTTPException(400, str(e))
    rep['file'] = file.filename
    audit(db, user, 'import', 'plan', ta.id, lessons=rep['lessons'])
    db.commit()
    return rep


class HoldIn(BaseModel):
    date: dt.date
    period: int = Field(ge=0, le=9)
    reason: str | None = Field(None, max_length=300)


@router.post('/plan/{ta_id}/hold')
def hold(ta_id: int, body: HoldIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Mövzunu saxla – gündəlik iş olduğundan Tənzimləmələr kilidi tələb olunmur."""
    ta = own_assignment(db, user, ta_id)
    ctx = plan_ctx(db, ta)
    if not slot_at(ctx.slots, body.date, body.period):
        raise HTTPException(400, 'Bu tarixdə və saatda dərsiniz yoxdur')
    if db.scalar(select(PlanHold).where(PlanHold.assignment_id == ta.id, PlanHold.date == body.date,
                                        PlanHold.period == body.period)):
        raise HTTPException(409, 'Bu dərsdə mövzu artıq saxlanılıb')
    db.add(PlanHold(assignment_id=ta.id, date=body.date, period=body.period, reason=body.reason, created_by=user.id))
    audit(db, user, 'create', 'plan_hold', ta.id, date=str(body.date), period=body.period)
    db.commit()
    return {'ok': True}


@router.delete('/plan/{ta_id}/hold')
def unhold(ta_id: int, date: dt.date, period: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    h = db.scalar(select(PlanHold).where(PlanHold.assignment_id == ta.id, PlanHold.date == date,
                                         PlanHold.period == period))
    if not h:
        raise HTTPException(404, 'Saxlama tapılmadı')
    db.delete(h)
    audit(db, user, 'delete', 'plan_hold', ta.id, date=str(date), period=period)
    db.commit()
    return {'ok': True}


@router.get('/timetable')
def timetable(date: dt.date | None = None, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Müəllimin həftəlik cədvəli mövzularla: {gün: {saat: [{sinif, mövzu, vaxt}]}}."""
    d = date or today()
    a = d - dt.timedelta(days=d.weekday())
    days = [a + dt.timedelta(days=i) for i in range(5)]
    grid: dict[str, dict[str, list]] = {str(x): {} for x in days}
    tas = db.scalars(select(TeachingAssignment).where(TeachingAssignment.teacher_id == user.id,
                                                      TeachingAssignment.archived_at.is_(None)))
    for ta in tas:
        ctx = plan_ctx(db, ta)
        if ctx.cls.archived_at:
            continue
        for s in ctx.slots:
            if a <= s.date <= days[-1]:
                pl = ctx.lesson_for(s)
                grid[str(s.date)].setdefault(str(s.period), []).append({
                    'ta_id': ta.id, 'class_name': ctx.cls.name, 'subject': ta.subject,
                    'time': bell(db, ctx.cls, s.period), 'topic': pl.topic if pl else None,
                    'assessment_type': pl.assessment_type if pl else None, 'held': s.held})
    return {'week_start': a, 'days': [{'date': x, 'weekday': WEEKDAYS[i], 'periods': grid[str(x)]}
                                      for i, x in enumerate(days)]}


def _plan_key(s: str) -> str:
    """Fayl adı və sinif adı üçün ortaq açar: «X-b sinif – riyaziyyat qrupu» ≈ «X b (riyaziyyat qrupu)»."""
    import re
    s = s.lower().replace('i̇', 'i')
    s = s.split(' – riyaziyyat perspektiv')[0].split(' - riyaziyyat perspektiv')[0]
    for w in ('bütöv sinif', 'sinifi', 'sinfi', 'sinif'):
        s = s.replace(w, ' ')
    return re.sub(r'[\s\-–()_.]+', '', s)


@router.post('/plan/import-many')
def import_many(files: list[UploadFile] = File(...), user: User = Depends(settings_unlocked),
                db: Session = Depends(get_db)):
    """Bir neçə rəsmi planı birdən yükləyir; fayl adına görə müəllimin öz dərs bağlılığına eşləşdirilir."""
    from ..services import import_plan
    tas = {}
    for ta, c in db.execute(select(TeachingAssignment, SchoolClass).join(SchoolClass).where(
            TeachingAssignment.teacher_id == user.id, TeachingAssignment.archived_at.is_(None))):
        tas[_plan_key(c.name)] = (ta, c)
    out = []
    for f in files:
        name = f.filename or ''
        hit = tas.get(_plan_key(name.rsplit('.', 1)[0])) if name.lower().endswith('.docx') else None
        if not hit:
            out.append({'file': name, 'ok': False, 'message': 'Uyğun sinif tapılmadı'})
            continue
        ta, c = hit
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'plan.docx'
            p.write_bytes(f.file.read())
            try:
                rep = import_plan(db, ta, p)
            except ValueError as e:
                out.append({'file': name, 'ok': False, 'message': str(e)})
                continue
        audit(db, user, 'import', 'plan', ta.id, lessons=rep['lessons'])
        out.append({'file': name, 'ok': True, 'class_name': c.name, 'lessons': rep['lessons'],
                    'ksq': rep['ksq'], 'bsq': rep['bsq'], 'warnings': rep['warnings'][:5]})
    db.commit()
    return out
