"""Jurnal: gün seçilir -> həmin günün dərs saatları (hər saat ayrıca), mövzu işçi plandan avtomatik,
davamiyyət, formativ qiymət (test: düzgün sayı -> faiz -> qiymət), ev tapşırığı və yoxlanması."""
from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import staff
from ..domain.plan import slot_at
from ..domain.rules import summative_grade
from ..models import Attendance, HomeworkCheck, JournalEntry, Mark, User
from ..services import lesson_out, own_assignment, plan_ctx, roster, taught_lesson, today
from .common import audit
from .plan import WEEKDAYS, bell

router = APIRouter(prefix='/api/journal', tags=['journal'])
ATT = ('var', 'yox', 'üzrlü', 'gecikdi')
HW = ('etdi', 'qismən', 'etmədi', 'köçürüb')
SUMMATIVE = ('KSQ', 'BSQ')          # summativ dərsdə formativ qiymət qoyulmur (metodik qayda)


def _entry_payload(db: Session, e: JournalEntry | None) -> dict:
    if not e:
        return {'exists': False, 'attendance': {}, 'marks': [], 'homework_checks': {}}
    return {
        'exists': True, 'auto': bool(e.auto), 'id': e.id, 'topic': e.topic, 'homework': e.homework, 'note': e.note,
        'attendance': {a.student_id: a.status for a in db.scalars(select(Attendance).where(Attendance.entry_id == e.id))},
        'marks': [{'student_id': m.student_id, 'kind': m.kind, 'grade': m.grade, 'test_correct': m.test_correct,
                   'test_total': m.test_total, 'comment': m.comment, 'task_id': m.task_id}
                  for m in db.scalars(select(Mark).where(Mark.entry_id == e.id))],
        'homework_checks': {h.student_id: h.status
                            for h in db.scalars(select(HomeworkCheck).where(HomeworkCheck.entry_id == e.id))},
    }


def _prev_homework(db: Session, ta_id: int, d: dt.date, period: int) -> str | None:
    """Yoxlanılacaq ev tapşırığı – ƏVVƏLKİ GÜNLƏRDƏ verilən sonuncu (eyni gün 1-ci saatda verilən ev tapşırığı
    həmin gün 5-ci saatda yoxlanılmır – şagirdin evdə etməyə vaxtı olmayıb)."""
    e = db.scalar(select(JournalEntry).where(
        JournalEntry.assignment_id == ta_id, JournalEntry.homework.is_not(None), JournalEntry.date < d)
        .order_by(JournalEntry.date.desc(), JournalEntry.period.desc()))
    return e.homework if e else None


@router.get('/{ta_id}/day')
def day(ta_id: int, date: dt.date | None = None, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    ctx = plan_ctx(db, ta)
    d = date or today()
    lessons = []
    for s in (x for x in ctx.slots if x.date == d):
        e = db.scalar(select(JournalEntry).where(JournalEntry.assignment_id == ta.id, JournalEntry.date == d,
                                                 JournalEntry.period == s.period))
        lessons.append({'period': s.period, 'time': bell(db, ctx.cls, s.period), 'held': s.held, 'shift': s.shift,
                        'plan': lesson_out(taught_lesson(ctx, s, e)), 'entry': _entry_payload(db, e),
                        'homework_to_check': _prev_homework(db, ta.id, d, s.period)})
    return {'date': d, 'weekday': WEEKDAYS[d.weekday()],
            'class_name': ctx.cls.name, 'subject': ta.subject, 'lessons': lessons,
            'students': [{'id': s.id, 'full_name': s.full_name, 'portal_code': s.portal_code}
                         for s in roster(db, ta)]}


class MarkIn(BaseModel):
    student_id: int
    kind: Literal['şifahi', 'yazılı', 'test']
    grade: int | None = Field(None, ge=2, le=5)
    test_correct: int | None = Field(None, ge=0)
    test_total: int | None = Field(None, ge=1, le=100)
    comment: str | None = Field(None, max_length=300)

    @model_validator(mode='after')
    def _check(self):
        if self.kind == 'test':
            if self.test_correct is None or self.test_total is None or self.test_correct > self.test_total:
                raise ValueError('test: düzgün cavab sayı və sual sayı lazımdır (düzgün ≤ sual)')
            self.grade = summative_grade(self.test_correct / self.test_total * 100)
        elif self.grade is None:
            raise ValueError('qiymət (2–5) lazımdır')
        return self


class EntryIn(BaseModel):
    date: dt.date
    period: int = Field(ge=0, le=9)
    topic: str | None = Field(None, max_length=2000)      # boş = plandakı mövzu
    homework: str | None = Field(None, max_length=2000)
    note: str | None = Field(None, max_length=2000)
    attendance: dict[int, Literal['var', 'yox', 'üzrlü', 'gecikdi']] = Field(default_factory=dict)
    marks: list[MarkIn] = Field(default_factory=list)
    homework_checks: dict[int, Literal['etdi', 'qismən', 'etmədi', 'köçürüb']] = Field(default_factory=dict)


@router.put('/{ta_id}/entry')
def save_entry(ta_id: int, body: EntryIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Gündəlik yazı – Tənzimləmələr kilidi tələb olunmur. Göndərilən siyahılar həmin dərs üçün tam əvəzlənir."""
    ta = own_assignment(db, user, ta_id)
    ctx = plan_ctx(db, ta)
    s = slot_at(ctx.slots, body.date, body.period)
    if not s:
        raise HTTPException(400, 'Bu tarixdə və saatda dərsiniz yoxdur (bayram, tətil və ya cədvəldə yoxdur)')
    if body.date > today() + dt.timedelta(days=14):
        raise HTTPException(400, 'Gələcək dərs üçün jurnal yazıla bilməz (ev tapşırığı üçün 14 günə qədər)')
    ids = {st.id for st in roster(db, ta)}
    extra = (set(body.attendance) | {m.student_id for m in body.marks} | set(body.homework_checks)) - ids
    if extra:
        raise HTTPException(400, f'Bu şagirdlər bu sinifdə/qrupda deyil: {sorted(extra)}')
    if body.date > today() and (body.attendance or body.marks or body.homework_checks):
        raise HTTPException(400, 'Gələcək dərs üçün yalnız mövzu və ev tapşırığı yazılır (davamiyyət və qiymət – dərs günü)')
    e = db.scalar(select(JournalEntry).where(JournalEntry.assignment_id == ta.id, JournalEntry.date == body.date,
                                             JournalEntry.period == body.period))
    # onlayn mövzu testindən gələn qiymət (dəyişdirilməyibsə) mənbəyini saxlayır; onlayn test evdə yazılır –
    # şagirdin dərsdə qayıb olması bu qiymətə mane deyil
    online = {m.student_id: (m.task_id, m.test_correct, m.test_total) for m in db.scalars(select(Mark).where(
        Mark.entry_id == e.id, Mark.kind == 'test', Mark.task_id.is_not(None)))} if e else {}

    def _from_task(m: MarkIn) -> int | None:
        o = online.get(m.student_id)
        return o[0] if o and m.kind == 'test' and (m.test_correct, m.test_total) == o[1:] else None
    absent = {k for k, v in body.attendance.items() if v in ('yox', 'üzrlü')}
    if any(m.student_id in absent and not _from_task(m) for m in body.marks):
        raise HTTPException(400, 'Dərsdə olmayan şagirdə (qayıb və ya üzrlü) qiymət yazıla bilməz')
    # dərsdə olmayan şagirdin ev tapşırığı yoxlanılmır – «etmədi» kimi yazılmasın (ev tapşırığı faizini korlamasın)
    body.homework_checks = {k: v for k, v in body.homework_checks.items() if k not in absent}
    pl = taught_lesson(ctx, s, e)          # düzəliş zamanı yazılmış mövzu dəyişmir
    if pl and pl.assessment_type in SUMMATIVE and body.marks:
        raise HTTPException(400, f'{pl.assessment_type} günü formativ qiymət yazılmır – nəticələr «KSQ / BSQ» bölməsində')
    if e is None:
        e = JournalEntry(assignment_id=ta.id, date=body.date, period=body.period)
        db.add(e)
    e.plan_lesson_id = pl.id if pl else None
    e.topic = body.topic if body.topic and (not pl or body.topic.strip() != pl.topic) else None
    e.homework, e.note = body.homework, body.note
    e.auto = False                         # müəllim saxladı – dərs yazılıb
    db.flush()
    for model in (Attendance, Mark, HomeworkCheck):
        db.query(model).filter(model.entry_id == e.id).delete()
    db.add_all(Attendance(entry_id=e.id, student_id=k, status=v) for k, v in body.attendance.items())
    db.add_all(Mark(entry_id=e.id, task_id=_from_task(m), **m.model_dump()) for m in body.marks)
    db.add_all(HomeworkCheck(entry_id=e.id, student_id=k, status=v) for k, v in body.homework_checks.items())
    audit(db, user, 'update', 'journal', e.id, date=str(body.date), period=body.period)
    db.commit()
    return {'id': e.id, **_entry_payload(db, e)}


CELL_ATT = {'yox': 'q', 'üzrlü': 'ü', 'gecikdi': 'g'}


@router.get('/{ta_id}/grid')
def grid(ta_id: int, month: str | None = None, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Klassik jurnal səhifəsi (ay üzrə): sətir – şagird, sütun – dərs (tarix, saat). Xanada: formativ qiymətlər,
    «q» qayıb / «ü» üzrlü / «g» gecikmə, həmin gün keçirilən KSQ/BSQ qiyməti. İkinci hissə – mövzu və ev tapşırığı."""
    from ..domain.rules import grade_from_points
    from ..models import Exam, ExamScore
    from .exams_online import exam_stats
    from ..services import journal_entries, taught_lesson
    ta = own_assignment(db, user, ta_id)
    ctx = plan_ctx(db, ta)
    try:
        y, m = map(int, (month or today().strftime('%Y-%m')).split('-'))
        a = dt.date(y, m, 1)
    except ValueError:
        raise HTTPException(400, 'ay: YYYY-MM')
    b = (a.replace(year=a.year + 1, month=1) if a.month == 12 else a.replace(month=a.month + 1)) - dt.timedelta(days=1)
    entries = journal_entries(db, ta.id, a, b)
    keys = sorted({(s.date, s.period) for s in ctx.slots if a <= s.date <= b} | set(entries))
    slots = {(s.date, s.period): s for s in ctx.slots}
    eids = [e.id for e in entries.values()]
    att = {(x.entry_id, x.student_id): x.status for x in db.scalars(select(Attendance).where(Attendance.entry_id.in_(eids)))}
    mk: dict = {}
    for x in db.scalars(select(Mark).where(Mark.entry_id.in_(eids))):
        mk.setdefault((x.entry_id, x.student_id), []).append(x.grade)
    exams = list(db.scalars(select(Exam).where(Exam.assignment_id == ta.id, Exam.date >= a, Exam.date <= b)))
    ex_first = {}
    for k in keys:                                     # KSQ/BSQ qiyməti həmin günün ilk dərs sütununa
        ex_first.setdefault(k[0], k)
    ex_cell: dict = {}
    for ex in exams:
        col = ex_first.get(ex.date)
        for sc in db.scalars(select(ExamScore).where(ExamScore.exam_id == ex.id)):
            if col and sc.points is not None and not sc.absent:
                ex_cell[(col, sc.student_id)] = f'{ex.kind}-{ex.no}: {grade_from_points(sc.points, ex.max_points)}'
    from .exams_online import class_exams
    exs = class_exams(db, ta, a, b)                    # sınaq – keçirildiyi günün ayrıca sütunu (ortaya daxil deyil)
    order = sorted([(k[0], 0, k[1], k) for k in keys] + [(x['date'], 1, i, x) for i, x in enumerate(exs)],
                   key=lambda z: z[:3])
    cols = []
    for d_, is_ex, _, k in order:
        if is_ex:
            cols.append({'date': d_, 'period': None, 'written': False, 'topic': k['title'], 'seq': None,
                         'assessment': None, 'homework': None, 'future': d_ > today(), 'sinaq': k['title']})
            continue
        e = entries.get(k)
        pl = taught_lesson(ctx, slots.get(k), e)
        cols.append({'date': k[0], 'period': k[1], 'written': e is not None and not e.auto,'topic': (e.topic if e and e.topic else pl.topic if pl else None),
                     'seq': pl.seq if pl else None, 'assessment': (f"{pl.assessment_type}-{pl.exam_no}" if pl and pl.exam_no else
                                                                  pl.assessment_type if pl and pl.assessment_type != 'formativ' else None),
                     'homework': e.homework if e else None, 'future': k[0] > today()})
    rows = []
    for s in roster(db, ta):
        cells = []
        for _, is_ex, _, k in order:
            if is_ex:
                r = k['rows'].get(s.id)
                cells.append({'marks': [], 'att': None, 'exam': None,
                              'sinaq': (f"{r['pct']:g}%" if r['status'] == 'yazıb' else 'yox' if k['closed'] else None)
                              if r else None})
                continue
            e = entries.get(k)
            c = {'marks': [], 'att': None, 'exam': ex_cell.get((k, s.id))}
            if e:
                c['marks'] = mk.get((e.id, s.id), [])
                c['att'] = CELL_ATT.get(att.get((e.id, s.id)))
            cells.append(c)
        g = [x for c in cells for x in c['marks']]
        rows.append({'student_id': s.id, 'full_name': s.full_name, 'cells': cells, **exam_stats(exs, s.id),
                     'avg': round(sum(g) / len(g), 2) if g else None, 'missed': sum(c['att'] in ('q', 'ü') for c in cells)})
    return {'month': f'{a:%Y-%m}', 'from': a, 'to': b, 'class_name': ctx.cls.name, 'subject': ta.subject,
            'year_start': ctx.year.start, 'year_end': ctx.year.end, 'columns': cols, 'rows': rows, 'exams': len(exs)}


@router.get('/{ta_id}/summary')
def summary(ta_id: int, semester: int | None = None, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Şagird üzrə: formativ orta, davamiyyət %, ev tapşırığı icrası %, testlər; sınaqlar – ayrıca (ortaya daxil deyil)."""
    from .exams_online import class_exams, exam_stats
    ta = own_assignment(db, user, ta_id)
    ctx = plan_ctx(db, ta)
    exs = class_exams(db, ta, ctx.year.sem2_start if semester == 2 else None, ctx.year.sem1_end if semester == 1 else None)
    st = select(JournalEntry.id).where(JournalEntry.assignment_id == ta.id)
    if semester == 1:
        st = st.where(JournalEntry.date <= ctx.year.sem1_end)
    elif semester == 2:
        st = st.where(JournalEntry.date >= ctx.year.sem2_start)
    eids = list(db.scalars(st))
    marks = list(db.scalars(select(Mark).where(Mark.entry_id.in_(eids))))
    att = list(db.scalars(select(Attendance).where(Attendance.entry_id.in_(eids))))
    hw = list(db.scalars(select(HomeworkCheck).where(HomeworkCheck.entry_id.in_(eids))))
    hw_w = {'etdi': 1.0, 'qismən': 0.5, 'etmədi': 0.0, 'köçürüb': 0.0}
    out = []
    for s in roster(db, ta):
        g = [m.grade for m in marks if m.student_id == s.id]
        t = [m for m in marks if m.student_id == s.id and m.kind == 'test']
        a = [x.status for x in att if x.student_id == s.id]
        h = [hw_w[x.status] for x in hw if x.student_id == s.id]
        out.append({'student_id': s.id, 'full_name': s.full_name,
                    'avg_grade': round(sum(g) / len(g), 2) if g else None, 'marks': len(g),
                    'tests': len(t), 'test_pct': round(sum(m.test_correct for m in t) * 100 / sum(m.test_total for m in t), 1) if t else None,
                    'lessons': len(a), 'absent': a.count('yox') + a.count('üzrlü'), 'late': a.count('gecikdi'),
                    'attendance_pct': round((len(a) - a.count('yox') - a.count('üzrlü')) * 100 / len(a), 1) if a else None,
                    'homework_pct': round(sum(h) * 100 / len(h), 1) if h else None, **exam_stats(exs, s.id)})
    written = db.scalar(select(func.count()).select_from(JournalEntry).where(JournalEntry.id.in_(eids), JournalEntry.auto.is_(False))) if eids else 0
    return {'lessons_written': written, 'students': out, 'exams': len(exs)}
