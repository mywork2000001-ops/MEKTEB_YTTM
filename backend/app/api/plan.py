"""Perspektiv plan: dərslərim, işçi plan (gün/həftə/ay/yarımil), rəsmi plan, import, «Mövzunu saxla»,
həftəlik cədvəl (sütun – gün, sətir – dərs saatı, içində mövzu)."""
from __future__ import annotations

import datetime as dt
import tempfile
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..services import ws_cond
from ..db import get_db
from ..deps import staff
from ..domain.plan import slot_at, view_range
from ..models import PlanHold, School, SchoolClass, TeachingAssignment, User
from ..services import lesson_out, own_assignment, plan_ctx, today
from .common import audit, settings_unlocked

router = APIRouter(prefix='/api', tags=['plan'])
WEEKDAYS = ['B.e.', 'Ç.a.', 'Ç.', 'C.a.', 'C.', 'Ş.', 'B.']     # Ş./B. – yalnız fərdi məkanda


def bell(db: Session, cls: SchoolClass, period: int, ta: TeachingAssignment | None = None, d: dt.date | None = None,
         wd: int | None = None) -> str | None:
    """Dərsin vaxtı: fərdi qrupun real vaxtı (ta.times, gün + sıra) → sinfin zəngi → məktəbin zəngi."""
    if ta is not None and ta.times:
        w = d.weekday() if d is not None else wd
        t = ta.times.get(f'{w}:{period}') if w is not None else None
        if t:
            return t
    if cls.bells and str(period) in cls.bells:
        return cls.bells[str(period)]
    s = db.get(School, cls.school_id)
    return (s.bells or {}).get(str(period)) if s else None


@router.get('/my/lessons')
def my_lessons(user: User = Depends(staff), db: Session = Depends(get_db)):
    from ..programs import ensure_current
    ensure_current(db, user)                 # hər sinif/qrupun mövcud planı əsas proqram kimi görünsün (əvvəldən)
    db.commit()
    rows = db.execute(select(TeachingAssignment, SchoolClass).join(SchoolClass)
                      .where(TeachingAssignment.teacher_id == user.id, ws_cond(user), TeachingAssignment.archived_at.is_(None),
                             SchoolClass.archived_at.is_(None)).order_by(SchoolClass.name))
    out = []
    for ta, c in rows:
        ctx = plan_ctx(db, ta)
        cur = next((s for s in ctx.slots if s.date >= today()), None)
        y = ctx.year
        # cari yarımil: II yarımil başlayıbsa – 2, əks halda 1 (qış tətilində bitmiş I yarımil)
        sem = 2 if today() >= y.sem2_start else 1
        from ..models import AssignmentProgram, PlanProgram
        prog = db.get(PlanProgram, ta.program_id) if ta.program_id else None
        n_extra = len(list(db.scalars(select(AssignmentProgram.id).where(AssignmentProgram.assignment_id == ta.id))))
        out.append({'id': ta.id, 'class_id': c.id, 'class_name': c.name, 'kind': c.kind, 'subject': ta.subject,
                    'semester': sem, 'program': prog.title if prog else None, 'extra_programs': n_extra,
                    'weekly_hours': ta.weekly_hours, 'slots': ta.slots, 'has_summative': ta.has_summative,
                    'split_with': c.split_with, 'plan_lessons': len(ctx.lessons),
                    'lag': cur.shift if cur else 0, 'unfit': len(ctx.unfit)})
    return out


def attach_p0010(db: Session, cls, lessons: list[dict]) -> None:
    """X–XI sinif: hər plan dərsinə P0010 test faylı (docs/x-xi-p0010-testleri-promtu.md) – müəllimin seçimi
    (LessonBankLink) varsa o, yoxdursa mövzuya ən uyğun fayl. p0010_manual – müəllim özü seçib/götürüb."""
    from ..services import class_grade
    if class_grade(db, cls) not in (10, 11) or not lessons:
        return
    from ..bank.match import Matcher
    from ..models import BankFile, LessonBankLink
    ids = [l['id'] for l in lessons if l.get('id')]
    manual = {k.plan_lesson_id: k for k in db.scalars(select(LessonBankLink).where(LessonBankLink.plan_lesson_id.in_(ids or [0])))}
    m = None
    for l in lessons:
        k = manual.get(l.get('id'))
        if k is not None:
            f = db.get(BankFile, k.file_id) if k.file_id else None
            l['p0010'] = f and {'file_id': f.id, 'label': f.label, 'url': f.url}
            l['p0010_manual'] = True
            continue
        if l.get('assessment_type') in ('KSQ', 'BSQ'):          # summativ dərsə mövzu testi verilmir
            continue
        m = m or Matcher(db)
        best = m.matches(l['topic'], l.get('section'), 1)
        l['p0010'] = {'file_id': best[0][0].id, 'label': best[0][0].label, 'url': best[0][0].url} if best else None


class P0010In(BaseModel):
    mode: Literal['auto', 'none', 'file']
    file_id: int | None = None


@router.put('/plan/{ta_id}/topics/{pl_id}/p0010')
def set_p0010(ta_id: int, pl_id: int, body: P0010In, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Müəllim dərsin P0010 faylını dəyişir: auto – avtomatik uyğunluğa qayıt, none – bağlantı yoxdur, file – bu fayl."""
    from ..bank.match import SOURCE
    from ..models import BankFile, LessonBankLink, PlanLesson
    ta = own_assignment(db, user, ta_id)
    pl = db.get(PlanLesson, pl_id)
    if not pl or pl.assignment_id != ta.id:
        raise HTTPException(404, 'Mövzu bu dərsin planında yoxdur')
    k = db.scalar(select(LessonBankLink).where(LessonBankLink.plan_lesson_id == pl.id))
    if body.mode == 'auto':
        if k:
            db.delete(k)
    else:
        fid = None
        if body.mode == 'file':
            f = db.get(BankFile, body.file_id) if body.file_id else None
            if not f or f.source_key != SOURCE or not f.active:
                raise HTTPException(400, 'P0010 faylı tapılmadı')
            fid = f.id
        if k is None:
            k = LessonBankLink(plan_lesson_id=pl.id)
            db.add(k)
        k.file_id, k.set_by = fid, user.id
    audit(db, user, 'update', 'lesson_bank_link', pl.id, mode=body.mode, file_id=body.file_id)
    db.commit()
    x = {'id': pl.id, 'topic': pl.topic, 'section': pl.section, 'assessment_type': pl.assessment_type}
    attach_p0010(db, db.get(SchoolClass, ta.class_id), [x])
    return {'p0010': x.get('p0010'), 'p0010_manual': bool(x.get('p0010_manual'))}


@router.get('/plan/{ta_id}')
def plan_view(ta_id: int, view: str = 'week', date: dt.date | None = None, user: User = Depends(staff),
              db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    ctx = plan_ctx(db, ta)
    d = date or today()
    try:
        a, b = view_range(view, d, ctx.year.sem1_end, ctx.year.sem2_start, ctx.year.start, ctx.year.end,
                          weekend=any(k in ('5', '6') for k in (ta.slots or {})))
    except ValueError:
        raise HTTPException(400, 'görünüş: day, week, month, semester')
    items = [{'date': s.date, 'weekday': WEEKDAYS[s.date.weekday()], 'period': s.period,
              'time': bell(db, ctx.cls, s.period, ctx.ta, s.date), 'held': s.held, 'shift': s.shift,
              'lesson': lesson_out(ctx.lesson_for(s))} for s in ctx.slots if a <= s.date <= b]
    from .topic_tests import topic_tests
    tests = topic_tests(db, ta, {i['lesson']['id'] for i in items if i['lesson']})
    for i in items:
        if i['lesson']:
            i['lesson']['tests'] = tests.get(i['lesson']['id'], [])
    attach_p0010(db, ctx.cls, [i['lesson'] for i in items if i['lesson']])
    return {'class_name': ctx.cls.name, 'subject': ta.subject, 'from': a, 'to': b, 'items': items,
            'unfit': [lesson_out(ctx.lessons[i]) for i in ctx.unfit], 'has_plan': bool(ctx.lessons)}


@router.get('/plan/{ta_id}/official')
def official(ta_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Rəsmi plan + icrası: hər mövzunun jurnalda keçildiyi tarixlər və işçi plana görə nəzərdə tutulan tarix."""
    from ..models import JournalEntry
    ctx = plan_ctx(db, own_assignment(db, user, ta_id))
    taught: dict[int, list] = {}
    for e in db.scalars(select(JournalEntry).where(JournalEntry.assignment_id == ctx.ta.id,
                                                   JournalEntry.plan_lesson_id.is_not(None)).order_by(JournalEntry.date)):
        taught.setdefault(e.plan_lesson_id, []).append(e.date)
    work: dict[int, dt.date] = {}
    for s in ctx.slots:
        if s.index is not None:
            work.setdefault(s.index, s.date)
    t = today()
    out = []
    for i, pl in enumerate(ctx.lessons):
        d = taught.get(pl.id, [])
        wd = work.get(i)
        out.append({**lesson_out(pl), 'taught_dates': d, 'working_date': wd,
                    'status': 'keçilib' if d else 'gecikir' if wd and wd < t else 'gözlənilir'})
    return out


# ---------------------------------------------------------------- mövzu icrası (irəliləyiş / geriləmə)
@router.get('/my/progress')
def progress_overview(user: User = Depends(staff), db: Session = Depends(get_db)):
    """Bütün dərslərim üzrə icmal: keçilib / cəmi, fərq (irəlidə + / geridə −), sığmayan."""
    from ..progress import topic_progress
    t = today()
    out = []
    for ta, c in db.execute(select(TeachingAssignment, SchoolClass).join(SchoolClass).where(
            TeachingAssignment.teacher_id == user.id, ws_cond(user), TeachingAssignment.archived_at.is_(None),
            SchoolClass.archived_at.is_(None)).order_by(SchoolClass.name)):
        p = topic_progress(db, plan_ctx(db, ta), t)
        out.append({'ta_id': ta.id, 'class_name': c.name, 'subject': ta.subject, **p['summary'],
                    'shortfall': p['forecast']['shortfall'],
                    'next': next(({'seq': x['seq'], 'topic': x['topic']} for x in p['topics']
                                  if x['status'] not in ('keçildi', 'təkrar')), None)})
    return out


@router.get('/plan/{ta_id}/progress')
def progress(ta_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    from ..progress import topic_progress
    ctx = plan_ctx(db, own_assignment(db, user, ta_id))
    return {'class_name': ctx.cls.name, 'subject': ctx.ta.subject, **topic_progress(db, ctx, today())}


class TopicIn(BaseModel):
    status: Literal['keçildi', 'təkrar', 'qismən']
    done_on: dt.date | None = None                      # boş – bu gün
    note: str | None = Field(None, max_length=300)


class TopicsBulkIn(TopicIn):
    ids: list[int] = Field(min_length=1, max_length=400)


def _set_topic(db: Session, user: User, ta: TeachingAssignment, pl_id: int, body: TopicIn):
    from ..models import PlanLesson, TopicProgress
    pl = db.get(PlanLesson, pl_id)
    if not pl or pl.assignment_id != ta.id:
        raise HTTPException(404, 'Mövzu bu dərsin planında yoxdur')
    d = body.done_on or today()
    if d > today():
        raise HTTPException(400, 'Gələcək tarixlə «keçildi» qeyd olunmur')
    m = db.scalar(select(TopicProgress).where(TopicProgress.assignment_id == ta.id, TopicProgress.plan_lesson_id == pl_id))
    if not m:
        m = TopicProgress(assignment_id=ta.id, plan_lesson_id=pl_id)
        db.add(m)
    m.status, m.done_on, m.note, m.updated_by = body.status, d, (body.note or '').strip() or None, user.id
    return pl


@router.put('/plan/{ta_id}/topics/{pl_id}')
def set_topic(ta_id: int, pl_id: int, body: TopicIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Gündəlik iş – Tənzimləmələr kilidi tələb olunmur (Mövzunu saxla kimi)."""
    ta = own_assignment(db, user, ta_id)
    pl = _set_topic(db, user, ta, pl_id, body)
    audit(db, user, 'update', 'topic_progress', ta.id, seq=pl.seq, status=body.status)
    db.commit()
    return {'ok': True}


@router.post('/plan/{ta_id}/topics/bulk')
def set_topics_bulk(ta_id: int, body: TopicsBulkIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Toplu qeyd: məs. «№1–№12 keçildi» (tətbiqə gec başlayan müəllim üçün)."""
    ta = own_assignment(db, user, ta_id)
    seqs = [_set_topic(db, user, ta, i, body).seq for i in dict.fromkeys(body.ids)]
    audit(db, user, 'update', 'topic_progress', ta.id, count=len(seqs), status=body.status)
    db.commit()
    return {'ok': True, 'count': len(seqs)}


@router.delete('/plan/{ta_id}/topics/{pl_id}')
def clear_topic(ta_id: int, pl_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Əl ilə qeydi götürür – jurnal yazılıbsa, mövzu yenə «keçildi» sayılır."""
    from ..models import TopicProgress
    ta = own_assignment(db, user, ta_id)
    m = db.scalar(select(TopicProgress).where(TopicProgress.assignment_id == ta.id, TopicProgress.plan_lesson_id == pl_id))
    if not m:
        raise HTTPException(404, 'Qeyd tapılmadı')
    db.delete(m)
    audit(db, user, 'delete', 'topic_progress', ta.id, plan_lesson_id=pl_id)
    db.commit()
    return {'ok': True}


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
    days = [a + dt.timedelta(days=i) for i in range(7)]
    grid: dict[str, dict[str, list]] = {str(x): {} for x in days}
    tas = db.scalars(select(TeachingAssignment).where(TeachingAssignment.teacher_id == user.id, ws_cond(user),
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
                    'time': bell(db, ctx.cls, s.period, ctx.ta, s.date), 'topic': pl.topic if pl else None,
                    'assessment_type': pl.assessment_type if pl else None, 'held': s.held})
    # şənbə/bazar – yalnız həmin gün dərs varsa (fərdi qrup); məktəb həftəsi 5 gün qalır
    return {'week_start': a, 'days': [{'date': x, 'weekday': WEEKDAYS[i], 'periods': grid[str(x)]}
                                      for i, x in enumerate(days) if i < 5 or grid[str(x)]]}


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
            TeachingAssignment.teacher_id == user.id, ws_cond(user), TeachingAssignment.archived_at.is_(None))):
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
