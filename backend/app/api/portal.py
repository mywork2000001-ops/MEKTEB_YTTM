"""Şagird portalı – şagird YALNIZ özünə aid məlumatı görür; sinif ortası adsızdır.
Bu gün (motivasiya, imtahan sayğacı, müəllimlər) · Dərs (gündəlik) · Plan · Tapşırıqlar (vaxtlı) · Nəticələrim · Analitika."""
from __future__ import annotations

import datetime as dt
import random
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..bank_labels import label_ml
from ..db import get_db
from ..deps import require
from ..domain.plan import view_range
from ..domain.rules import grade_from_points, semester_grade, year_grade
from ..models import (Attendance, Exam, ExamAppeal, ExamScore, GroupMember, HomeworkCheck, JournalEntry, Mark, OnlineTask, PlanLesson,
                      Role, SchoolClass, Student, TaskAttempt, TeachingAssignment, User, now)
from ..services import SCHOOL_TZ, journal_entries, plan_ctx, roster, taught_lesson, today
from .plan import WEEKDAYS, bell
from ..exam_cards import published_for
from .tasks import apct, attempt_pct, aware, expire_due, finalize, is_ok, review_opens_at

router = APIRouter(prefix='/api/portal', tags=['portal'])
SUBMIT_GRACE = dt.timedelta(seconds=10)     # vaxt bitən anda göndərilən son cavablar üçün (şəbəkə gecikməsi)
student_only = require(Role.student)

MOTIVATION = [
    'Hər gün bir az irəli – ilin sonunda böyük yol.', 'Səhv etmək öyrənməyin bir hissəsidir.',
    'Bu gün həll etdiyin hər misal sabahkı imtahanda sənə kömək edəcək.', 'Diqqət + ardıcıllıq = uğur.',
    'Çətin sual – yeni bir şey öyrənmək fürsətidir.', 'Özünü dünənki özünlə müqayisə et.',
    'Kiçik addımlar da addımdır.', 'Riyaziyyat səbir sevir: tələsmə, yoxla.',
    'Sualı iki dəfə oxu – cavabın yarısı sualdadır.', 'Bilik paylaşdıqca artır – yoldaşına kömək et.',
    'Bu gün 20 dəqiqə təkrar – sabah daha asan dərs.', 'Uğur hər gün təkrarlanan kiçik səylərin cəmidir.',
    'İnanırsansa, yarısını artıq etmisən.', 'Dəftərin səliqəli olsa, fikrin də səliqəli olar.',
    'Hər test sənə nəyi bilmədiyini göstərir – bu da qazancdır.', 'Sual vermək ayıb deyil, bilməmək qalmaq ayıbdır.',
    'Başlamaq üçün mükəmməl olmaq lazım deyil, mükəmməl olmaq üçün başlamaq lazımdır.',
    'Bugünkü zəhmət – sabahkı özgüvəndir.', 'Yorulanda dayan, amma dayanıb qalma.', 'Hədəfini yaz, hər gün ona bax.',
]


def _L(user: User | None, az: str, ru: str, en: str) -> str:
    """Şagirdə görünən server mesajı istifadəçinin dilində (rus dili promtu)."""
    return {'ru': ru, 'en': en}.get(getattr(user, 'language', None), az)


def me_student(db: Session, user: User) -> Student:
    s = db.scalar(select(Student).where(Student.user_id == user.id, Student.archived_at.is_(None)))
    if not s:
        raise HTTPException(404, _L(user, 'Şagird qeydi tapılmadı', 'Запись ученика не найдена', 'Student record not found'))
    return s


def my_assignments(db: Session, s: Student) -> list[tuple[TeachingAssignment, SchoolClass]]:
    group_ids = set(db.scalars(select(GroupMember.group_id).where(GroupMember.student_id == s.id)))
    return list(db.execute(select(TeachingAssignment, SchoolClass).join(SchoolClass).where(
        TeachingAssignment.archived_at.is_(None), SchoolClass.archived_at.is_(None),
        SchoolClass.id.in_(group_ids | {s.class_id}))).all())


def _teacher(db: Session, ta: TeachingAssignment) -> str:
    return db.get(User, ta.teacher_id).full_name


@router.get('/me')
def me(user: User = Depends(student_only), db: Session = Depends(get_db)):
    s = me_student(db, user)
    c = db.get(SchoolClass, s.class_id)
    tas = my_assignments(db, s)
    d = today()
    motivation = MOTIVATION[d.toordinal() % len(MOTIVATION)]
    personal = None
    last = db.scalar(select(TaskAttempt).where(TaskAttempt.student_id == s.id, TaskAttempt.submitted_at.is_not(None))
                     .order_by(TaskAttempt.submitted_at.desc()))
    if last and last.total:
        pct = round(apct(last))
        tier = 2 if pct >= 81 else 1 if pct >= 61 else 0
        personal = _L(user, f'Son tapşırıqda nəticən {pct}% oldu – ', f'Результат в последнем задании — {pct}% — ', f'Your result in the last task was {pct}% – ') + (
            _L(user, 'səhvlərinə bax, növbəti dəfə daha yaxşı olacaq.', 'посмотри на свои ошибки — в следующий раз получится лучше.', 'look at your mistakes – next time will be better.'),
            _L(user, 'yaxşıdır, bir az da səy!', 'хорошо, ещё немного усилий!', 'good, a little more effort!'),
            _L(user, 'əla, belə davam et!', 'отлично, так держать!', 'excellent, keep it up!'))[tier]
    exam = c.exam_date
    return {'full_name': s.full_name, 'portal_code': s.portal_code, 'class_name': c.name,
            'teachers': sorted({(_teacher(db, ta), ta.subject) for ta, _ in tas}),
            'exam_date': exam, 'days_to_exam': (exam - d).days if exam and exam >= d else None,
            'motivation': motivation, 'personal': personal, 'language': user.language, 'theme': user.theme}


def _plan_fields(pl, sl, e) -> dict:
    """Perspektiv plandan şagirdə lazım olanlar: bölmə, KSQ/BSQ nömrəsi, dərslik səhifələri, rəsmi tarix."""
    return {'topic': e.topic if e is not None and e.topic else pl.topic if pl else None,
            'plan_topic': pl.topic if pl else None, 'section': pl.section if pl else None,
            'assessment_type': pl.assessment_type if pl else None, 'exam_no': pl.exam_no if pl else None,
            'tt_pages': pl.tt_pages if pl else None, 'official_date': pl.date if pl else None,
            'plan_seq': pl.seq if pl else None, 'held': bool(sl and sl.held), 'shift': sl.shift if sl else 0,
            'taught': e is not None, 'off_schedule': sl is None}


def _slots_with_entries(ctx, a: dt.date, b: dt.date, entries: dict) -> list:
    """Cədvəl yuvaları + cədvəldən kənar qalmış jurnal yazıları (cədvəl sonradan dəyişibsə, itməsin)."""
    items = [(x.date, x.period, x) for x in ctx.slots if a <= x.date <= b]
    have = {(d, p) for d, p, _ in items}
    items += [(d, p, None) for (d, p) in entries if (d, p) not in have]
    return sorted(items, key=lambda x: (x[0], x[1]))


def _lesson_start(d: dt.date, time: str | None) -> dt.datetime:
    """Dərsin başlama anı (zəng «08:30-09:15» – birinci vaxt); zəng yoxdursa – 08:00, məktəb vaxtı."""
    import re
    from zoneinfo import ZoneInfo
    m = re.search(r'(\d{1,2}):(\d{2})', time or '')
    h, mi = (int(m.group(1)), int(m.group(2))) if m else (8, 0)
    return dt.datetime(d.year, d.month, d.day, h, mi, tzinfo=ZoneInfo(SCHOOL_TZ))


def _p0010(db: Session, c: SchoolClass, pairs: list[tuple[dict, PlanLesson | None]]) -> None:
    """X–XI: dərsin P0010 testi şagirdə yalnız dərsin tarixi və saatı çatanda açılır (o vaxta qədər – p0010_opens_at)."""
    from .plan import attach_p0010
    ls = {pl.id: {'id': pl.id, 'topic': pl.topic, 'section': pl.section, 'assessment_type': pl.assessment_type}
          for _, pl in pairs if pl is not None}
    attach_p0010(db, c, list(ls.values()))
    at = now()
    for item, pl in pairs:
        x = ls.get(pl.id).get('p0010') if pl is not None else None
        if not x:
            continue
        start = _lesson_start(item['date'], item.get('time'))
        if at >= start:
            item['p0010'] = {'label': x['label'], 'url': x['url']}
        else:
            item['p0010_opens_at'] = start


@router.get('/day')
def day(date: dt.date | None = None, user: User = Depends(student_only), db: Session = Depends(get_db)):
    s = me_student(db, user)
    d = date or today()
    lessons, pairs = [], []
    for ta, c in my_assignments(db, s):
        ctx = plan_ctx(db, ta)
        entries = journal_entries(db, ta.id, d, d)
        for _, period, sl in _slots_with_entries(ctx, d, d, entries):
            e = entries.get((d, period))
            pl = taught_lesson(ctx, sl, e)
            item = {'date': d, 'period': period, 'time': bell(db, c, period, ta, d), 'subject': ta.subject, 'class_name': c.name,
                    'teacher': _teacher(db, ta), **_plan_fields(pl, sl, e), 'homework': e.homework if e else None,
                    'attendance': None, 'marks': [], 'homework_check': None}
            if e:
                a = db.get(Attendance, (e.id, s.id))
                item['attendance'] = a.status if a else None
                item['marks'] = [{'kind': m.kind, 'grade': m.grade, 'test_correct': m.test_correct,
                                  'test_total': m.test_total, 'comment': m.comment} for m in   # müəllimin rəyi
                                 db.scalars(select(Mark).where(Mark.entry_id == e.id, Mark.student_id == s.id))]
                h = db.get(HomeworkCheck, (e.id, s.id))
                item['homework_check'] = h.status if h else None
            lessons.append(item)
            pairs.append((item, pl))
        _p0010(db, c, pairs)
        pairs = []
    lessons.sort(key=lambda x: (x['time'] or '', x['period']))
    return {'date': d, 'weekday': WEEKDAYS[d.weekday()], 'lessons': lessons}


@router.get('/plan')
def plan(view: str = 'week', date: dt.date | None = None, user: User = Depends(student_only),
         db: Session = Depends(get_db)):
    s = me_student(db, user)
    d = date or today()
    items, rng = [], (d, d)
    for ta, c in my_assignments(db, s):
        pairs: list = []
        ctx = plan_ctx(db, ta)
        try:
            a, b = view_range(view, d, ctx.year.sem1_end, ctx.year.sem2_start, ctx.year.start, ctx.year.end,
                              weekend=any(k in ('5', '6') for k in (ta.slots or {})))
            rng = (a, b)
        except ValueError:
            raise HTTPException(400, _L(user, 'görünüş: day, week, month, semester', 'вид: day, week, month, semester', 'view: day, week, month, semester'))
        entries = journal_entries(db, ta.id, a, b)
        for d_, period, sl in _slots_with_entries(ctx, a, b, entries):
            e = entries.get((d_, period))
            pl = taught_lesson(ctx, sl, e)
            items.append({'date': d_, 'weekday': WEEKDAYS[d_.weekday()], 'period': period,
                          'time': bell(db, c, period, ta, d_), 'subject': ta.subject, 'class_name': c.name,
                          'group': c.kind == 'qrup',
                          **_plan_fields(pl, sl, e), 'homework': e.homework if e else None})
            pairs.append((items[-1], pl))
        _p0010(db, c, pairs)
    items.sort(key=lambda x: (x['date'], x['time'] or '', x['period']))
    return {'view': view, 'from': rng[0], 'to': rng[1], 'items': items}


@router.get('/progress')
def progress(user: User = Depends(student_only), db: Session = Depends(get_db)):
    """Fənlər üzrə keçilən mövzular: keçilib / cəmi, plana nisbətən fərq, təkrar tövsiyə olunan və növbəti mövzular.
    Müəllimin qeydi (note) şagirdə göstərilmir."""
    from ..progress import DONE, topic_progress
    s = me_student(db, user)
    t = today()
    out = []
    for ta, c in my_assignments(db, s):
        p = topic_progress(db, plan_ctx(db, ta), t)
        if not p['topics']:
            continue
        tp = p['topics']
        out.append({'ta_id': ta.id, 'subject': ta.subject, 'class_name': c.name, 'group': c.kind == 'qrup',
                    'teacher': _teacher(db, ta),
                    **{k: p['summary'][k] for k in ('total', 'done', 'expected', 'delta', 'done_pct', 'plan_pct')},
                    'review': [{'seq': x['seq'], 'topic': x['topic']} for x in tp if x['status'] == 'təkrar'][-5:],
                    'recent': [{'seq': x['seq'], 'topic': x['topic'], 'done_on': x['done_on']}
                               for x in sorted((x for x in tp if x['status'] in DONE and x['done_on']),
                                               key=lambda x: (x['done_on'], x['seq']))][-5:][::-1],
                    'next': [{'seq': x['seq'], 'topic': x['topic'], 'assessment_type': x['assessment_type'],
                              'exam_no': x['exam_no']} for x in tp if x['status'] not in DONE][:3],
                    'sections': [{k: x[k] for k in ('section', 'total', 'done')} for x in p['sections']]})
    return out


UPCOMING_DAYS = 21          # summativdən 3 həftə əvvəl şagird təkrara başlasın


@router.get('/upcoming')
def upcoming(user: User = Depends(student_only), db: Session = Depends(get_db)):
    """Hazırlıq: 1) yaxınlaşan KSQ/BSQ (işçi plana görə tarix) və əhatə etdiyi mövzular + standartlar
    (əvvəlki summativdən bu yana); 2) hər fənn üzrə növbəti dərs və ona verilən ev tapşırığı."""
    s = me_student(db, user)
    d = today()
    exams, homework = [], []
    for ta, c in my_assignments(db, s):
        ctx = plan_ctx(db, ta)
        # növbəti summativ
        nxt = next((sl for sl in ctx.slots if sl.date >= d and sl.index is not None
                    and ctx.lessons[sl.index].assessment_type in ('KSQ', 'BSQ')), None)
        if nxt and (nxt.date - d).days <= UPCOMING_DAYS and ta.has_summative:
            pl = ctx.lessons[nxt.index]
            prev = max((i for i in range(nxt.index) if ctx.lessons[i].assessment_type in ('KSQ', 'BSQ')), default=-1)
            topics = [x for x in ctx.lessons[prev + 1:nxt.index] if x.assessment_type not in ('KSQ', 'BSQ')]
            if pl.assessment_type == 'BSQ':            # BSQ bütün yarımili əhatə edir
                topics = [x for x in ctx.lessons[:nxt.index] if x.semester == pl.semester
                          and x.assessment_type not in ('KSQ', 'BSQ')]
            exams.append({'subject': ta.subject, 'class_name': c.name, 'kind': pl.assessment_type, 'no': pl.exam_no,
                          'date': nxt.date, 'days': (nxt.date - d).days, 'title': pl.topic,
                          'topics': [{'seq': x.seq, 'topic': x.topic, 'tt_pages': x.tt_pages} for x in topics],
                          'standards': sorted({st for x in topics for st in (x.standards or [])},
                                              key=lambda v: [int(p) if p.isdigit() else p for p in v.split('.')])})
        # növbəti dərsə ev tapşırığı – SON dərs gününün bütün saatlarında verilənlər (gündə 2 dərs olanda
        # 1-ci saatda verilib, 5-ci saatda verilməyə bilər); son dərs günü ev tapşırığı yoxdursa – heç nə
        after = next((sl for sl in ctx.slots if sl.date > d), None)
        last_day = db.scalar(select(JournalEntry.date).where(JournalEntry.assignment_id == ta.id, JournalEntry.date <= d)
                             .order_by(JournalEntry.date.desc()))
        hws = [e.homework for e in db.scalars(select(JournalEntry).where(
            JournalEntry.assignment_id == ta.id, JournalEntry.date == last_day, JournalEntry.homework.is_not(None))
            .order_by(JournalEntry.period))] if last_day else []
        if hws and after:
            homework.append({'subject': ta.subject, 'class_name': c.name, 'homework': '; '.join(dict.fromkeys(hws)),
                             'given': last_day, 'due': after.date, 'due_period': after.period,
                             'due_time': bell(db, c, after.period, ta, after.date)})
    exams.sort(key=lambda x: x['date'])
    homework.sort(key=lambda x: (x['due'], x['due_time'] or ''))
    return {'today': d, 'exams': exams, 'homework': homework}


# ---------------------------------------------------------------- tapşırıqlar
def _my_tasks(db: Session, s: Student) -> list[OnlineTask]:
    ids = [ta.id for ta, _ in my_assignments(db, s)]
    return [t for t in db.scalars(select(OnlineTask).where(OnlineTask.assignment_id.in_(ids),
                                                          OnlineTask.archived_at.is_(None)).order_by(OnlineTask.opens_at))
            if t.student_ids is None or s.id in t.student_ids]


def _status(t: OnlineTask, a: TaskAttempt | None, at: dt.datetime) -> str:
    if a and a.submitted_at:
        return 'təhvil verilib'
    if at < aware(t.opens_at):
        return 'gözlənilir'
    if a and at < aware(a.deadline):
        return 'həll edilir'
    if at >= aware(t.closes_at):
        return 'buraxılıb'
    return 'açıq'


def _can_review(db: Session, t: OnlineTask, a: TaskAttempt | None, at: dt.datetime) -> bool:
    if not a or not a.submitted_at or t.show_answers == 'never':
        return False
    return t.show_answers == 'after_submit' or at >= review_opens_at(db, t)


def _shown_grade(t: OnlineTask, a: TaskAttempt) -> int | None:
    return None if t.kind in ('sinaq', 'ksq') else a.grade   # sınaq formativ qiymətə təsir etmir; KSQ – nəticəni müəllim açır


@router.get('/tasks')
def tasks(user: User = Depends(student_only), db: Session = Depends(get_db)):
    s = me_student(db, user)
    at = now()
    out = []
    for t in _my_tasks(db, s):
        expire_due(db, t)
        a = db.scalar(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.student_id == s.id))
        ta = db.get(TeachingAssignment, t.assignment_id)
        pl = db.get(PlanLesson, t.plan_lesson_id) if t.kind == 'movzu' and t.plan_lesson_id else None
        out.append({'id': t.id, 'title': t.title, 'description': t.description, 'subject': ta.subject,
                    'teacher': _teacher(db, ta), 'opens_at': aware(t.opens_at), 'closes_at': aware(t.closes_at),
                    'duration_min': t.duration_min, 'questions': len(t.questions), 'status': _status(t, a, at),
                    'deadline': aware(a.deadline) if a else None,
                    'result': {'correct': a.correct, 'total': a.total, 'grade': _shown_grade(t, a),
                               'pct': attempt_pct(db, t, a)} if a and a.submitted_at and t.kind != 'ksq' else None,
                    'can_review': _can_review(db, t, a, at), 'kind': t.kind,
                    'solution_at': a.solution_at if a and a.solution_key else None,
                    'topic_seq': pl.seq if pl else None, 'topic': pl.topic if pl else None})
    return out


def _task_for(db: Session, s: Student, task_id: int, user: User | None = None) -> OnlineTask:
    t = next((x for x in _my_tasks(db, s) if x.id == task_id), None)
    if not t:
        raise HTTPException(404, _L(user, 'Tapşırıq tapılmadı', 'Задание не найдено', 'Task not found'))
    return t


def _public_q(q: dict, i: int) -> dict:
    """Şagirdə düzgün cavab və izah GÖNDƏRİLMİR."""
    return {'index': i, 'kind': q['kind'], 'text': q['text'], 'options': q.get('options'), 'image': q.get('image'),
            'points': q.get('points')}                    # 100 ballıq sistem – sualın balı (köhnə testdə yoxdur)


@router.post('/tasks/{task_id}/start')
def start(task_id: int, user: User = Depends(student_only), db: Session = Depends(get_db)):
    s = me_student(db, user)
    t = _task_for(db, s, task_id, user)
    at = now()
    a = db.scalar(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.student_id == s.id))
    if a is None:
        if at < aware(t.opens_at):
            raise HTTPException(409, _L(user, 'Tapşırıq hələ açılmayıb', 'Задание ещё не открыто', 'The task is not open yet'))
        if at >= aware(t.closes_at):
            raise HTTPException(409, _L(user, 'Tapşırığın vaxtı bitib', 'Время на выполнение задания истекло', 'The time for the task has ended'))
        order = list(range(len(t.questions)))
        if t.shuffle:
            random.Random(f'{t.id}:{s.id}').shuffle(order)
        a = TaskAttempt(task_id=t.id, student_id=s.id, started_at=at, order=order, answers={},
                        deadline=min(at + dt.timedelta(minutes=t.duration_min), aware(t.closes_at)))
        db.add(a)
        try:
            db.commit()
        except IntegrityError:                               # eyni anda iki «Başla» (iki klik / cihaz) – eyni cəhd
            db.rollback()
            a = db.scalar(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.student_id == s.id))
    elif not a.submitted_at and at >= aware(a.deadline):
        finalize(db, t, a, at, auto=True)
        db.commit()
    if a.submitted_at:
        raise HTTPException(409, _L(user, 'Tapşırıq artıq təhvil verilib', 'Задание уже сдано', 'The task has already been submitted'))
    return {'task_id': t.id, 'title': t.title, 'deadline': aware(a.deadline), 'server_time': at,
            'answers': a.answers, 'questions': [_public_q(t.questions[i], i) for i in a.order]}


class AnswersIn(BaseModel):
    # açıq cavab ≤ 500 simvol, ≤ 100 sual – bazaya böyük mətn yazılmasın
    answers: dict[Annotated[str, StringConstraints(max_length=4)],
                  int | Annotated[str, StringConstraints(max_length=500)] | None] = Field(max_length=100)


def _open_attempt(db: Session, s: Student, t: OnlineTask, user: User | None = None) -> TaskAttempt:
    a = db.scalar(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.student_id == s.id))
    if not a:
        raise HTTPException(409, _L(user, 'Tapşırığa başlanmayıb', 'Вы ещё не начали это задание', 'The task has not been started'))
    if a.submitted_at:
        raise HTTPException(409, _L(user, 'Tapşırıq artıq təhvil verilib', 'Задание уже сдано', 'The task has already been submitted'))
    return a


@router.put('/tasks/{task_id}/answers')
def save_answers(task_id: int, body: AnswersIn, user: User = Depends(student_only), db: Session = Depends(get_db)):
    """Avtomatik yadda saxlama. Müddət bitibsə – serverdə avtomatik təhvil (sonrakı cavablar qəbul edilmir)."""
    s = me_student(db, user)
    t = _task_for(db, s, task_id, user)
    a = _open_attempt(db, s, t, user)
    at = now()
    if at >= aware(a.deadline):
        finalize(db, t, a, at, auto=True)
        db.commit()
        raise HTTPException(409, _L(user, 'Vaxt bitdi – cavablar avtomatik təhvil verildi', 'Время вышло – ответы сданы автоматически', 'Time is up – your answers were submitted automatically'))
    n = len(t.questions)
    clean = {k: v for k, v in body.answers.items() if k.isdigit() and int(k) < n}
    a.answers = {**(a.answers or {}), **clean}
    db.commit()
    return {'saved': len(clean), 'deadline': aware(a.deadline), 'server_time': at}


@router.post('/tasks/{task_id}/submit')
def submit(task_id: int, body: AnswersIn | None = None, user: User = Depends(student_only),
           db: Session = Depends(get_db)):
    s = me_student(db, user)
    t = _task_for(db, s, task_id, user)
    a = _open_attempt(db, s, t, user)
    at = now()
    late = at >= aware(a.deadline)
    if body and at < aware(a.deadline) + SUBMIT_GRACE:
        n = len(t.questions)
        a.answers = {**(a.answers or {}), **{k: v for k, v in body.answers.items() if k.isdigit() and int(k) < n}}
    finalize(db, t, a, at, auto=late)
    from ..certificates import for_attempt
    cert = for_attempt(db, t, a)                             # mövzu testi ≥ hədd – sertifikat dərhal
    db.commit()
    if t.kind == 'ksq':                                      # KSQ/BSQ: bal jurnala yazıldı, şagirdə müəllim açanda görünür
        return {'ksq': True, 'correct': None, 'total': None, 'grade': None, 'pct': None, 'points': None,
                'auto_submitted': a.auto_submitted, 'can_review': False, 'certificate': None}
    return {'correct': a.correct, 'total': a.total, 'grade': _shown_grade(t, a), 'auto_submitted': a.auto_submitted,
            'can_review': _can_review(db, t, a, at), 'pct': attempt_pct(db, t, a), 'points': attempt_pct(db, t, a),
            'certificate': {'code': cert.code, 'title': cert.title} if cert else None}


@router.get('/tasks/{task_id}/review')
def review(task_id: int, user: User = Depends(student_only), db: Session = Depends(get_db)):
    s = me_student(db, user)
    t = _task_for(db, s, task_id, user)
    a = db.scalar(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.student_id == s.id))
    if not _can_review(db, t, a, now()):
        raise HTTPException(403, _L(user, 'Cavablar hələ açılmayıb', 'Ответы ещё не открыты', 'Answers are not open yet') if a and a.submitted_at else _L(user, 'Tapşırıq təhvil verilməyib', 'Задание не сдано', 'The task has not been submitted'))
    out = []
    for i in a.order:
        q = t.questions[i]
        given = (a.answers or {}).get(str(i))
        out.append({**_public_q(q, i), 'given': given, 'ok': is_ok(t, a, i), 'correct': q.get('correct'),
                    'answer': q.get('answer'), 'explanation': q.get('explanation')})
    return {'title': t.title, 'correct': a.correct, 'total': a.total, 'grade': _shown_grade(t, a), 'questions': out}


# ---------------------------------------------------------------- nəticələr və analitika
def _entries(db: Session, ta_id: int, a: dt.date | None = None, b: dt.date | None = None) -> list[int]:
    st = select(JournalEntry.id).where(JournalEntry.assignment_id == ta_id)
    if a:
        st = st.where(JournalEntry.date >= a)
    if b:
        st = st.where(JournalEntry.date <= b)
    return list(db.scalars(st))


def _stats(db: Session, eids: list[int], sid: int) -> dict:
    marks = [m.grade for m in db.scalars(select(Mark).where(Mark.entry_id.in_(eids), Mark.student_id == sid))]
    att = [x.status for x in db.scalars(select(Attendance).where(Attendance.entry_id.in_(eids), Attendance.student_id == sid))]
    w = {'etdi': 1, 'qismən': .5, 'etmədi': 0, 'köçürüb': 0}
    hw = [w[x.status] for x in db.scalars(select(HomeworkCheck).where(HomeworkCheck.entry_id.in_(eids),
                                                                       HomeworkCheck.student_id == sid))]
    miss = sum(x in ('yox', 'üzrlü') for x in att)
    return {'avg_grade': round(sum(marks) / len(marks), 2) if marks else None, 'marks': len(marks),
            'attendance_pct': round((len(att) - miss) * 100 / len(att), 1) if att else None,
            'homework_pct': round(sum(hw) * 100 / len(hw), 1) if hw else None}


@router.get('/exams')
def my_exams(user: User = Depends(student_only), db: Session = Depends(get_db)):
    """Sınaq imtahanlarım: bal, sinifdə və ümumi yerim, orta / ən yüksək bal, dinamika."""
    from .exams_online import student_exams
    s = me_student(db, user)
    items = student_exams(db, s, [t.id for t in _my_tasks(db, s)])
    got = [x for x in items if x.get('pct') is not None]
    db.commit()
    return {'items': items[::-1], 'trend': [{'title': x['title'], 'pct': x['pct'], 'avg_pct': x['avg_pct']} for x in got],
            'delta': round(got[-1]['pct'] - got[-2]['pct'], 1) if len(got) >= 2 else None}


@router.get('/topic-rating')
def topic_rating(user: User = Depends(student_only), db: Session = Depends(get_db)):
    """Mövzu testləri üzrə öz yerim (fənn üzrə, sinifdə): orta, son, dinamika, sinif ortası – başqasının adı yoxdur."""
    from ..test_stats import collect, rating
    s = me_student(db, user)
    out = []
    for ta, cls in my_assignments(db, s):
        rt = rating(collect(db, None, 'movzu', {ta.id}))
        me = next((r for r in rt['rows'] if r['student_id'] == s.id), None)
        if not me or not me['given'] and not me['wrote']:
            continue
        ranked = [r for r in rt['rows'] if r['avg_pct'] is not None]
        out.append({'subject': ta.subject, 'class_name': cls.name, 'tests': len(rt['tests']),
                    **{k: me[k] for k in ('avg_pct', 'last_pct', 'delta', 'given', 'wrote', 'missed', 'place_class')},
                    'class_count': len(ranked),
                    'class_avg': round(sum(r['avg_pct'] for r in ranked) / len(ranked), 1) if ranked else None})
    db.commit()
    return out


@router.get('/my/report')
def my_report(date_from: dt.date | None = None, date_to: dt.date | None = None, user: User = Depends(student_only),
              db: Session = Depends(get_db)):
    """Fərdi hesabatım: onlayn + kağız nəticələr, adı ilə sınaqlar, KSQ/BSQ. Yalnız nəşr olunmuş; sinif ortası – ≥5 nəticə olanda."""
    from ..student_report import my_results
    rep = my_results(db, me_student(db, user), date_from, date_to)
    db.commit()
    return rep


def _card(db: Session, e: Exam, sid: int) -> dict | None:
    """Şagirdin öz cavab kartı (docs/kart-skanlarini-silme-promtu.md): kartın şəkli, oxunuş, nəşrdən sonra düz cavab / ✓✗ / bal.
    Məntiq app/exam_cards.py-dadır (paket də eyni funksiyanı işlədir)."""
    from ..exam_cards import published_for, scan_info
    return scan_info(db, e, sid, published_for(db, e, sid))


@router.get('/exam-card/{scan_id}/image')
def card_image(scan_id: int, user: User = Depends(student_only), db: Session = Depends(get_db)):
    """Şagirdin ÖZ kartının şəkli (başqasınınkı – 404)."""
    from fastapi.responses import StreamingResponse
    from ..models import ExamScan
    from ..storage import storage_for_key
    s = me_student(db, user)
    sc = db.get(ExamScan, scan_id)
    if sc is None or sc.student_id != s.id or sc.status != 'graded' or not sc.crop_key:
        raise HTTPException(404, _L(user, 'Şəkil yoxdur', 'Изображения нет', 'No image'))
    return StreamingResponse(storage_for_key(sc.crop_key).stream(sc.crop_key, db), media_type='image/jpeg',
                             headers={'Cache-Control': 'private, max-age=300'})


@router.get('/notifications')
def notifications(user: User = Depends(student_only), db: Session = Depends(get_db)):
    """Bildirişlər (serverdə saxlanmır – hər dəfə hesablanır): açıq və 24 saat ərzində açılacaq testlər,
    yeni sınaq nəticəsi (7 gün), bu gün / sabah əlavə məşğələ. key – cihazda «görüldü» işarəsi üçün sabit açar."""
    from zoneinfo import ZoneInfo
    from .exams_online import student_exams
    from .extra import student_courses
    s = me_student(db, user)
    at = now()
    hm = lambda x: aware(x).astimezone(ZoneInfo(SCHOOL_TZ)).strftime('%d.%m %H:%M')
    lang = user.language if user.language in ('ru', 'en') else 'az'
    L = lambda az, ru, en: {'az': az, 'ru': ru, 'en': en}[lang]          # bildiriş mətni istifadəçinin dilində (rus dili promtu)
    out = []
    tasks = _my_tasks(db, s)
    for t in tasks:
        a = db.scalar(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.student_id == s.id))
        st = _status(t, a, at)
        kind = 'sınaq' if t.kind == 'sinaq' else 'test'
        if st in ('açıq', 'həll edilir'):
            out.append({'key': f'task-open-{t.id}', 'kind': kind, 'title': f"{t.title} – {L('açıqdır', 'открыт', 'open')}",
                        'text': L(f'{hm(t.closes_at)}-dək', f'до {hm(t.closes_at)}', f'until {hm(t.closes_at)}') + ' · ' + L(f'{t.duration_min} dəq', f'{t.duration_min} мин', f'{t.duration_min} min'), 'link': f'/t/{t.id}', 'at': aware(t.opens_at)})
        elif st == 'gözlənilir' and aware(t.opens_at) - at <= dt.timedelta(hours=24):
            out.append({'key': f'task-soon-{t.id}', 'kind': kind, 'title': f"{t.title} – {L('tezliklə', 'скоро', 'soon')}",
                        'text': L('açılır', 'открывается', 'opens') + f': {hm(t.opens_at)}', 'link': '/tasks', 'at': aware(t.opens_at)})
    for x in student_exams(db, s, [t.id for t in tasks]):
        if x.get('closed') and x.get('pct') is not None and at - x['closes_at'] <= dt.timedelta(days=7):
            out.append({'key': f'exam-{x["batch_id"]}', 'kind': 'nəticə', 'title': f'{x["title"]} – ' + L('nəticə hazırdır', 'результат готов', 'result is ready'),
                        'text': f'{x["pct"]}% · ' + L('sinifdə', 'в классе', 'in class') + f' {x["place_class"]}/{x["class_count"]}', 'link': '/results',
                        'at': x['closes_at']})
    from ..models import ExamScan
    from ..models import ExamDelivery
    sent = {d.exam_id: d for d in db.scalars(select(ExamDelivery).where(ExamDelivery.student_id == s.id))}
    for d in sent.values():                                   # nəticə paketi (cavab kartı + öz testi): göndəriş bir dəfə, bildiriş də bir dəfə
        e = db.get(Exam, d.exam_id)
        if e and published_for(db, e, s.id) and at - aware(d.sent_at) <= dt.timedelta(days=7):
            out.append({'key': f'pkg-{e.id}', 'kind': 'nəticə',
                        'title': f'{e.kind}-{e.no} – ' + L('nəticən hazırdır', 'твой результат готов', 'your result is ready'),
                        'text': L('cavab kartın və öz testin (altmövzu və № ilə)', 'твой бланк и твой тест (с подтемой и №)',
                                  'your answer card and your test (with subtopic and number)'),
                        'link': f'/results?pkg={e.id}', 'at': aware(d.sent_at)})
    for sc in db.scalars(select(ExamScan).where(ExamScan.student_id == s.id, ExamScan.status == 'graded')):   # kartın şəkli və nəticəsi
        e = db.get(Exam, sc.exam_id)
        if e and e.id in sent:
            continue                                          # paket bildirişi artıq var
        if e and e.results_published_at and sc.updated_at and at - aware(sc.updated_at) <= dt.timedelta(days=7):   # nəşrdən əvvəl bal bildirilmir
            out.append({'key': f'card-{sc.id}-{int(aware(sc.updated_at).timestamp())}', 'kind': 'nəticə',
                        'title': f'{e.kind}-{e.no} – ' + L('kartının şəkli və nəticəsi', 'фото твоего бланка и результат', 'your answer card and result'),
                        'text': L(f'{sc.points:g} bal · cavablarını düz cavablarla yoxla', f'{sc.points:g} балл · сверь ответы с правильными',
                                  f'{sc.points:g} points · check your answers against the key') if sc.points is not None else '',
                        'link': '/results', 'at': aware(sc.updated_at)})
    today = at.astimezone(ZoneInfo(SCHOOL_TZ)).date()
    for c in student_courses(db, s):
        n = c['next']
        if n and (n['date'] - today).days <= 1:
            when = L('bu gün', 'сегодня', 'today') if n['date'] == today else L('sabah', 'завтра', 'tomorrow')
            out.append({'key': f'extra-{n["id"]}', 'kind': 'məşğələ', 'title': f'{c["title"]} – {when} {n["start"]}',
                        'text': ' · '.join(n['topics']) or n['format'], 'link': '/extra',
                        'at': dt.datetime.combine(n['date'], dt.time.fromisoformat(n['start']), tzinfo=ZoneInfo(SCHOOL_TZ))})
    db.commit()
    return sorted(out, key=lambda x: x['at'])


@router.get('/extra')
def my_extra(user: User = Depends(student_only), db: Session = Depends(get_db)):
    """Əlavə məşğələlərim: kursun planı, növbəti məşğələ, öz iştirakım və məşğələ testlərim."""
    from .extra import student_courses
    return student_courses(db, me_student(db, user))


@router.post('/extra/{sid}/join')
def join_extra(sid: int, user: User = Depends(student_only), db: Session = Depends(get_db)):
    """Onlayn məşğələyə qoşul: qoşulma vaxtı qeyd olunur (müəllim davamiyyəti təsdiqləyir), keçid qaytarılır."""
    from .extra import join
    return join(db, me_student(db, user), sid)


def my_exam(db: Session, user: User, exam_id: int) -> tuple[Student, Exam]:
    """Şagirdin ÖZ imtahanı: başqa sinfin və ya əlavə imtahanda seçilməyən şagirdin imtahanı – 403."""
    s = me_student(db, user)
    e = db.get(Exam, exam_id)
    if e is None:
        raise HTTPException(404, _L(user, 'İmtahan tapılmadı', 'Работа не найдена', 'Exam not found'))
    if e.assignment_id not in {ta.id for ta, _ in my_assignments(db, s)} or (e.extra_students is not None and s.id not in e.extra_students):
        raise HTTPException(403, _L(user, 'Bu imtahan sizin deyil', 'Эта работа не ваша', 'This exam is not yours'))
    return s, e


@router.get('/exams/{exam_id}/card')
def exam_card_view(exam_id: int, user: User = Depends(student_only), db: Session = Depends(get_db)):
    """Şagirdin öz cavab kartı: yalnız müəllim «nəticəni şagirdlərə göstər» etdikdən sonra; variant sualları əvvəl heç vaxt göstərilmir."""
    from ..exam_cards import exam_card
    s, e = my_exam(db, user, exam_id)
    if not published_for(db, e, s.id):
        raise HTTPException(403, _L(user, 'Nəticələr hələ şagirdlərə göstərilməyib', 'Результаты ещё не опубликованы', 'Results have not been published yet'))
    c = exam_card(db, e, s.id)
    if c is not None:
        for q in c['questions']:
            q.pop('ref', None)                       # «altmövzu · №n · B<id>» texniki ünvan yalnız müəllimə; şagird yalnız altmövzu adını (topic) görür
            if q.get('topic'):
                q['topic'] = label_ml(q['topic'], user.language)   # altmövzu adı şagirdin dilində (RU/EN)
        c['appeal_until'] = e.appeal_until
        c['appeals'] = [{'id': a.id, 'slot': a.slot, 'source': a.source, 'status': a.status, 'reason': a.reason, 'teacher_reply': a.teacher_reply,
                         'apply_all': a.apply_all} for a in db.scalars(select(ExamAppeal).where(ExamAppeal.exam_id == e.id, ExamAppeal.student_id == s.id))]
    if c is None or not c['sources']:                 # yazmayan şagirdə sual və düz cavablar göstərilmir
        raise HTTPException(404, _L(user, 'Cavab kartı yoxdur', 'Бланка ответов нет', 'No answer card'))
    return c


@router.get('/exams/{exam_id}/package')
def exam_package(exam_id: int, user: User = Depends(student_only), db: Session = Depends(get_db)):
    """Nəticə paketi (bir ekran): kartın şəkli + oxunuş; nəşrdən/göndərişdən sonra öz testi (sual, öz cavab, düz cavab, bal) və sualın
    altında «altmövzu · №n». Başqa şagirdin paketi (başqa sinif/əlavə imtahan) – 404; kartı olmayan (yazmayan) şagird – 404."""
    from ..exam_cards import student_package
    try:
        s, e = my_exam(db, user, exam_id)
    except HTTPException:                                 # başqasının imtahanı mövcudluğunu belə bildirmir
        raise HTTPException(404, _L(user, 'Nəticə paketi yoxdur', 'Пакета результата нет', 'No result package'))
    pub = published_for(db, e, s.id)
    p = student_package(db, e, s.id, user.language, pub)
    if p is None:                                         # yazmayan şagirdə sual və düz cavablar göstərilmir
        raise HTTPException(404, _L(user, 'Nəticə paketi yoxdur', 'Пакета результата нет', 'No result package'))
    if pub:
        p['appeal_until'] = e.appeal_until
        p['appeals'] = [{'id': a.id, 'slot': a.slot, 'source': a.source, 'status': a.status, 'reason': a.reason,
                         'teacher_reply': a.teacher_reply} for a in db.scalars(
                             select(ExamAppeal).where(ExamAppeal.exam_id == e.id, ExamAppeal.student_id == s.id))]
        from ..models import ExamDelivery
        d = db.get(ExamDelivery, (e.id, s.id))
        if d is not None and d.seen_at is None:           # müəllim ekranında «baxıb»
            d.seen_at = now()
            db.commit()
    return p


class AppealIn(BaseModel):
    slot: int = Field(ge=1)
    source: Literal['paper', 'online'] = 'paper'
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1000)]


@router.post('/exams/{exam_id}/appeals')
def create_appeal(exam_id: int, body: AppealIn, user: User = Depends(student_only), db: Session = Depends(get_db)):
    """Sual üzrə apelyasiya: yalnız nəşrdən sonra və müddət (appeal_until) bitənədək; bir sual (mənbə üzrə) – bir apelyasiya."""
    from ..appeals import ref_of
    from ..domain.ksq_card import key_value
    from ..models import ExamScan, ExamVariant
    s, e = my_exam(db, user, exam_id)
    if not published_for(db, e, s.id):
        raise HTTPException(403, _L(user, 'Nəticələr hələ şagirdlərə göstərilməyib', 'Результаты ещё не опубликованы', 'Results have not been published yet'))
    if e.appeal_until is not None and now() > aware(e.appeal_until):
        raise HTTPException(400, _L(user, 'Apelyasiya müddəti bitib', 'Срок подачи апелляции истёк', 'The appeal period has ended'))
    sc = db.scalar(select(ExamScan).where(ExamScan.exam_id == e.id, ExamScan.student_id == s.id, ExamScan.source == body.source,
                                          ExamScan.status == 'graded'))
    v = db.get(ExamVariant, (e.id, s.id))
    q = next((x for x in (v.questions if v else []) if x['slot'] == body.slot), None)
    if sc is None or q is None:
        raise HTTPException(404, _L(user, 'Bu sual üçün nəticə tapılmadı', 'Результат по этому вопросу не найден', 'No result found for this question'))
    if body.slot in ({it['n'] for it in (e.items or []) if it.get('annulled')} | set(sc.lost or [])):
        raise HTTPException(400, _L(user, 'Bu sual sayılmayıb – apelyasiya lazım deyil', 'Этот вопрос не засчитывался – апелляция не нужна', 'This question was not counted – no appeal needed'))
    if db.scalar(select(ExamAppeal.id).where(ExamAppeal.exam_id == e.id, ExamAppeal.student_id == s.id, ExamAppeal.slot == body.slot,
                                             ExamAppeal.source == body.source)):
        raise HTTPException(409, _L(user, 'Bu sual üzrə apelyasiya artıq verilib', 'Апелляция по этому вопросу уже подана', 'An appeal for this question has already been submitted'))
    read = next((r.get('value') for r in sc.reading or [] if r.get('slot') == body.slot), None)
    a = ExamAppeal(exam_id=e.id, student_id=s.id, slot=body.slot, source=body.source, bank_id=q.get('bank_id'), bank_ref=ref_of(db, q),
                   my_answer=read or '', correct_at_time=key_value(q), reason=body.reason)
    db.add(a)
    db.flush()
    from .common import audit
    audit(db, user, 'create', 'exam_appeal', a.id, exam_id=e.id, slot=body.slot, source=body.source)
    db.commit()
    return {'id': a.id, 'status': a.status}


@router.delete('/exam-appeals/{appeal_id}')
def withdraw_appeal(appeal_id: int, user: User = Depends(student_only), db: Session = Depends(get_db)):
    """Cavablanmamış öz apelyasiyanı geri götür; başqasının apelyasiyası – 403."""
    s = me_student(db, user)
    a = db.get(ExamAppeal, appeal_id)
    if a is None:
        raise HTTPException(404, _L(user, 'Apelyasiya tapılmadı', 'Апелляция не найдена', 'Appeal not found'))
    if a.student_id != s.id:
        raise HTTPException(403, _L(user, 'Bu apelyasiya sizin deyil', 'Эта апелляция не ваша', 'This appeal is not yours'))
    if a.status != 'open':
        raise HTTPException(409, _L(user, 'Qərar verilib – geri götürmək olmaz', 'Решение принято – отозвать нельзя', 'A decision has been made – cannot withdraw'))
    db.delete(a)
    db.commit()
    return {'ok': True}


def _sem_args(exams: list, gmap: dict, sem: int) -> tuple:
    """Yarımil qiyməti üçün (KSQ qiymətləri, BSQ) – əlavə imtahan ayrıca sayılmır (exam_logic.final_grades)."""
    from ..exam_logic import final_grades
    ksq, bsq = final_grades([x for x in exams if x.semester == sem], lambda x: gmap.get(x.id))
    return [g for _, g in ksq if g is not None], bsq


def _sem_missed(exams: list, gmap: dict, sem: int) -> list[int]:
    """Keçirilmiş, lakin qiyməti olmayan (buraxılmış) KSQ nömrələri – yarımil qiyməti «şərti»."""
    from ..exam_logic import final_grades, missed_ksq
    xs = [x for x in exams if x.semester == sem]
    ksq, _ = final_grades(xs, lambda x: gmap.get(x.id))
    return missed_ksq(xs, ksq, today())


@router.get('/results')
def results(user: User = Depends(student_only), db: Session = Depends(get_db)):
    s = me_student(db, user)
    at = now()
    subjects = []
    for ta, c in my_assignments(db, s):
        exams = [x for x in db.scalars(select(Exam).where(Exam.assignment_id == ta.id, Exam.to_journal.is_(True)).order_by(Exam.semester, Exam.date))
                 if x.extra_students is None or s.id in x.extra_students]      # əlavə imtahan – yalnız seçilən şagirdə
        ex_rows, gmap, hidden_sems = [], {}, set()
        from ..models import ExamScan
        for e in exams:
            sc = db.get(ExamScore, (e.id, s.id))
            g = grade_from_points(sc.points, e.max_points) if sc and sc.points is not None and not sc.absent else None
            # skanı olan, lakin müəllim hələ açmayıb imtahan: nəticə şagirdə göstərilmir
            pub_for = published_for(db, e, s.id)              # global nəşr və ya «skan olunan kimi göndər» (şagird üzrə)
            card = _card(db, e, s.id)
            hidden = not pub_for and db.scalar(
                select(ExamScan.id).where(ExamScan.exam_id == e.id, ExamScan.student_id == s.id).limit(1)) is not None
            if hidden:
                hidden_sems.add(e.semester)
                g = None
            # özünüqiymətləndirmə: tapşırıq üzrə ✓/✗ və standart (sinif yoldaşlarının nəticəsi yoxdur)
            items = [{'n': it['n'], 'points': it['points'], 'standard': it.get('standard'), 'ok': bool(m)}
                     for it, m in zip(e.items or [], (sc.item_marks or []) if g else [])]
            weak = sorted({i['standard'] for i in items if i['standard'] and not i['ok']})
            gmap[e.id] = g
            ex_rows.append({'exam_id': e.id, 'published': pub_for, 'has_package': bool(pub_for and card),
                            'kind': e.kind, 'no': e.no, 'semester': e.semester, 'date': e.date, 'extra_seq': e.extra_seq or 0,
                            'points': sc.points if sc and not hidden else None, 'max_points': e.max_points, 'hidden': hidden,
                            'pct': round(sc.points * 100 / e.max_points, 1) if g else None, 'grade': g,
                            'absent': bool(sc and sc.absent), 'taken_on': sc.taken_on if sc and g else None,
                            'items': items, 'weak_standards': weak, 'card': card})
        sem_g = {k: None if k in hidden_sems else semester_grade(*_sem_args(exams, gmap, k)) for k in (1, 2)}
        subjects.append({'subject': ta.subject, 'class_name': c.name, 'teacher': _teacher(db, ta),
                         'exams': ex_rows, **_stats(db, _entries(db, ta.id), s.id),
                         'semester_grades': sem_g, 'year_grade': year_grade(sem_g[1], sem_g[2]),
                         # buraxılmış KSQ – yarımil qiyməti «şərti» (müəllim əlavə KSQ təyin edə bilər)
                         'semester_missed_ksq': {k: [] if k in hidden_sems else _sem_missed(exams, gmap, k) for k in (1, 2)}})
    task_rows, mistakes = [], []
    done = []
    for t in _my_tasks(db, s):
        a = db.scalar(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.student_id == s.id))
        if a and a.submitted_at and t.kind != 'ksq':          # onlayn KSQ – «İmtahanlar» sətrində (müəllim açanda)
            done.append((t, a))
    done.sort(key=lambda x: aware(x[1].submitted_at), reverse=True)          # ən yenisi yuxarıda
    for t, a in done:
        ta = db.get(TeachingAssignment, t.assignment_id)
        task_rows.append({'id': t.id, 'title': t.title, 'kind': t.kind, 'subject': ta.subject if ta else None,
                          'submitted_at': aware(a.submitted_at), 'closes_at': aware(t.closes_at), 'correct': a.correct,
                          'total': a.total, 'pct': attempt_pct(db, t, a),       # sınaqda cərimə ilə – «Sınaq imtahanları» ilə eyni
                          'grade': _shown_grade(t, a), 'auto_submitted': a.auto_submitted,
                          'can_review': _can_review(db, t, a, at), 'solution': bool(a.solution_key)})
        if _can_review(db, t, a, at):
            for i in a.order:
                q = t.questions[i]
                if not is_ok(t, a, i):                                    # müəllimin açıq sual düzəlişi nəzərə alınır
                    mistakes.append({'task': t.title, 'task_id': t.id, **_public_q(q, i), 'given': (a.answers or {}).get(str(i)),
                                     'correct': q.get('correct'), 'answer': q.get('answer'), 'explanation': q.get('explanation')})
    # nailiyyətlər «Uğurlarım»dadır (app/certificates.py::achievements) – burada təkrarlanmır
    badges: list = []
    return {'subjects': subjects, 'tasks': task_rows, 'mistakes': mistakes[:100], 'badges': badges}


@router.get('/analytics')
def analytics(date_from: dt.date | None = None, date_to: dt.date | None = None, user: User = Depends(student_only),
              db: Session = Depends(get_db)):
    """Öz göstəricilərin və sinif ortası (adsız, yalnız orta rəqəm)."""
    s = me_student(db, user)
    out = []
    for ta, c in my_assignments(db, s):
        eids = _entries(db, ta.id, date_from, date_to)
        mine = _stats(db, eids, s.id)
        others = [_stats(db, eids, x.id) for x in roster(db, ta)]

        def avg(k):
            v = [o[k] for o in others if o[k] is not None]
            return round(sum(v) / len(v), 2) if v else None
        out.append({'subject': ta.subject, 'class_name': c.name, 'me': mine,
                    'class_avg': {k: (avg(k) if len(others) >= 5 else None) for k in ('avg_grade', 'attendance_pct', 'homework_pct')},
                    'class_avg_hidden': len(others) < 5,          # 5-dən az şagird – sinif ortası şəxsi nəticəni açar
                    'class_size': len(others)})
    return {'from': date_from, 'to': date_to, 'subjects': out}


# ---------------------------------------------------------------- həllin şəkilləri (mövzu testi və sınaq): bir PDF
SOLUTION_MAX = 25 * 1024 ** 2


def solution_response(db: Session, a: TaskAttempt, name: str, user: User | None = None):
    from urllib.parse import quote

    from fastapi.responses import StreamingResponse

    from ..storage import storage_for_key
    if not a or not a.solution_key:
        raise HTTPException(404, _L(user, 'Həll faylı yoxdur', 'Файла с решением нет', 'No solution file'))
    st = storage_for_key(a.solution_key)
    return StreamingResponse(st.stream(a.solution_key, db), media_type='application/pdf', headers={
        'Content-Disposition': f"inline; filename*=UTF-8''{quote(name)}"})


@router.post('/tasks/{task_id}/solution')
def upload_solution(task_id: int, file: UploadFile = File(...), user: User = Depends(student_only),
                    db: Session = Depends(get_db)):
    """Şagird həllin şəkillərini (brauzerdə bir PDF-ə yığılır) müəllimə göndərir – test bağlanana qədər; təkrar göndərmə əvəz edir."""
    from ..storage import get_storage
    s = me_student(db, user)
    t = _task_for(db, s, task_id, user)
    a = db.scalar(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.student_id == s.id))
    if not a:
        raise HTTPException(400, _L(user, 'Əvvəlcə testə başlayın', 'Сначала начните тест', 'Start the test first'))
    if now() >= aware(t.closes_at):
        raise HTTPException(400, _L(user, 'Test bağlanıb – həll göndərilmir', 'Тест закрыт – решение не принимается', 'The test is closed – solutions are no longer accepted'))
    head = file.file.read(5)
    file.file.seek(0)
    if head != b'%PDF-':
        raise HTTPException(400, _L(user, 'Fayl PDF deyil', 'Файл не в формате PDF', 'The file is not a PDF'))
    key, size = get_storage().save(file.file, f'hell-{t.id}-{s.id}.pdf', 'application/pdf', SOLUTION_MAX, db)
    a.solution_key, a.solution_size, a.solution_at = key, size, now()
    db.commit()
    return {'solution_at': a.solution_at, 'solution_size': size}


@router.get('/tasks/{task_id}/solution')
def my_solution(task_id: int, user: User = Depends(student_only), db: Session = Depends(get_db)):
    s = me_student(db, user)
    t = _task_for(db, s, task_id, user)
    a = db.scalar(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.student_id == s.id))
    return solution_response(db, a, f'hell-{t.id}.pdf', user)
