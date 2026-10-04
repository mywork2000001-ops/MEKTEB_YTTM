"""Şagird portalı – şagird YALNIZ özünə aid məlumatı görür; sinif ortası adsızdır.
Bu gün (motivasiya, imtahan sayğacı, müəllimlər) · Dərs (gündəlik) · Plan · Tapşırıqlar (vaxtlı) · Nəticələrim · Analitika."""
from __future__ import annotations

import datetime as dt
import random

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require
from ..domain.answers import check
from ..domain.plan import view_range
from ..domain.rules import grade_from_points, semester_grade
from ..models import (Attendance, Exam, ExamScore, GroupMember, HomeworkCheck, JournalEntry, Mark, OnlineTask, PlanLesson,
                      Role, SchoolClass, Student, TaskAttempt, TeachingAssignment, User, now)
from ..services import SCHOOL_TZ, journal_entries, plan_ctx, roster, taught_lesson, today
from .plan import WEEKDAYS, bell
from .tasks import aware, expire_due, finalize

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


def me_student(db: Session, user: User) -> Student:
    s = db.scalar(select(Student).where(Student.user_id == user.id, Student.archived_at.is_(None)))
    if not s:
        raise HTTPException(404, 'Şagird qeydi tapılmadı')
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
        pct = round(last.correct * 100 / last.total)
        personal = f'Son tapşırıqda nəticən {pct}% oldu – ' + ('əla, belə davam et!' if pct >= 81 else
                                                               'yaxşıdır, bir az da səy!' if pct >= 61 else
                                                               'səhvlərinə bax, növbəti dəfə daha yaxşı olacaq.')
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


@router.get('/day')
def day(date: dt.date | None = None, user: User = Depends(student_only), db: Session = Depends(get_db)):
    s = me_student(db, user)
    d = date or today()
    lessons = []
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
    lessons.sort(key=lambda x: (x['time'] or '', x['period']))
    return {'date': d, 'weekday': WEEKDAYS[d.weekday()], 'lessons': lessons}


@router.get('/plan')
def plan(view: str = 'week', date: dt.date | None = None, user: User = Depends(student_only),
         db: Session = Depends(get_db)):
    s = me_student(db, user)
    d = date or today()
    items, rng = [], (d, d)
    for ta, c in my_assignments(db, s):
        ctx = plan_ctx(db, ta)
        try:
            a, b = view_range(view, d, ctx.year.sem1_end, ctx.year.sem2_start, ctx.year.start, ctx.year.end,
                              weekend=any(k in ('5', '6') for k in (ta.slots or {})))
            rng = (a, b)
        except ValueError:
            raise HTTPException(400, 'görünüş: day, week, month, semester')
        entries = journal_entries(db, ta.id, a, b)
        for d_, period, sl in _slots_with_entries(ctx, a, b, entries):
            e = entries.get((d_, period))
            pl = taught_lesson(ctx, sl, e)
            items.append({'date': d_, 'weekday': WEEKDAYS[d_.weekday()], 'period': period,
                          'time': bell(db, c, period, ta, d_), 'subject': ta.subject, 'class_name': c.name,
                          'group': c.kind == 'qrup',
                          **_plan_fields(pl, sl, e), 'homework': e.homework if e else None})
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


def _can_review(t: OnlineTask, a: TaskAttempt | None, at: dt.datetime) -> bool:
    if not a or not a.submitted_at or t.show_answers == 'never':
        return False
    return t.show_answers == 'after_submit' or at >= aware(t.closes_at)


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
                    'result': {'correct': a.correct, 'total': a.total, 'grade': a.grade} if a and a.submitted_at else None,
                    'can_review': _can_review(t, a, at), 'kind': t.kind,
                    'topic_seq': pl.seq if pl else None, 'topic': pl.topic if pl else None})
    return out


def _task_for(db: Session, s: Student, task_id: int) -> OnlineTask:
    t = next((x for x in _my_tasks(db, s) if x.id == task_id), None)
    if not t:
        raise HTTPException(404, 'Tapşırıq tapılmadı')
    return t


def _public_q(q: dict, i: int) -> dict:
    """Şagirdə düzgün cavab və izah GÖNDƏRİLMİR."""
    return {'index': i, 'kind': q['kind'], 'text': q['text'], 'options': q.get('options'), 'image': q.get('image')}


@router.post('/tasks/{task_id}/start')
def start(task_id: int, user: User = Depends(student_only), db: Session = Depends(get_db)):
    s = me_student(db, user)
    t = _task_for(db, s, task_id)
    at = now()
    a = db.scalar(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.student_id == s.id))
    if a is None:
        if at < aware(t.opens_at):
            raise HTTPException(409, 'Tapşırıq hələ açılmayıb')
        if at >= aware(t.closes_at):
            raise HTTPException(409, 'Tapşırığın vaxtı bitib')
        order = list(range(len(t.questions)))
        if t.shuffle:
            random.Random(f'{t.id}:{s.id}').shuffle(order)
        a = TaskAttempt(task_id=t.id, student_id=s.id, started_at=at, order=order, answers={},
                        deadline=min(at + dt.timedelta(minutes=t.duration_min), aware(t.closes_at)))
        db.add(a)
        db.commit()
    elif not a.submitted_at and at >= aware(a.deadline):
        finalize(db, t, a, at, auto=True)
        db.commit()
    if a.submitted_at:
        raise HTTPException(409, 'Tapşırıq artıq təhvil verilib')
    return {'task_id': t.id, 'title': t.title, 'deadline': aware(a.deadline), 'server_time': at,
            'answers': a.answers, 'questions': [_public_q(t.questions[i], i) for i in a.order]}


class AnswersIn(BaseModel):
    answers: dict[str, int | str | None]


def _open_attempt(db: Session, s: Student, t: OnlineTask) -> TaskAttempt:
    a = db.scalar(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.student_id == s.id))
    if not a:
        raise HTTPException(409, 'Tapşırığa başlanmayıb')
    if a.submitted_at:
        raise HTTPException(409, 'Tapşırıq artıq təhvil verilib')
    return a


@router.put('/tasks/{task_id}/answers')
def save_answers(task_id: int, body: AnswersIn, user: User = Depends(student_only), db: Session = Depends(get_db)):
    """Avtomatik yadda saxlama. Müddət bitibsə – serverdə avtomatik təhvil (sonrakı cavablar qəbul edilmir)."""
    s = me_student(db, user)
    t = _task_for(db, s, task_id)
    a = _open_attempt(db, s, t)
    at = now()
    if at >= aware(a.deadline):
        finalize(db, t, a, at, auto=True)
        db.commit()
        raise HTTPException(409, 'Vaxt bitdi – cavablar avtomatik təhvil verildi')
    n = len(t.questions)
    clean = {k: v for k, v in body.answers.items() if k.isdigit() and int(k) < n}
    a.answers = {**(a.answers or {}), **clean}
    db.commit()
    return {'saved': len(clean), 'deadline': aware(a.deadline), 'server_time': at}


@router.post('/tasks/{task_id}/submit')
def submit(task_id: int, body: AnswersIn | None = None, user: User = Depends(student_only),
           db: Session = Depends(get_db)):
    s = me_student(db, user)
    t = _task_for(db, s, task_id)
    a = _open_attempt(db, s, t)
    at = now()
    late = at >= aware(a.deadline)
    if body and at < aware(a.deadline) + SUBMIT_GRACE:
        n = len(t.questions)
        a.answers = {**(a.answers or {}), **{k: v for k, v in body.answers.items() if k.isdigit() and int(k) < n}}
    finalize(db, t, a, at, auto=late)
    db.commit()
    return {'correct': a.correct, 'total': a.total, 'grade': a.grade, 'auto_submitted': a.auto_submitted,
            'can_review': _can_review(t, a, at)}


@router.get('/tasks/{task_id}/review')
def review(task_id: int, user: User = Depends(student_only), db: Session = Depends(get_db)):
    s = me_student(db, user)
    t = _task_for(db, s, task_id)
    a = db.scalar(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.student_id == s.id))
    if not _can_review(t, a, now()):
        raise HTTPException(403, 'Cavablar hələ açılmayıb' if a and a.submitted_at else 'Tapşırıq təhvil verilməyib')
    out = []
    for i in a.order:
        q = t.questions[i]
        given = (a.answers or {}).get(str(i))
        out.append({**_public_q(q, i), 'given': given, 'ok': check(q, given), 'correct': q.get('correct'),
                    'answer': q.get('answer'), 'explanation': q.get('explanation')})
    return {'title': t.title, 'correct': a.correct, 'total': a.total, 'grade': a.grade, 'questions': out}


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
    out = []
    tasks = _my_tasks(db, s)
    for t in tasks:
        a = db.scalar(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.student_id == s.id))
        st = _status(t, a, at)
        kind = 'sınaq' if t.kind == 'sinaq' else 'test'
        if st in ('açıq', 'həll edilir'):
            out.append({'key': f'task-open-{t.id}', 'kind': kind, 'title': f'{t.title} – açıqdır',
                        'text': f'{hm(t.closes_at)}-dək · {t.duration_min} dəq', 'link': f'/t/{t.id}', 'at': aware(t.opens_at)})
        elif st == 'gözlənilir' and aware(t.opens_at) - at <= dt.timedelta(hours=24):
            out.append({'key': f'task-soon-{t.id}', 'kind': kind, 'title': f'{t.title} – tezliklə',
                        'text': f'açılır: {hm(t.opens_at)}', 'link': '/tasks', 'at': aware(t.opens_at)})
    for x in student_exams(db, s, [t.id for t in tasks]):
        if x.get('closed') and x.get('pct') is not None and at - x['closes_at'] <= dt.timedelta(days=7):
            out.append({'key': f'exam-{x["batch_id"]}', 'kind': 'nəticə', 'title': f'{x["title"]} – nəticə hazırdır',
                        'text': f'{x["pct"]}% · sinifdə {x["place_class"]}/{x["class_count"]}', 'link': '/results',
                        'at': x['closes_at']})
    today = at.astimezone(ZoneInfo(SCHOOL_TZ)).date()
    for c in student_courses(db, s):
        n = c['next']
        if n and (n['date'] - today).days <= 1:
            when = 'bu gün' if n['date'] == today else 'sabah'
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


@router.get('/results')
def results(user: User = Depends(student_only), db: Session = Depends(get_db)):
    s = me_student(db, user)
    at = now()
    subjects = []
    for ta, c in my_assignments(db, s):
        exams = list(db.scalars(select(Exam).where(Exam.assignment_id == ta.id).order_by(Exam.semester, Exam.date)))
        ex_rows, per_sem = [], {1: ([], None), 2: ([], None)}
        for e in exams:
            sc = db.get(ExamScore, (e.id, s.id))
            g = grade_from_points(sc.points, e.max_points) if sc and sc.points is not None and not sc.absent else None
            # özünüqiymətləndirmə: tapşırıq üzrə ✓/✗ və standart (sinif yoldaşlarının nəticəsi yoxdur)
            items = [{'n': it['n'], 'points': it['points'], 'standard': it.get('standard'), 'ok': bool(m)}
                     for it, m in zip(e.items or [], (sc.item_marks or []) if g else [])]
            weak = sorted({i['standard'] for i in items if i['standard'] and not i['ok']})
            ex_rows.append({'kind': e.kind, 'no': e.no, 'semester': e.semester, 'date': e.date,
                            'points': sc.points if sc else None, 'max_points': e.max_points,
                            'pct': round(sc.points * 100 / e.max_points, 1) if g else None, 'grade': g,
                            'absent': bool(sc and sc.absent), 'taken_on': sc.taken_on if sc and g else None,
                            'items': items, 'weak_standards': weak})
            ks, bs = per_sem[e.semester]
            if g is not None:
                per_sem[e.semester] = (ks + [g], bs) if e.kind == 'KSQ' else (ks, g)
        subjects.append({'subject': ta.subject, 'class_name': c.name, 'teacher': _teacher(db, ta),
                         'exams': ex_rows, **_stats(db, _entries(db, ta.id), s.id),
                         'semester_grades': {k: semester_grade(*v) for k, v in per_sem.items()}})
    task_rows, mistakes = [], []
    for t in _my_tasks(db, s):
        a = db.scalar(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.student_id == s.id))
        if not a or not a.submitted_at:
            continue
        task_rows.append({'id': t.id, 'title': t.title, 'submitted_at': aware(a.submitted_at), 'correct': a.correct,
                          'total': a.total, 'pct': round(a.correct * 100 / a.total, 1) if a.total else None,
                          'grade': a.grade, 'auto_submitted': a.auto_submitted})
        if _can_review(t, a, at):
            for i in a.order:
                q = t.questions[i]
                given = (a.answers or {}).get(str(i))
                if not check(q, given):
                    mistakes.append({'task': t.title, **_public_q(q, i), 'given': given, 'correct': q.get('correct'),
                                     'answer': q.get('answer'), 'explanation': q.get('explanation')})
    badges = []
    if any(r['pct'] == 100 for r in task_rows):
        badges.append({'key': 'perfect', 'title': 'Tam bal', 'text': 'Tapşırığı 100% həll etdin'})
    if len(task_rows) >= 5:
        badges.append({'key': 'steady', 'title': 'Ardıcıl', 'text': '5 tapşırıq təhvil verdin'})
    if any((x['attendance_pct'] or 0) == 100 and x['marks'] for x in subjects):
        badges.append({'key': 'present', 'title': 'Hər dərsdə', 'text': 'Heç bir dərsi buraxmamısan'})
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
                    'class_avg': {k: avg(k) for k in ('avg_grade', 'attendance_pct', 'homework_pct')},
                    'class_size': len(others)})
    return {'from': date_from, 'to': date_to, 'subjects': out}
