"""Sınaq seriyası: seçilmiş sınaqlar növbə ilə dövrə görə (gün / həftə / ay) siniflərə özü gedir; bankda yeni sınaq
görünəndə növbəyə düşür (docs/sinaq-seriyasi-promtu.md). Hər yuvada adi sınaq yaranır – «Sınaq jurnalı» və reytinq eynidir."""
from __future__ import annotations

import calendar
import copy
import datetime as dt
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import staff
from ..models import (BankFile, BankQuestion, BankSource, ExamSeries, OnlineTask, Role, School, SchoolClass, TeachingAssignment,
                      TestBatch, User, now)
from ..services import SCHOOL_TZ, class_grade, roster
from .common import audit
from .exams_online import _can_target, given_files, grade_fits
from ..timing import NO_DEADLINE
from .tasks import MIN_TEST_MIN, TestMinutes, _snapshot, aware

router = APIRouter(prefix='/api/exam-series', tags=['exam-series'])
TZ = ZoneInfo(SCHOOL_TZ)
WD = ['B.e.', 'Ç.a.', 'Ç.', 'C.a.', 'C.', 'Ş.', 'B.']


# ---------------------------------------------------------------- yuvalar
def _at(d: dt.date, hm: str) -> dt.datetime:
    h, m = (int(x) for x in hm.split(':'))
    return dt.datetime(d.year, d.month, d.day, h, m, tzinfo=TZ)


def _month_day(y: int, m: int, day: int) -> dt.date:
    return dt.date(y, m, min(day, calendar.monthrange(y, m)[1]))


def advance(s: ExamSeries, t: dt.datetime) -> dt.datetime:
    """Növbəti yuva: gün – +every gün, həftə – +7·every gün, ay – +every ay (ayın günü yoxdursa – son gün)."""
    t = t.astimezone(TZ)
    if s.period == 'day':
        return _at(t.date() + dt.timedelta(days=s.every), s.open_time)
    if s.period == 'week':
        return _at(t.date() + dt.timedelta(days=7 * s.every), s.open_time)
    m = t.month - 1 + s.every
    return _at(_month_day(t.year + m // 12, m % 12 + 1, s.month_day), s.open_time)


def first_slot(s: ExamSeries, start: dt.date, after: dt.datetime) -> dt.datetime:
    """Başlama tarixindən sonrakı ilk yuva (keçmişdə qalanlar atlanır)."""
    if s.period == 'week':
        d = start + dt.timedelta(days=(s.weekday - start.weekday()) % 7)
    elif s.period == 'month':
        d = _month_day(start.year, start.month, s.month_day)
        if d < start:
            d = _month_day(start.year + (start.month == 12), start.month % 12 + 1, s.month_day)
    else:
        d = start
    t = _at(d, s.open_time)
    while t < after:
        t = advance(s, t)
    return t


# ---------------------------------------------------------------- fayllar
# seriyaya yararlı mənbələr; TAİM (P004) – müəllim imtahanıdır, şagird sınağı deyil (köhnə seriyada qalıbsa sükutla atılır)
SERIES_SOURCES = ('sinaqlar', 'p012', 'p009')


def _files_q(sources: list[str]):
    return (select(BankFile).join(BankSource, BankSource.key == BankFile.source_key)
            .where(BankFile.source_key.in_([x for x in sources if x in SERIES_SOURCES]), BankFile.active.is_(True), BankSource.enabled.is_(True),
                   BankFile.question_count > 0).order_by(BankFile.id))


def _grade_ok(f: BankFile, grade: int | None) -> bool:
    return grade is None or not f.grades or grade in f.grades


def _grades(db: Session, ta_ids) -> dict[int, int | None]:
    """Dərs → sinif rəqəmi (arxivlənmiş / əlçatmaz dərs atlanır)."""
    out = {}
    for i in ta_ids:
        ta = db.get(TeachingAssignment, i)
        cls = ta and db.get(SchoolClass, ta.class_id)
        if cls:
            out[i] = class_grade(db, cls)
    return out


def _given_to(db: Session, ta_ids: list[int]) -> dict[int, dict[int, str]]:
    """Fayl → {ta_id: sinif} – sınaq bu dərslərə artıq verilib (təkrar göndərilmir, docs/sinaq-tekrar-qadagasi-promtu.md)."""
    return {fid: {c['ta_id']: c['class_name'] for c in g['classes'] if c['full']}
            for fid, g in given_files(db, ta_ids).items() if g['full']}


@router.get('/files')
def files(sources: str = 'sinaqlar', grade: int | None = None, all_kinds: bool = False, ta_ids: str = '',
          user: User = Depends(staff), db: Session = Depends(get_db)):
    """Sınaq faylları (növ «sınaq»; all_kinds – mənbənin bütün faylları); given – seçilmiş siniflərdən hansına verilib."""
    src = [x for x in sources.split(',') if x]
    tas = []
    for x in {int(x) for x in ta_ids.split(',') if x.strip().isdigit()}:
        try:
            tas.append(_can_target(db, user, x)[0].id)
        except HTTPException:
            continue
    given = _given_to(db, tas)
    gr = _grades(db, tas)
    return [{'id': f.id, 'label': f.label, 'questions': f.question_count, 'kind': f.kind, 'grades': f.grades or [],
             'held_on': f.held_on, 'held_prec': f.held_prec,
             'source': f.source_key, 'given': sorted(given.get(f.id, {}).values()),
             'grade_ok': all(grade_fits(f, g) for g in gr.values())}
            for f in db.scalars(_files_q(src)) if _grade_ok(f, grade) and (all_kinds or f.kind == 'sinaq')]


def _newest_key(f: BankFile):
    """Yenidən köhnəyə sıra açarı: sınağın tarixi azalan (tarixsiz – sonda), sonra fayl id-si azalan."""
    return (f.held_on is None, -(f.held_on.toordinal() if f.held_on else 0), -f.id)


def _spaces(db: Session, user: User) -> set[int]:
    """İstifadəçinin məkanları: əsas məktəb + (varsa) fərdi məkan – zamanlayıcıda aktiv məkandan asılı olmur."""
    from ..workspaces import main_school_id, private_of
    out = {main_school_id(user)}
    p = private_of(db, user)
    if p:
        out.add(p.id)
    return out


def _owner_target(db: Session, user: User, ta_id: int) -> tuple[TeachingAssignment, SchoolClass]:
    """_can_target-in eyni qaydası, amma sahibin hər iki məkanı üçün (məktəb və fərdi): sahibi və ya öz məktəbinin admini."""
    from ..workspaces import main_school_id
    ta = db.get(TeachingAssignment, ta_id)
    cls = ta and db.get(SchoolClass, ta.class_id)
    ok = ta and not ta.archived_at and cls and not cls.archived_at and cls.school_id in _spaces(db, user) and (
        ta.teacher_id == user.id or (user.role == Role.admin and cls.school_id == main_school_id(user)))
    if not ok:
        raise HTTPException(404, 'Dərs tapılmadı')
    return ta, cls


# ---------------------------------------------------------------- iş (scheduler)
def _sync_new(db: Session, s: ExamSeries) -> int:
    """auto_new: seriya yaradılandan sonra bankda görünən, səviyyəsi uyğun sınaqlar növbənin sonuna."""
    known = set(s.queue or []) | {x['file_id'] for x in s.done or []}
    tas = {t['ta_id'] for t in s.targets}
    given = _given_to(db, list(tas))
    gr = _grades(db, tas)
    # avtomatik – yalnız öz sinfinin sınağı (başqa sinfin / sinifsiz fayl müəllimin təsdiqini gözləyir)
    new = [f.id for f in db.scalars(_files_q(s.sources).where(BankFile.id > (s.since_file_id or 0)))
           if f.kind == 'sinaq' and _grade_ok(f, s.grade) and f.id not in known and not tas <= set(given.get(f.id, {}))
           and any(grade_fits(f, g) for g in gr.values())]
    if new and s.newest_first:                       # yenidən köhnəyə: yeni fayl açara görə öz yerinə (müəllimin sırası pozulmur)
        q = list(s.queue or [])
        files = {f.id: f for f in db.scalars(select(BankFile).where(BankFile.id.in_(q + new)))}
        for fid in sorted(new, key=lambda i: _newest_key(files[i])):
            k = _newest_key(files[fid])
            pos = next((n for n, x in enumerate(q) if x not in files or _newest_key(files[x]) > k), len(q))
            q.insert(pos, fid)
        s.queue = q
    elif new:
        s.queue = list(s.queue or []) + new
    return len(new)


def _send(db: Session, s: ExamSeries, f: BankFile, o: dt.datetime) -> TestBatch | None:
    """Bir fayldan adi sınaq – seriyanın bütün siniflərinə (create_exam ilə eyni nəticə)."""
    user = db.get(User, s.created_by)
    ids = list(db.scalars(select(BankQuestion.id).where(BankQuestion.file_id == f.id, BankQuestion.active.is_(True))
                          .order_by(BankQuestion.n).limit(100)))
    if not ids:
        return None
    qs = _snapshot(db, ids)
    c = o + dt.timedelta(hours=s.window_hours) if s.window_hours else NO_DEADLINE      # 0 – müddətsiz
    title = f.label[:200]
    given = _given_to(db, [tg['ta_id'] for tg in s.targets]).get(f.id, {})
    b = None
    for tg in s.targets:
        if tg['ta_id'] in given:
            continue                                         # bu sinfə artıq verilib (əl ilə və ya başqa seriya) – təkrar yox
        try:
            ta, cls = _owner_target(db, user, tg['ta_id'])
        except HTTPException:
            continue                                         # sinif arxivləşib / əlçatmazdır – atlanır
        if not grade_fits(f, class_grade(db, cls)) and f.id not in (s.other_ok or []):
            continue                                         # başqa sinfin sınağı – müəllim təsdiqləməyib
        if b is None:
            b = TestBatch(kind='sinaq', title=title, subject=ta.subject, grade=class_grade(db, cls), penalty=s.penalty,
                          created_by=user.id)
            db.add(b)
            db.flush()
        sids = tg.get('student_ids')
        if sids is not None:
            mine = {st.id for st in roster(db, ta)}
            sids = [x for x in sids if x in mine] or None
        t = OnlineTask(assignment_id=ta.id, title=title, description=f'Sınaq seriyası: {s.title}',
                       opens_at=o.astimezone(dt.timezone.utc), closes_at=c.astimezone(dt.timezone.utc),
                       duration_min=max(s.duration_min, MIN_TEST_MIN) if s.duration_min else 0, questions=copy.deepcopy(qs), shuffle=s.shuffle,
                       show_answers=s.show_answers, student_ids=sids, created_by=user.id, kind='sinaq', batch_id=b.id)
        db.add(t)
        db.flush()
        audit(db, user, 'create', 'task', t.id, kind='sinaq', batch=b.id, series=s.id, class_name=cls.name,
              questions=len(qs))
    return b


def _fire(db: Session, s: ExamSeries, slot: dt.datetime, open_at: dt.datetime) -> int:
    """Bir yuvada növbədən per_slot sınaq göndərir (göndərilməyən / bankdan çıxmış fayl sayılmır)."""
    queue = list(s.queue or [])
    sent = 0
    while queue and sent < (s.per_slot or 1):
        f = db.get(BankFile, queue.pop(0))
        if f is None or not f.active or not f.question_count:
            continue                                     # bankdan çıxıb / sualı yoxdur – atlanır
        b = _send(db, s, f, open_at)
        if b is None:
            continue
        s.done = list(s.done or []) + [{'file_id': f.id, 'batch_id': b.id, 'at': slot.isoformat()}]
        sent += 1
    s.queue = queue
    return sent


MAX_PAST_DAYS = 14


def _past_slots(s: ExamSeries, start: dt.date, t0: dt.datetime) -> list[dt.datetime]:
    """Başlama tarixindən indiyədək qaçırılmış yuvalar (yalnız müddətsiz seriyada doldurulur)."""
    out, t = [], first_slot(s, start, _at(start, '00:00'))
    while t <= t0 and len(out) < 100:
        out.append(t)
        t = advance(s, t)
    return out


def _check_start(start: dt.date | None) -> None:
    if start and start < now().astimezone(TZ).date() - dt.timedelta(days=MAX_PAST_DAYS):
        raise HTTPException(422, f'Başlama tarixi {MAX_PAST_DAYS} gündən çox keçmişdə ola bilməz')


def _backfill(db: Session, s: ExamSeries, start: dt.date, t0: dt.datetime) -> int:
    """Müddətsiz seriyada keçmiş yuvalar yaradılanda bir dəfə doldurulur (opens_at = yuvanın vaxtı); növbəti yuva gələcəkdə."""
    made = 0
    if not s.window_hours and start < t0.astimezone(TZ).date() + dt.timedelta(days=1):
        for slot in _past_slots(s, start, t0):
            made += _fire(db, s, slot, slot)
        s.next_at = first_slot(s, t0.astimezone(TZ).date(), t0 + dt.timedelta(microseconds=1)).astimezone(dt.timezone.utc)
    return made


def run_series(db: Session, at: dt.datetime | None = None, only: int | None = None) -> int:
    """Vaxtı çatmış yuvalarda növbənin ilk sınağını göndərir; auto_new – yeni faylları növbəyə əlavə edir."""
    at = at or now()
    made = 0
    st = select(ExamSeries).where(ExamSeries.active.is_(True))
    if only:
        st = st.where(ExamSeries.id == only)
    for s in db.scalars(st):
        if s.auto_new:
            _sync_new(db, s)
        slot = aware(s.next_at)
        if slot > at:
            continue
        # server yatıb yuvanı bir saatdan çox keçiribsə – sınaq indi açılır (açıq qalma müddəti tam olsun)
        made += _fire(db, s, slot, slot if slot >= at - dt.timedelta(hours=1) else at)
        nxt = advance(s, slot)
        while nxt <= at:                                     # keçmiş yuvalar toplanmır
            nxt = advance(s, nxt)
        s.next_at = nxt.astimezone(dt.timezone.utc)                    # UTC – SQLite saat qurşağını saxlamır
    db.commit()
    return made


# ---------------------------------------------------------------- API
class Target(BaseModel):
    ta_id: int
    student_ids: list[int] | None = None


class SeriesIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    targets: list[Target] = Field(min_length=1, max_length=60)
    sources: list[str] = Field(min_length=1, max_length=10)
    grade: int | None = Field(None, ge=1, le=12)
    queue: list[int] = Field(default_factory=list, max_length=200)
    other_ok: list[int] = Field(default_factory=list, max_length=200)   # başqa sinfin / sinifsiz – təsdiqlənmiş fayllar
    auto_new: bool = True
    period: Literal['day', 'week', 'month'] = 'week'
    every: int = Field(1, ge=1, le=12)
    weekday: int | None = Field(None, ge=0, le=6)
    month_day: int | None = Field(None, ge=1, le=31)
    start: dt.date | None = None
    open_time: str = Field('15:00', pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
    window_hours: int = Field(0, ge=0, le=24 * 31)      # 0 – müddətsiz
    duration_min: TestMinutes = 0                       # 0 – taymer yoxdur
    penalty: Literal[0, 3, 4] = 0
    show_answers: Literal['after_close', 'after_submit', 'never', 'teacher'] = 'after_close'
    shuffle: bool = True
    per_slot: int = Field(1, ge=1, le=2)                # bir yuvada neçə sınaq
    newest_first: bool = False                          # növbə yenidən köhnəyə (yeni seriyada frontend defolt true göndərir)

    @model_validator(mode='after')
    def _v(self):
        if self.period == 'week' and self.weekday is None:
            raise ValueError('həftənin gününü seçin')
        if self.period == 'month' and self.month_day is None:
            raise ValueError('ayın gününü seçin')
        if self.window_hours and self.duration_min > self.window_hours * 60:
            raise ValueError('həll müddəti açıq qalma müddətindən uzundur')
        if not self.queue and not self.auto_new:
            raise ValueError('ən azı bir sınaq seçin və ya «yeni sınaqları avtomatik əlavə et»i açın')
        if any(x not in SERIES_SOURCES for x in self.sources):
            raise ValueError('mənbə: yalnız Sınaqlar, P012, P009')
        if len({t.ta_id for t in self.targets}) != len(self.targets):
            raise ValueError('bir sinif iki dəfə seçilib')
        return self


def _own(db: Session, user: User, sid: int) -> ExamSeries:
    s = db.get(ExamSeries, sid)
    if not s or (s.created_by != user.id and user.role != Role.admin):
        raise HTTPException(404, 'Seriya tapılmadı')
    return s


def _check_queue(db: Session, queue: list[int], sources: list[str]) -> None:
    bad = [i for i in queue if (f := db.get(BankFile, i)) is None or f.source_key not in sources]
    if bad:
        raise HTTPException(400, f'Seçilmiş sınaq bu mənbələrdə yoxdur: {bad[:5]}')


def series_out(db: Session, s: ExamSeries) -> dict:
    q = list(s.queue or [])
    files = {f.id: f for f in db.scalars(select(BankFile).where(BankFile.id.in_(q + [0])))}
    labels = {i: f.label for i, f in files.items()}
    tas = {t['ta_id'] for t in s.targets}
    given = _given_to(db, list(tas)) if q else {}
    gr = _grades(db, tas) if q else {}
    ok = set(s.other_ok or [])
    # sınaq alacaq siniflər: verilməyib və sinfi uyğundur (və ya müəllim təsdiqləyib)
    gets = {i: {ta for ta, g in gr.items() if ta not in given.get(i, {}) and (i in ok or grade_fits(files.get(i), g))} for i in q}
    slots, t = [], aware(s.next_at)
    sendable = [i for i in q if gets[i]]                                    # heç kimə getməyəcəklər atlanır
    ps = s.per_slot or 1
    for i in range(6):
        fids = sendable[i * ps:(i + 1) * ps]
        fid = fids[0] if fids else None
        slots.append({'at': t, 'weekday': WD[t.astimezone(TZ).weekday()], 'file_id': fid, 'label': labels.get(fid),
                      'file_ids': fids, 'labels': [labels.get(x) for x in fids]})
        t = advance(s, t)
    return {'id': s.id, 'title': s.title, 'subject': s.subject, 'targets': s.targets, 'sources': s.sources, 'grade': s.grade,
            'period': s.period, 'every': s.every, 'weekday': s.weekday, 'month_day': s.month_day, 'open_time': s.open_time,
            'window_hours': s.window_hours, 'duration_min': s.duration_min, 'penalty': s.penalty,
            'show_answers': s.show_answers, 'shuffle': s.shuffle, 'auto_new': s.auto_new, 'active': s.active,
            'per_slot': s.per_slot or 1, 'newest_first': bool(s.newest_first),
            'next_at': aware(s.next_at),
            'queue': [{'id': i, 'label': labels.get(i), 'given': sorted(given.get(i, {}).values()),
                       'other_ok': i in ok, 'skip': not gets[i]} for i in q],
            'done': s.done or [], 'preview': slots}


@router.get('')
def list_series(user: User = Depends(staff), db: Session = Depends(get_db)):
    st = select(ExamSeries).order_by(ExamSeries.id.desc())
    if user.role != Role.admin:
        st = st.where(ExamSeries.created_by == user.id)
    return [series_out(db, s) for s in db.scalars(st)]


@router.post('')
def create_series(body: SeriesIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    subjects = set()
    for tg in body.targets:
        ta, cls = _can_target(db, user, tg.ta_id)
        subjects.add(ta.subject)
        if tg.student_ids is not None and (not tg.student_ids or set(tg.student_ids) - {x.id for x in roster(db, ta)}):
            raise HTTPException(400, f'{cls.name}: şagirdlər bu sinifdən/qrupdan seçilməlidir')
    if len(subjects) > 1:
        raise HTTPException(400, 'Bir seriya yalnız bir fənn üzrə ola bilər')
    _check_start(body.start)
    _check_queue(db, body.queue, body.sources)
    if body.newest_first:                                      # yaradılanda növbə yenidən köhnəyə sıralanır
        fm = {f.id: f for f in db.scalars(select(BankFile).where(BankFile.id.in_(body.queue or [0])))}
        body.queue = sorted(dict.fromkeys(body.queue), key=lambda i: _newest_key(fm[i]) if i in fm else (True, 0, -i))
    gr = _grades(db, [t.ta_id for t in body.targets])
    bad = [f.label for i in body.queue if i not in body.other_ok and (f := db.get(BankFile, i))
           and not all(grade_fits(f, g) for g in gr.values())]
    if bad:
        raise HTTPException(409, {'message': f'«{bad[0]}» seçilmiş siniflərin sinfinə uyğun deyil (başqa sinfin və ya sinfi '
                                             'göstərilməmiş sınaq). Təsdiq edin və ya növbədən çıxarın.', 'grade': bad})
    t0 = now()
    s = ExamSeries(created_by=user.id, title=body.title, subject=subjects.pop(), targets=[t.model_dump() for t in body.targets],
                   sources=body.sources, grade=body.grade, period=body.period, every=body.every, weekday=body.weekday,
                   month_day=body.month_day, open_time=body.open_time, window_hours=body.window_hours,
                   duration_min=body.duration_min, penalty=body.penalty, show_answers=body.show_answers,
                   shuffle=body.shuffle, auto_new=body.auto_new, queue=list(dict.fromkeys(body.queue)), done=[],
                   other_ok=[i for i in dict.fromkeys(body.other_ok) if i in body.queue],
                   since_file_id=db.scalar(select(func.coalesce(func.max(BankFile.id), 0))) or 0,
                   per_slot=body.per_slot, newest_first=body.newest_first, next_at=t0, active=True)
    s.next_at = first_slot(s, body.start or t0.astimezone(TZ).date(), t0).astimezone(dt.timezone.utc)
    db.add(s)
    db.flush()
    filled = _backfill(db, s, body.start, t0) if body.start else 0
    audit(db, user, 'create', 'exam_series', s.id, queue=len(s.queue), period=s.period, backfilled=filled)
    db.commit()
    run_series(db, only=s.id)
    return series_out(db, s)


class SeriesPatch(BaseModel):
    active: bool | None = None
    queue: list[int] | None = Field(None, max_length=200)
    auto_new: bool | None = None
    title: str | None = Field(None, min_length=2, max_length=200)


@router.patch('/{sid}')
def patch_series(sid: int, body: SeriesPatch, user: User = Depends(staff), db: Session = Depends(get_db)):
    s = _own(db, user, sid)
    if body.queue is not None:
        _check_queue(db, body.queue, s.sources)
        s.queue = list(dict.fromkeys(body.queue))
    if body.auto_new is not None:
        s.auto_new = body.auto_new
    if body.title is not None:
        s.title = body.title
    if body.active is not None and body.active != s.active:
        s.active = body.active
        if s.active:                                       # davam edəndə növbəti yuva gələcəkdən
            t0 = now()
            s.next_at = first_slot(s, t0.astimezone(TZ).date(), t0).astimezone(dt.timezone.utc)
    audit(db, user, 'update', 'exam_series', s.id, **body.model_dump(exclude_none=True, exclude={'queue'}))
    db.commit()
    return series_out(db, s)


@router.delete('/{sid}')
def delete_series(sid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    s = _own(db, user, sid)
    db.delete(s)
    audit(db, user, 'delete', 'exam_series', sid)
    db.commit()
    return {'ok': True}


# ---------------------------------------------------------------- bütün siniflər üçün avtomatik seriya
class AutoAllIn(BaseModel):
    dry_run: bool = True
    period: Literal['day', 'week', 'month'] = 'day'
    every: int = Field(1, ge=1, le=12)
    weekday: int | None = Field(None, ge=0, le=6)
    month_day: int | None = Field(None, ge=1, le=31)
    per_slot: int = Field(2, ge=1, le=2)
    newest_first: bool = True
    auto_new: bool = True
    sources: list[str] = Field(default_factory=lambda: list(SERIES_SOURCES), min_length=1, max_length=10)
    open_time: str = Field('15:00', pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
    window_hours: int = Field(0, ge=0, le=24 * 31)      # 0 – müddətsiz
    duration_min: TestMinutes = 0
    penalty: Literal[0, 3, 4] = 0
    show_answers: Literal['after_close', 'after_submit', 'never', 'teacher'] = 'teacher'
    shuffle: bool = True
    start: dt.date | None = None                        # boş – 23.10.2026 (keçmişdə ≤ 14 gün qaldıqca), sonra bu gün

    @model_validator(mode='after')
    def _v(self):
        if self.period == 'week' and self.weekday is None:
            raise ValueError('həftənin gününü seçin')
        if self.period == 'month' and self.month_day is None:
            raise ValueError('ayın gününü seçin')
        if self.window_hours and self.duration_min > self.window_hours * 60:
            raise ValueError('həll müddəti açıq qalma müddətindən uzundur')
        if any(x not in SERIES_SOURCES for x in self.sources):
            raise ValueError('mənbə: yalnız Sınaqlar, P012, P009')
        return self


AUTO_START = dt.date(2026, 10, 23)


@router.post('/auto-all')
def auto_all(body: AutoAllIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Müəllimin bütün aktiv dərsləri (məktəb + fərdi məkan) üçün hərəyə bir seriya; aktiv seriyası olan dərs atlanır.
    dry_run (defolt) – heç nə yazmır, siyahı qaytarır. Sinfin rəqəmi bilinmirsə – seriya yaranmır (status «empty»)."""
    _check_start(body.start)
    today = now().astimezone(TZ).date()
    start = body.start or (AUTO_START if today - AUTO_START <= dt.timedelta(days=MAX_PAST_DAYS) else today)
    spaces = _spaces(db, user)
    kinds = {s.id: s.kind for s in db.scalars(select(School).where(School.id.in_(spaces)))}
    rows = db.execute(select(TeachingAssignment, SchoolClass).join(SchoolClass, SchoolClass.id == TeachingAssignment.class_id)
                      .where(TeachingAssignment.teacher_id == user.id, TeachingAssignment.archived_at.is_(None),
                             SchoolClass.archived_at.is_(None), SchoolClass.school_id.in_(spaces),
                             SchoolClass.parent_id.is_(None))
                      .order_by(SchoolClass.name, TeachingAssignment.id)).all()
    busy = {t['ta_id'] for s in db.scalars(select(ExamSeries).where(ExamSeries.created_by == user.id, ExamSeries.active.is_(True)))
            for t in s.targets}
    files = [f for f in db.scalars(_files_q(body.sources)) if f.kind == 'sinaq']
    files.sort(key=_newest_key)
    given = _given_to(db, [ta.id for ta, _ in rows])
    since = db.scalar(select(func.coalesce(func.max(BankFile.id), 0))) or 0
    t0 = now()
    out, made = [], []
    for ta, cls in rows:
        g = class_grade(db, cls)
        queue = [f for f in files if g is not None and grade_fits(f, g) and ta.id not in given.get(f.id, {})]
        status = 'exists' if ta.id in busy else ('create' if g is not None else 'empty')
        probe = ExamSeries(period=body.period, every=body.every, weekday=body.weekday, month_day=body.month_day,
                           open_time=body.open_time)
        now_n = min(len(queue), body.per_slot * len(_past_slots(probe, start, t0))) if not body.window_hours else 0
        out.append({'ta_id': ta.id, 'class_name': cls.name, 'open_now': now_n, 'space': 'private' if kinds.get(cls.school_id) == 'private' else 'school',
                    'subject': ta.subject, 'grade': g, 'queue_n': len(queue), 'first': [f.label for f in queue[:2]],
                    'status': status})
        if body.dry_run or status != 'create':
            continue
        s = ExamSeries(created_by=user.id, title=f'Avtomatik seriya – {cls.name}', subject=ta.subject, targets=[{'ta_id': ta.id}],
                       sources=list(body.sources), grade=g, period=body.period, every=body.every, weekday=body.weekday,
                       month_day=body.month_day, open_time=body.open_time, window_hours=body.window_hours,
                       duration_min=body.duration_min, penalty=body.penalty, show_answers=body.show_answers,
                       shuffle=body.shuffle, auto_new=body.auto_new, queue=[f.id for f in queue], done=[],
                       other_ok=[], since_file_id=since, per_slot=body.per_slot, newest_first=body.newest_first,
                       next_at=t0, active=True)
        s.next_at = first_slot(s, max(start, today), t0).astimezone(dt.timezone.utc)
        db.add(s)
        db.flush()
        filled = _backfill(db, s, start, t0)
        audit(db, user, 'create', 'exam_series', s.id, queue=len(s.queue), period=s.period, auto_all=True, backfilled=filled)
        made.append(s.id)
    if body.dry_run:
        return {'dry_run': True, 'items': out}
    db.commit()
    for i in made:
        run_series(db, only=i)
    return {'dry_run': False, 'items': out, 'created': made}
