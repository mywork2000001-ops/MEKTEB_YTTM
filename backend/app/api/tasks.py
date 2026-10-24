"""Onlayn tapşırıqlar (müəllim): test bazasından və ya öz suallarından, tarix + saat aralığı + həll müddəti.
Məsələn: 29.09.2026 15:00–16:00, müddət 40 dəq. Vaxt bitəndə cavablar avtomatik təhvil verilir (serverdə)."""
from __future__ import annotations

import copy
import datetime as dt
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import AfterValidator, BaseModel, Field, model_validator
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import staff
from ..domain.answers import check, part_share
from ..distractors import question_distribution
from ..domain.rules import FORMATIVE_SCALE, formative_grade, level, normalize_scale, summative_grade, validate_scale
from ..models import prepare_points
from ..models import (BankFile, BankQuestion, BankSource, Mark, OnlineTask, PlanLesson, Student, TaskAttempt, TeachingAssignment,
                      TestBatch, User, now)
from ..services import class_grade, own_assignment, roster
from ..timing import NO_DEADLINE, attempt_deadline, closes_or_none, fits_window, is_unlimited, no_timer
from .common import audit, get_or_404

router = APIRouter(prefix='/api/tasks', tags=['tasks'])

MIN_TEST_MIN = 45        # mövzu testi və sınaqda həll müddəti ən azı 45 dəqiqə (az yazılsa – 45-ə qaldırılır)
# 0 – taymer yoxdur (müddətsiz test, app/timing.py); 1–44 → 45-ə qaldırılır
TestMinutes = Annotated[int, Field(ge=0, le=300), AfterValidator(lambda v: v if v == 0 else max(v, MIN_TEST_MIN))]


def aware(t: dt.datetime) -> dt.datetime:
    # SQLite tz saxlamır: oxunan vaxt UTC sayılır, yazılan vaxt UTC-yə çevrilir (+04:00 ilə gələn vaxt sürüşməsin)
    return t.astimezone(dt.timezone.utc) if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def is_ok(task: OnlineTask, a: TaskAttempt, i: int) -> bool:
    """Sual düzgündür: müəllimin düzəlişi (açıq sual) avtomatik yoxlamadan üstündür."""
    m = (a.manual or {}).get(str(i))
    return bool(m) if m is not None else check(task.questions[i], (a.answers or {}).get(str(i)))


def part_score(task: OnlineTask, a: TaskAttempt, i: int) -> float:
    """Sualın payı 0..1: müəllimin düzəlişi varsa – 1/0 (qismən balı əvəz edir); yoxsa uyğunluq sualında düz sətirlərin payı."""
    m = (a.manual or {}).get(str(i))
    if m is not None:
        return 1.0 if m else 0.0
    return part_share(task.questions[i], (a.answers or {}).get(str(i)))


def formative_kind(task: OnlineTask) -> bool:
    """Formativ test (mövzu testi və adi tapşırıq): sinfin formativ şkalası və qismən bal. KSQ və sınaq – dəyişməz."""
    return task.kind not in ('ksq', 'sinaq')


def class_scale(task: OnlineTask) -> dict:
    """Tapşırığın sinfinin formativ şkalası (TeachingAssignment.cert_rules['formative_scale']; yoxdursa defolt)."""
    from sqlalchemy.orm import object_session
    db = object_session(task)
    ta = db.get(TeachingAssignment, task.assignment_id) if db is not None else None
    return normalize_scale(((ta.cert_rules or {}).get('formative_scale')) if ta else None)


def score(task: OnlineTask, a: TaskAttempt):
    """Düzgün cavab sayı, 100 ballıq bal (sualın çətinlik balı ilə) və qiymət – düzəlişdən sonra da yenidən.
    Formativ testdə: uyğunluq sualında qismən bal + sinfin şkalası; `correct` yalnız tam düzləri sayır."""
    from ..domain.scoring import question_points
    ok = [is_ok(task, a, i) for i in range(len(task.questions))]
    a.correct, a.total = sum(ok), len(task.questions)
    qp = question_points(task.questions)
    if formative_kind(task):
        a.points = round(sum(p * part_score(task, a, i) for i, p in enumerate(qp)), 1) if a.total else None
        a.grade = formative_grade(a.points, class_scale(task)) if a.total else None
    else:
        a.points = round(sum(p for p, k in zip(qp, ok) if k), 1) if a.total else None
        a.grade = summative_grade(a.points) if a.total else None


def apct(a: TaskAttempt) -> float | None:
    """Cəhdin balı (0–100): 100 ballıq sistemdə – sualların çətinlik balı ilə; köhnə cəhd – düz ÷ ümumi."""
    if not a.total:
        return None
    return a.points if a.points is not None else a.correct * 100 / a.total


def _forget(*batch_ids):
    """Sınaq paketi dəyişdi – keşlənmiş nəticəsi atılır (app/result_cache.py)."""
    from .. import result_cache
    for b in batch_ids:
        if b:
            result_cache.forget(b)


def exam_score(task: OnlineTask, a: TaskAttempt, penalty: int = 0) -> dict:
    """Sınaq balı – hər yerdə eyni (jurnal, reytinq, şagird, sertifikat): bal = düz − səhv ÷ N, faiz = max(0, bal) ÷ sual.
    Boş cavab səhv sayılmır; müəllimin «düz say»ı boş cavaba verilibsə – düz sayılır, boş yox."""
    from ..domain.scoring import question_points
    n = len(task.questions)
    ok = [is_ok(task, a, i) for i in range(n)]
    empty = [not ok[i] and (a.answers or {}).get(str(i)) in (None, '') for i in range(n)]
    qp = question_points(task.questions)                 # 100 ballıq: hər sualın öz balı (köhnə test – bərabər)
    earned = sum(p for p, k in zip(qp, ok) if k)
    lost = sum(p for i, p in enumerate(qp) if not ok[i] and not empty[i])     # cərimə: səhvin öz balının 1/N-i
    pts = round(earned - (lost / penalty if penalty else 0), 2)
    c, blank = sum(ok), sum(empty)
    return {'correct': c, 'wrong': n - c - blank, 'blank': blank, 'points': pts,
            'pct': round(max(0.0, pts), 1) if n else None}


def penalty_of(db: Session, task: OnlineTask) -> int:
    if task.kind != 'sinaq' or not task.batch_id:
        return 0
    b = db.get(TestBatch, task.batch_id)
    return (b.penalty or 0) if b else 0


def attempt_pct(db: Session, task: OnlineTask, a: TaskAttempt) -> float | None:
    """Şagirdə və siyahılara göstərilən faiz: sınaqda cərimə ilə, qalanında düz ÷ ümumi."""
    if not a.submitted_at or not a.total:
        return None
    if task.kind == 'sinaq':
        return exam_score(task, a, penalty_of(db, task))['pct']
    return round(apct(a), 1)


def review_opens_at(db: Session, task: OnlineTask) -> dt.datetime:
    """«Bağlandıqdan sonra» cavablar: bir neçə sinfə verilmiş paketdə – ən gec bağlanan sinifdən sonra
    (erkən bağlanan sinif cavabları başqa sinif hələ yazarkən görməsin)."""
    c = aware(task.closes_at)
    if task.batch_id and not is_unlimited(task):
        for x in db.scalars(select(OnlineTask.closes_at).where(OnlineTask.batch_id == task.batch_id,
                                                               OnlineTask.archived_at.is_(None))):
            c = max(c, aware(x))
    return c


def finalize(db: Session, task: OnlineTask, a: TaskAttempt, at: dt.datetime | None = None, auto: bool = False):
    """Cavabları yoxlayır və təhvil verir (bir dəfə)."""
    if a.submitted_at:
        return a
    at = at or now()
    score(task, a)
    a.submitted_at, a.auto_submitted = min(at, aware(a.deadline)), auto
    if task.kind == 'ksq':                                 # onlayn KSQ/BSQ – bal kağız kartı kimi jurnala (api/ksq_online.py)
        from .ksq_online import record
        record(db, task, a)
    return a


def expire_due(db: Session, task: OnlineTask):
    """Müddəti bitmiş, təhvil verilməmiş cəhdlər avtomatik təhvil verilir."""
    t = now()
    changed = False
    for a in db.scalars(select(TaskAttempt).where(TaskAttempt.task_id == task.id, TaskAttempt.submitted_at.is_(None))):
        if aware(a.deadline) <= t:
            finalize(db, task, a, t, auto=True)
            changed = True
    if changed:
        db.commit()


class CustomQ(BaseModel):
    kind: Literal['mcq', 'open']
    text: str = Field(min_length=1, max_length=5000)
    options: list[str] | None = None
    correct: int | None = None
    answer: str | None = None
    explanation: str | None = None
    image: str | None = Field(None, max_length=5_000_000)       # data: URI şəkillər ola bilər
    bank_id: int | None = None                  # redaktə olunmuş bank sualı – mənbə izi saxlanır
    source: str | None = Field(None, max_length=40)
    lesson: str | None = Field(None, max_length=400)
    raw: dict | None = None                     # dəyişdirilməmiş sualın orijinal surəti (AZ/RU/EN tərcümələri qalsın)
    difficulty: Literal['asan', 'orta', 'çətin'] | None = None   # müəllimin seçimi (boş – avtomatik: statistika / növ)

    @model_validator(mode='after')
    def _v(self):
        if self.kind == 'mcq':
            if not self.options or len(self.options) < 2 or self.correct is None or not 0 <= self.correct < len(self.options):
                raise ValueError('variantlı sual: ən azı 2 variant və düzgün variantın nömrəsi')
        elif not (self.answer or '').strip():
            raise ValueError('açıq sual: düzgün cavab lazımdır')
        return self


class TaskIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str | None = Field(None, max_length=2000)
    opens_at: dt.datetime
    closes_at: dt.datetime | None = None        # boş – son tarix yoxdur
    duration_min: TestMinutes = 0               # 0 – taymer yoxdur
    bank_ids: list[int] = Field(default_factory=list)
    custom: list[CustomQ] = Field(default_factory=list)
    shuffle: bool = True
    show_answers: Literal['after_close', 'after_submit', 'never', 'teacher'] = 'after_close'
    student_ids: list[int] | None = None

    @model_validator(mode='after')
    def _v(self):
        o, c = aware(self.opens_at), closes_or_none(self.closes_at)
        if c <= o:
            raise ValueError('bağlanma vaxtı açılmadan sonra olmalıdır')
        if not fits_window(self.duration_min, o, c):
            raise ValueError('həll müddəti açıq qalma aralığından uzun ola bilməz')
        if not self.bank_ids and not self.custom:
            raise ValueError('ən azı bir sual seçin')
        if len(self.bank_ids) + len(self.custom) > 100:
            raise ValueError('bir tapşırıqda ən çoxu 100 sual')
        return self


def _snapshot(db: Session, ids: list[int]) -> list[dict]:
    rows = {q.id: (q, f) for q, f in db.execute(
        select(BankQuestion, BankFile).join(BankFile).join(BankSource, BankSource.key == BankFile.source_key)
        .where(BankQuestion.id.in_(ids), BankQuestion.active.is_(True), BankSource.enabled.is_(True)))}
    missing = [i for i in ids if i not in rows]
    if missing:
        raise HTTPException(400, f'Bu suallar test bazasında yoxdur və ya söndürülüb: {missing[:10]}')
    return [{'bank_id': q.id, 'source': f.source_key, 'lesson': f.label, 'kind': q.kind, 'text': q.text,
             'options': q.options, 'correct': q.correct, 'answer': q.answer, 'image': q.image,
             'explanation': q.explanation} for q, f in (rows[i] for i in ids)]


RAW_KEYS = ('bank_id', 'source', 'lesson', 'kind', 'text', 'options', 'correct', 'answer', 'image', 'explanation', 'edited')


def custom_snapshot(q: 'CustomQ') -> dict:
    d = _custom_snapshot(q)
    d.pop('points', None)                       # bal yenidən hesablanır (çətinlik dəyişə bilər)
    if q.difficulty:
        d['difficulty'] = q.difficulty
    return d


def _custom_snapshot(q: 'CustomQ') -> dict:
    if q.raw and q.raw.get('kind') in ('mcq', 'open') and isinstance(q.raw.get('text'), dict):
        return {k: q.raw[k] for k in RAW_KEYS if k in q.raw}
    return {'bank_id': q.bank_id, 'source': q.source or 'müəllim', 'lesson': q.lesson, 'kind': q.kind,
            'text': {'az': q.text}, 'options': [{'az': o} for o in q.options] if q.options else None,
            'correct': q.correct if q.kind == 'mcq' else None, 'answer': q.answer if q.kind == 'open' else None,
            'image': q.image, 'explanation': {'az': q.explanation} if q.explanation else None, 'edited': True}


def task_out(t: OnlineTask) -> dict:
    return {'id': t.id, 'ta_id': t.assignment_id, 'title': t.title, 'description': t.description, 'opens_at': aware(t.opens_at),
            'closes_at': aware(t.closes_at), 'duration_min': t.duration_min, 'questions': len(t.questions),
            'shuffle': t.shuffle, 'show_answers': t.show_answers, 'student_ids': t.student_ids,
            'archived': t.archived_at is not None, 'kind': t.kind, 'batch_id': t.batch_id,
            'plan_lesson_id': t.plan_lesson_id, 'journal_auto': bool(t.journal_auto),
            'journal_done_at': aware(t.journal_done_at) if t.journal_done_at else None,
            'created_at': aware(t.created_at) if t.created_at else None}   # kim/nə vaxt – təsadüfi yaradılanı tanımaq üçün


def exam_batch(db: Session, ta: TeachingAssignment, title: str, user: User) -> TestBatch:
    """Plandan kənar test «Sınaq imtahanları»na düşür: hər biri öz sınaq paketi ilə."""
    from ..models import SchoolClass
    b = TestBatch(kind='sinaq', title=title, subject=ta.subject, grade=class_grade(db, db.get(SchoolClass, ta.class_id)),
                  created_by=user.id)
    db.add(b)
    db.flush()
    return b


class ScaleIn(BaseModel):
    t3: int = Field(ge=1, le=100)
    t4: int = Field(ge=1, le=100)
    t5: int = Field(ge=1, le=100)


@router.get('/formative-scale/{ta_id}')
def get_scale(ta_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Sinfin formativ şkalası (mövzu testi): qiymət «3/4/5» üçün alt hədd, %."""
    ta = own_assignment(db, user, ta_id)
    sc = normalize_scale((ta.cert_rules or {}).get('formative_scale'))
    return {'t3': sc[3], 't4': sc[4], 't5': sc[5], 'default': sc == FORMATIVE_SCALE}


@router.put('/formative-scale/{ta_id}')
def set_scale(ta_id: int, body: ScaleIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Şkalanı saxlayır. Köhnə cəhdlər dəyişmir: yalnız yeni təhvil və yenidən qiymətləndirmə."""
    ta = own_assignment(db, user, ta_id)
    sc = {3: body.t3, 4: body.t4, 5: body.t5}
    err = validate_scale(sc)
    if err:
        raise HTTPException(422, err)
    ta.cert_rules = {**(ta.cert_rules or {}), 'formative_scale': {str(k): v for k, v in sc.items()}}
    audit(db, user, 'update', 'teaching_assignment', ta.id, formative_scale=ta.cert_rules['formative_scale'])
    db.commit()
    return get_scale(ta_id, user, db)


@router.delete('/formative-scale/{ta_id}')
def reset_scale(ta_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """«Defolta qaytar» (KSQ şkalası 31/61/81)."""
    ta = own_assignment(db, user, ta_id)
    rules = {k: v for k, v in (ta.cert_rules or {}).items() if k != 'formative_scale'}
    ta.cert_rules = rules or None
    audit(db, user, 'update', 'teaching_assignment', ta.id, formative_scale=None)
    db.commit()
    return get_scale(ta_id, user, db)


@router.post('/{ta_id}')
def create_task(ta_id: int, body: TaskIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    if body.student_ids is not None:
        bad = set(body.student_ids) - {s.id for s in roster(db, ta)}
        if bad or not body.student_ids:
            raise HTTPException(400, 'Şagirdlər bu sinifdən/qrupdan seçilməlidir')
    qs = _snapshot(db, body.bank_ids) + [custom_snapshot(q) for q in body.custom]
    b = exam_batch(db, ta, body.title, user)          # perspektiv plana bağlı olmayan test – sınaq
    t = OnlineTask(assignment_id=ta.id, title=body.title, description=body.description,
                   opens_at=aware(body.opens_at), closes_at=closes_or_none(body.closes_at), duration_min=body.duration_min,
                   questions=qs, shuffle=body.shuffle, show_answers=body.show_answers,
                   student_ids=body.student_ids, created_by=user.id, kind='sinaq', batch_id=b.id)
    db.add(t)
    db.flush()
    audit(db, user, 'create', 'task', t.id, questions=len(qs), kind='sinaq', batch=b.id)
    db.commit()
    return task_out(t)


def expire_many(db: Session, tasks: list[OnlineTask]) -> None:
    """expire_due – bir sorğu ilə bir neçə tapşırıq üçün (siyahılar hər test üçün ayrıca sorğu etməsin)."""
    by_id = {t.id: t for t in tasks}
    if not by_id:
        return
    t0, changed = now(), False
    for a in db.scalars(select(TaskAttempt).where(TaskAttempt.task_id.in_(list(by_id)), TaskAttempt.submitted_at.is_(None))):
        if aware(a.deadline) <= t0:
            finalize(db, by_id[a.task_id], a, t0, auto=True)
            changed = True
    if changed:
        db.commit()


@router.get('/mine')
def my_tasks(archived: bool = False, kind: str = 'movzu', user: User = Depends(staff), db: Session = Depends(get_db)):
    """Bütün dərslərimin testləri bir siyahıda (sinif seçmədən): sinif adı, mövzu, təhvil sayı və orta faiz."""
    from ..models import SchoolClass
    from ..services import ws_cond
    tas = {ta.id: ta for ta in db.scalars(select(TeachingAssignment).where(
        TeachingAssignment.teacher_id == user.id, TeachingAssignment.archived_at.is_(None), ws_cond(user)))}
    if not tas:
        return []
    flt = OnlineTask.archived_at.is_not(None) if archived else OnlineTask.archived_at.is_(None)
    tasks = list(db.scalars(select(OnlineTask).where(OnlineTask.assignment_id.in_(list(tas)), OnlineTask.kind == kind, flt)
                            .order_by(OnlineTask.opens_at.desc())))
    expire_many(db, tasks)
    names = {c.id: c.name for c in db.scalars(select(SchoolClass).where(SchoolClass.id.in_({ta.class_id for ta in tas.values()})))}
    stats: dict[int, list] = {}
    for a in db.scalars(select(TaskAttempt).where(TaskAttempt.task_id.in_([t.id for t in tasks] or [-1]),
                                                  TaskAttempt.submitted_at.is_not(None))):
        if a.total:
            stats.setdefault(a.task_id, []).append(apct(a))
    pls = {p.id: p for p in db.scalars(select(PlanLesson).where(
        PlanLesson.id.in_({t.plan_lesson_id for t in tasks if t.plan_lesson_id} or {-1})))}
    from ..task_groups import group_tasks
    gmap = {i: g for g in group_tasks(tasks) for i in g['task_ids']}       # eyni testin yenidən göndərişləri – bir qrup (görünüş üçün)
    out = []
    for t in tasks:
        ta, v, pl = tas[t.assignment_id], stats.get(t.id, []), pls.get(t.plan_lesson_id)
        g = gmap[t.id]
        out.append({**task_out(t), 'group_key': g['group_key'], 'group_sends': g['sends'], 'group_main_id': g['main_task_id'],
                    'ta_id': ta.id, 'class_name': names.get(ta.class_id), 'subject': ta.subject,
                    'submitted': len(v), 'avg_pct': round(sum(v) / len(v), 1) if v else None,
                    'topic': pl and {'seq': pl.seq, 'topic': pl.topic}})
    return out


@router.get('/{ta_id}')
def list_tasks(ta_id: int, archived: bool = False, user: User = Depends(staff), db: Session = Depends(get_db)):
    """archived=true – silinmiş (arxivdəki) testlər: geri qaytarmaq və ya yenidən göndərmək üçün."""
    ta = own_assignment(db, user, ta_id)
    out = []
    flt = OnlineTask.archived_at.is_not(None) if archived else OnlineTask.archived_at.is_(None)
    for t in db.scalars(select(OnlineTask).where(OnlineTask.assignment_id == ta.id, flt,
                                                 (OnlineTask.kind.is_(None)) | (OnlineTask.kind.not_in(('ksq', 'sehv'))))   # onlayn KSQ – KSQ səhifəsində; «Səhvlər üzərində iş» – şagirdin şəxsi işi
                        .order_by(OnlineTask.opens_at.desc())):
        expire_due(db, t)
        done = [a for a in db.scalars(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.submitted_at.is_not(None)))
                if a.total]                           # sualsız (boş) tapşırıq ortanı sıfıra bölməsin
        pl = db.get(PlanLesson, t.plan_lesson_id) if t.plan_lesson_id else None
        out.append({**task_out(t), 'submitted': len(done), 'topic': pl and {'seq': pl.seq, 'topic': pl.topic},
                    'avg_pct': round(sum(apct(a) for a in done) / len(done), 1) if done else None})
    return out


def mistake_work_of(db: Session, t: OnlineTask, sid: int, a: TaskAttempt | None) -> dict | None:
    """Müəllim sətrinə: «Səhv üzərində iş: 3/5» (yalnız şagird bitiribsə)."""
    if t.kind != 'movzu' or not a or not a.submitted_at:
        return None
    from ..mistake_work import result_of
    r = result_of(db, t, sid)
    return r if r and r['done'] else None


@router.get('/{ta_id}/{task_id}')
def task_results(ta_id: int, task_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    t = get_or_404(db, OnlineTask, task_id, 'Tapşırıq')
    if t.assignment_id != ta.id:
        raise HTTPException(404, 'Tapşırıq tapılmadı')
    expire_due(db, t)
    atts = {a.student_id: a for a in db.scalars(select(TaskAttempt).where(TaskAttempt.task_id == t.id))}
    targets = [s for s in roster(db, ta) if t.student_ids is None or s.id in t.student_ids]
    pen, sinaq = penalty_of(db, t), t.kind == 'sinaq'      # sınaq: faiz cərimə ilə, qiymət yox – sınaq jurnalı ilə eyni
    rows = []
    for s in targets:
        a = atts.get(s.id)
        status = 'başlamayıb' if not a else ('təhvil verib' if a.submitted_at else 'həll edir')
        answered = sum(1 for v in (a.answers or {}).values() if v not in (None, '')) if a else 0
        rows.append({'student_id': s.id, 'full_name': s.full_name, 'portal_code': s.portal_code, 'status': status,
                     'answered': answered, 'started_at': aware(a.started_at) if a else None,
                     'deadline': aware(a.deadline) if a else None,
                     'submitted_at': aware(a.submitted_at) if a and a.submitted_at else None,
                     'auto_submitted': bool(a and a.auto_submitted), 'correct': a.correct if a else None,
                     'total': a.total if a else None, 'grade': None if sinaq or not a else a.grade,
                     'pct': (exam_score(t, a, pen)['pct'] if sinaq else round(apct(a), 1))
                     if a and a.submitted_at and a.total else None,
                     'level': None if sinaq or not a or not a.submitted_at or not a.total else level(apct(a)),
                     'solution_at': aware(a.solution_at) if a and a.solution_key and a.solution_at else None,
                     'answers_released_at': aware(a.answers_released_at) if a and a.answers_released_at else None,
                     'mistake_work': mistake_work_of(db, t, s.id, a)})
    done = [a for a in atts.values() if a.submitted_at]
    per_q = []
    for i, q in enumerate(t.questions):
        ok = sum(is_ok(t, a, i) for a in done)
        per_q.append({'index': i, 'text': q['text'], 'kind': q['kind'], 'correct': ok, 'of': len(done),
                      'pct': round(ok * 100 / len(done), 1) if done else None,
                      'distribution': question_distribution(q, i, done)})      # M2: variantların paylanması (mcq), açıq sualda None
    summary = {k: sum(r['status'] == k for r in rows) for k in ('başlamayıb', 'həll edir', 'təhvil verib')}
    return {'task': task_out(t), 'rows': rows, 'questions': per_q, 'summary': summary, 'server_time': now()}


@router.get('/{ta_id}/{task_id}/solution/{student_id}')
def student_solution(ta_id: int, task_id: int, student_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Şagirdin göndərdiyi həll şəkilləri (bir PDF)."""
    from .portal import solution_response
    ta = own_assignment(db, user, ta_id)
    t = get_or_404(db, OnlineTask, task_id, 'Tapşırıq')
    if t.assignment_id != ta.id:
        raise HTTPException(404, 'Tapşırıq tapılmadı')
    a = db.scalar(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.student_id == student_id))
    st = db.get(Student, student_id)
    return solution_response(db, a, f'{(st.full_name if st else "sagird")} – {t.title}.pdf'[:150])


@router.post('/{ta_id}/{task_id}/archive')
def archive_task(ta_id: int, task_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    own_assignment(db, user, ta_id)
    t = get_or_404(db, OnlineTask, task_id, 'Tapşırıq')
    if t.assignment_id != ta_id:
        raise HTTPException(404, 'Tapşırıq tapılmadı')
    if t.kind == 'sinaq':                         # silinən sınaq sistemdən tam silinir (müəllim və şagird üçün)
        purge_tasks(db, [t])
        audit(db, user, 'delete', 'task', task_id, kind='sinaq')
        db.commit()
        return {'ok': True, 'deleted': True}
    t.archived_at = now()
    _forget(t.batch_id)
    audit(db, user, 'archive', 'task', t.id)
    db.commit()
    return {'ok': True}


@router.delete('/{ta_id}/{task_id}')
def delete_task(ta_id: int, task_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """«Silinənlər»dəki test birdəfəlik silinir – nəticələri və şagird cəhdləri ilə (geri qaytarılmır)."""
    own_assignment(db, user, ta_id)
    t = get_or_404(db, OnlineTask, task_id, 'Tapşırıq')
    if t.assignment_id != ta_id:
        raise HTTPException(404, 'Tapşırıq tapılmadı')
    if t.archived_at is None and t.kind != 'sinaq':
        raise HTTPException(400, 'Əvvəlcə testi silin – sonra «Silinənlər»dən birdəfəlik silmək olar')
    purge_tasks(db, [t])
    audit(db, user, 'delete', 'task', task_id, kind=t.kind)
    db.commit()
    return {'deleted': True}


def purge_tasks(db: Session, tasks: list[OnlineTask]) -> int:
    """Tapşırıqları cəhdləri ilə birlikdə birdəfəlik silir; boş qalan sınaq paketi də silinir."""
    batches = {t.batch_id for t in tasks if t.batch_id}
    _forget(*batches)
    ids = [t.id for t in tasks]
    if not ids:
        return 0
    db.execute(delete(TaskAttempt).where(TaskAttempt.task_id.in_(ids)))
    db.execute(update(Mark).where(Mark.task_id.in_(ids)).values(task_id=None))
    for t in tasks:
        db.delete(t)
    db.flush()
    for bid in batches:
        b = db.get(TestBatch, bid)
        if b and b.kind == 'sinaq' and db.scalar(select(OnlineTask.id).where(OnlineTask.batch_id == bid)) is None:
            db.delete(b)
    return len(ids)


@router.post('/{ta_id}/{task_id}/restore')
def restore_task(ta_id: int, task_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Silinmiş testi geri qaytarır (nəticələr və cəhdlər itmir)."""
    own_assignment(db, user, ta_id)
    t = get_or_404(db, OnlineTask, task_id, 'Tapşırıq')
    if t.assignment_id != ta_id:
        raise HTTPException(404, 'Tapşırıq tapılmadı')
    t.archived_at = None
    _forget(t.batch_id)
    audit(db, user, 'restore', 'task', t.id)
    db.commit()
    return task_out(t)


class CopyIn(BaseModel):
    target_ta_id: int                              # eyni və ya başqa sinif/qrup (müəllimin öz dərsi)
    opens_at: dt.datetime
    closes_at: dt.datetime | None = None                     # boş – son tarix yoxdur
    duration_min: TestMinutes | None = None                  # boş – əvvəlki müddət; 0 – taymer yoxdur
    title: str | None = Field(None, min_length=2, max_length=200)
    student_ids: list[int] | None = None           # boş – bütün sinif/qrup
    unlimited: bool = False                                  # müddətsiz: taymer və son tarix yoxdur (KSQ/BSQ istisna)


@router.post('/{ta_id}/{task_id}/copy')
def copy_task(ta_id: int, task_id: int, body: CopyIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Yenidən göndər: testin surəti (eyni suallar) yeni vaxtla həmin və ya başqa sinfə. Köhnə nəticələr yerində qalır,
    şagirdlər yeni testi təzədən həll edir. Silinmiş testdən də surət çıxarmaq olar."""
    own_assignment(db, user, ta_id)
    src = get_or_404(db, OnlineTask, task_id, 'Tapşırıq')
    if src.assignment_id != ta_id:
        raise HTTPException(404, 'Tapşırıq tapılmadı')
    target = own_assignment(db, user, body.target_ta_id)
    o, c = aware(body.opens_at), closes_or_none(body.closes_at)
    dur = body.duration_min if body.duration_min is not None else (max(src.duration_min, MIN_TEST_MIN) if src.duration_min else 0)
    if src.kind == 'ksq':                          # KSQ/BSQ müddətsiz olmur: həmişə 45 dəq və son tarix
        if body.closes_at is None:
            raise HTTPException(400, 'KSQ/BSQ üçün bağlanma vaxtı seçin')
        dur = MIN_TEST_MIN
    elif body.unlimited or (is_unlimited(src) and body.closes_at is None and body.duration_min is None):
        c, dur = NO_DEADLINE, 0                    # müddətsiz mənbənin surəti də müddətsizdir (timing.py)
    if c <= o:
        raise HTTPException(400, 'Bağlanma vaxtı açılmadan sonra olmalıdır')
    if c <= now():
        raise HTTPException(400, 'Bağlanma vaxtı keçmişdədir – gələcək vaxt seçin')
    if not fits_window(dur, o, c):
        raise HTTPException(400, f'Həll müddəti ({dur} dəq) açıq qalma aralığından uzun ola bilməz')
    if body.student_ids is not None:
        bad = set(body.student_ids) - {x.id for x in roster(db, target)}
        if bad or not body.student_ids:
            raise HTTPException(400, 'Şagirdlər seçilən sinifdən/qrupdan olmalıdır')
    title = body.title or src.title
    pl_id = _target_topic(db, src, target) if src.kind == 'movzu' else None
    if pl_id:                                     # mövzu testi – hədəf sinfin planında həmin mövzuya
        kind, batch_id = 'movzu', None
    elif src.kind == 'sinaq' and src.batch_id and db.get(TestBatch, src.batch_id):
        kind, batch_id = 'sinaq', src.batch_id      # yenidən göndərilən sınaq – EYNİ sınaq (yeni paket yox: təkrar sətir olmasın)
        _forget(batch_id)
    else:                                         # plandan kənar – sınaq
        kind, batch_id = 'sinaq', exam_batch(db, target, title, user).id
    t = OnlineTask(assignment_id=target.id, title=title, description=src.description,
                   opens_at=o, closes_at=c, duration_min=dur, questions=copy.deepcopy(src.questions),
                   shuffle=src.shuffle, show_answers=src.show_answers, student_ids=body.student_ids, created_by=user.id,
                   kind=kind, batch_id=batch_id, plan_lesson_id=pl_id)
    db.add(t)
    db.flush()
    audit(db, user, 'create', 'task', t.id, copied_from=src.id, target_ta=target.id)
    db.commit()
    return task_out(t)


def _target_topic(db: Session, src: OnlineTask, target: TeachingAssignment) -> int | None:
    """Mövzu testinin surəti: həmin dərsdə – eyni mövzu, başqa sinifdə – planda eyni adlı mövzu."""
    from .topic_tests import norm_topic
    pl = db.get(PlanLesson, src.plan_lesson_id) if src.plan_lesson_id else None
    if not pl:
        return None
    if target.id == src.assignment_id:
        return pl.id
    key = norm_topic(pl.topic)
    return next((x.id for x in db.scalars(select(PlanLesson).where(PlanLesson.assignment_id == target.id)
                                          .order_by(PlanLesson.seq)) if norm_topic(x.topic) == key), None)


@router.delete('/{ta_id}/{task_id}/attempts/{student_id}')
def reset_attempt(ta_id: int, task_id: int, student_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Bir şagirdə təkrar icazə: cəhdi silinir, test açıq olduğu müddətdə yenidən başlaya bilər."""
    t = _own_task(db, user, ta_id, task_id)
    if now() >= aware(t.closes_at):
        raise HTTPException(409, 'Test bağlanıb – şagirdə «Yenidən göndər» ilə yeni vaxt verin')
    a = db.scalar(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.student_id == student_id))
    if not a:
        raise HTTPException(404, 'Şagird bu testə başlamayıb')
    db.delete(a)
    _forget(t.batch_id)
    for m in db.scalars(select(Mark).where(Mark.task_id == t.id, Mark.student_id == student_id)):
        db.delete(m)                                  # mövzu testindən jurnala yazılmış qiymət də götürülür
    audit(db, user, 'delete', 'task_attempt', t.id, student_id=student_id)
    db.commit()
    return {'ok': True}


class ResumeIn(BaseModel):
    minutes: int | None = Field(None, ge=5, le=300)        # boş – testin istifadə olunmamış vaxtı (ən azı 10 dəq)


def _resume(db: Session, t: OnlineTask, a: TaskAttempt, minutes: int | None = None) -> int:
    """Cəhdi yenidən açır: cavablar saxlanır, qalan vaxt (və ya verilən dəqiqə), jurnal qiyməti silinir (təhvildə yenidən)."""
    at = now()
    used = ((aware(a.submitted_at) if a.submitted_at else min(at, aware(a.deadline))) - aware(a.started_at)).total_seconds() / 60
    a.submitted_at, a.auto_submitted = None, False
    a.correct = a.total = a.grade = a.points = None
    if no_timer(t) and not minutes:                       # müddətsiz test – yenə müddətsiz davam edir
        a.deadline = aware(t.closes_at)
        _forget(t.batch_id)
        for m in db.scalars(select(Mark).where(Mark.task_id == t.id, Mark.student_id == a.student_id)):
            db.delete(m)
        return 0
    minutes = minutes or max(10, round(t.duration_min - used))
    a.deadline = at + dt.timedelta(minutes=minutes)
    _forget(t.batch_id)
    for m in db.scalars(select(Mark).where(Mark.task_id == t.id, Mark.student_id == a.student_id)):
        db.delete(m)
    return minutes


@router.post('/{ta_id}/{task_id}/resume-all')
def resume_all(ta_id: int, task_id: int, body: ResumeIn | None = None, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Bütün sinif üçün «Davam etsin»: başlamış hər şagirdin cəhdi açılır (hərəyə öz qalan vaxtı), cavablar saxlanır."""
    t = _own_task(db, user, ta_id, task_id)
    at = now()
    n = 0
    for a in db.scalars(select(TaskAttempt).where(TaskAttempt.task_id == t.id)):
        if a.submitted_at or at >= aware(a.deadline):
            _resume(db, t, a, body.minutes if body else None)
            n += 1
    audit(db, user, 'update', 'online_task', t.id, resume_all=n)
    db.commit()
    return {'ok': True, 'resumed': n}


@router.post('/{ta_id}/{task_id}/attempts/{student_id}/resume')
def resume_attempt(ta_id: int, task_id: int, student_id: int, body: ResumeIn | None = None, user: User = Depends(staff),
                   db: Session = Depends(get_db)):
    """«Davam etsin»: şagird testdən təsadüfən çıxıb (vaxt bitdi / təhvil getdi) — cəhd yenidən açılır, CAVABLARI SAXLANIR,
    yeni müddət verilir; test bağlanıbsa da yalnız bu şagird üçün işləyir. Nəticə təhvildə yenidən hesablanır."""
    t = _own_task(db, user, ta_id, task_id)
    a = db.scalar(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.student_id == student_id))
    if not a:
        raise HTTPException(404, 'Şagird bu testə başlamayıb – «Yenidən göndər» istifadə edin')
    minutes = _resume(db, t, a, body.minutes if body else None)
    audit(db, user, 'update', 'task_attempt', t.id, student_id=student_id, resume_minutes=minutes)
    db.commit()
    return {'ok': True, 'deadline': aware(a.deadline), 'minutes': minutes, 'answers': len(a.answers or {})}


def _own_task(db: Session, user: User, ta_id: int, task_id: int) -> OnlineTask:
    ta = own_assignment(db, user, ta_id)
    t = get_or_404(db, OnlineTask, task_id, 'Tapşırıq')
    if t.assignment_id != ta.id or t.archived_at:
        raise HTTPException(404, 'Tapşırıq tapılmadı')
    return t


class ToJournalIn(BaseModel):
    date: dt.date | None = None          # boş – testin açıldığı gün (Bakı vaxtı)
    period: int | None = Field(None, ge=0, le=9)
    unlock_reason: str | None = Field(None, max_length=300)   # admin: bağlanmış yarımildə köçürmə səbəbi


@router.post('/{ta_id}/{task_id}/to-journal')
def to_journal(ta_id: int, task_id: int, body: ToJournalIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Onlayn testin nəticəsi bir düymə ilə formativ «test» qiyməti kimi jurnala: düzgün / sual → faiz → qiymət.
    Seçilən dərsdə qayıb/üzrlü olan şagird ötürülür; KSQ/BSQ dərsinə və gələcək dərsə köçürülmür."""
    from zoneinfo import ZoneInfo
    from ..domain.plan import slot_at
    from ..models import Attendance, JournalEntry, Mark
    from ..services import SCHOOL_TZ, plan_ctx, taught_lesson, today
    from .journal import SUMMATIVE, check_open
    t = _own_task(db, user, ta_id, task_id)
    if t.kind == 'extra':
        raise HTTPException(400, 'Əlavə məşğələ testi jurnala köçürülmür – nəticə məşğələ statistikasındadır')
    if t.kind == 'sinaq':
        raise HTTPException(400, 'Sınaq imtahanının nəticəsi formativ jurnala köçürülmür – «Sınaq jurnalı»nda və reytinqdədir')
    if t.kind == 'movzu' and t.plan_lesson_id and body.date is None:   # mövzu testi – mövzunun öz dərsinə
        from ..task_journal import write_topic_marks
        expire_due(db, t)
        r = write_topic_marks(db, t, by=user.id)
        if r['status'] != 'yazıldı':
            raise HTTPException(400, f'Jurnala yazılmadı: {r["status"]} – dərsi (tarix və saat) özünüz seçin')
        db.commit()
        return {'date': r['date'], 'period': r['period'], 'topic': r['topic'], 'copied': r['copied'],
                'updated': r['updated'], 'skipped': r['skipped']}
    ta = db.get(TeachingAssignment, t.assignment_id)
    ctx = plan_ctx(db, ta)
    d = body.date or aware(t.opens_at).astimezone(ZoneInfo(SCHOOL_TZ)).date()
    day = [s for s in ctx.slots if s.date == d]
    s = slot_at(ctx.slots, d, body.period) if body.period is not None else (day[0] if day else None)
    if not s:
        raise HTTPException(400, f'{d:%d.%m.%Y} tarixində bu sinifdə dərs yoxdur – dərsi (tarix və saat) seçin')
    if d > today():
        raise HTTPException(400, 'Gələcək dərsə qiymət yazılmır')
    unlock = check_open(ctx.year, d, user, body.unlock_reason)         # bağlanmış yarımil: yalnız admin + səbəb
    e = db.scalar(select(JournalEntry).where(JournalEntry.assignment_id == ta.id, JournalEntry.date == d,
                                             JournalEntry.period == s.period))
    pl = taught_lesson(ctx, s, e)
    if pl and pl.assessment_type in SUMMATIVE:
        raise HTTPException(400, f'{pl.assessment_type} dərsinə formativ qiymət köçürülmür – başqa dərs seçin')
    if e is None:
        e = JournalEntry(assignment_id=ta.id, date=d, period=s.period, plan_lesson_id=pl.id if pl else None, auto=True)
        db.add(e)
        db.flush()
    out_ids = {a.student_id for a in db.scalars(select(Attendance).where(
        Attendance.entry_id == e.id, Attendance.status.in_(('yox', 'üzrlü'))))}
    names = {x.id: x.full_name for x in roster(db, ta)}
    copied, updated, skipped = 0, 0, []
    for a in db.scalars(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.submitted_at.is_not(None))):
        if a.student_id not in names or not a.total:
            continue
        if a.student_id in out_ids:
            skipped.append({'full_name': names[a.student_id], 'reason': 'həmin dərsdə olmayıb'})
            continue
        m = db.scalar(select(Mark).where(Mark.entry_id == e.id, Mark.student_id == a.student_id, Mark.kind == 'test'))
        if m:
            updated += 1
        else:
            m = Mark(entry_id=e.id, student_id=a.student_id, kind='test')
            db.add(m)
            copied += 1
        m.test_correct, m.test_total = a.correct, a.total
        m.grade = formative_grade(apct(a), class_scale(t)) if formative_kind(t) else summative_grade(apct(a))
        m.comment, m.task_id = f'Onlayn test: {t.title}'[:300], t.id
    audit(db, user, 'update', 'journal', e.id, from_task=t.id, copied=copied, updated=updated, **({'unlock_reason': unlock} if unlock else {}))
    db.commit()
    return {'date': d, 'period': s.period, 'topic': (e.topic or (pl.topic if pl else None)), 'copied': copied,
            'updated': updated, 'skipped': skipped}


@router.get('/{ta_id}/{task_id}/full')
def task_full(ta_id: int, task_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Redaktə üçün: tapşırıq + sualların tam surəti (düzgün cavablarla – yalnız müəllimə)."""
    t = _own_task(db, user, ta_id, task_id)
    started = db.scalar(select(func.count()).select_from(TaskAttempt).where(TaskAttempt.task_id == t.id)) or 0
    return {**task_out(t), 'questions_full': t.questions, 'started': started}


class TaskPatch(BaseModel):
    title: str | None = Field(None, min_length=2, max_length=200)
    description: str | None = Field(None, max_length=2000)
    opens_at: dt.datetime | None = None
    closes_at: dt.datetime | None = None
    duration_min: TestMinutes | None = None
    unlimited_deadline: bool = False             # True – son tarix yoxdur (closes_at = NO_DEADLINE)
    shuffle: bool | None = None
    show_answers: Literal['after_close', 'after_submit', 'never', 'teacher'] | None = None
    student_ids: list[int] | None = None
    all_students: bool = False                   # True – «hamı» (student_ids = None)
    questions: list[CustomQ] | None = None       # tam siyahı (yalnız heç kim başlamayıbsa)


@router.patch('/{ta_id}/{task_id}')
def update_task(ta_id: int, task_id: int, body: TaskPatch, user: User = Depends(staff), db: Session = Depends(get_db)):
    t = _own_task(db, user, ta_id, task_id)
    ta = db.get(TeachingAssignment, t.assignment_id)
    data = body.model_dump(exclude_unset=True)
    o = aware(body.opens_at) if body.opens_at else aware(t.opens_at)
    c = aware(body.closes_at) if body.closes_at else aware(t.closes_at)
    if body.unlimited_deadline:
        c = NO_DEADLINE
    d = body.duration_min if body.duration_min is not None else t.duration_min
    if c <= o:
        raise HTTPException(400, 'Bağlanma vaxtı açılmadan sonra olmalıdır')
    if not fits_window(d, o, c):
        raise HTTPException(400, 'Həll müddəti açıq qalma aralığından uzun ola bilməz')
    if body.questions is not None:
        # sınaq paketi: suallar bütün siniflərdə eyni olmalıdır (jurnal, sual analizi, reytinq) – birlikdə dəyişir
        same = list(db.scalars(select(OnlineTask).where(OnlineTask.batch_id == t.batch_id))) \
            if t.kind == 'sinaq' and t.batch_id else [t]
        if db.scalar(select(func.count()).select_from(TaskAttempt).where(TaskAttempt.task_id.in_([x.id for x in same]))):
            raise HTTPException(409, 'Şagirdlər artıq başlayıb – suallar dəyişdirilə bilməz (ad və vaxt dəyişə bilər)'
                                if len(same) == 1 else 'Bu sınağa başqa sinifdə artıq başlayıblar – suallar dəyişdirilə bilməz')
        if not body.questions or len(body.questions) > 100:
            raise HTTPException(400, '1–100 sual olmalıdır')
        qs = [custom_snapshot(q) for q in body.questions]
        for x in same:
            x.questions = prepare_points(db.connection(), copy.deepcopy(qs))   # 100 bal yenidən
    if body.all_students:
        t.student_ids = None
    elif 'student_ids' in data and body.student_ids is not None:
        if not body.student_ids or set(body.student_ids) - {s.id for s in roster(db, ta)}:
            raise HTTPException(400, 'Şagirdlər bu sinifdən/qrupdan seçilməlidir')
        # testə başlamış şagirdi auditoriyadan çıxarmaq olmaz – nəticəsi siyahıdan itər
        before = set(t.student_ids) if t.student_ids is not None else {s.id for s in roster(db, ta)}
        gone = before - set(body.student_ids)
        started = [db.get(Student, a.student_id) for a in db.scalars(select(TaskAttempt).where(
            TaskAttempt.task_id == t.id, TaskAttempt.student_id.in_(gone)))] if gone else []
        if started:
            raise HTTPException(409, f'{", ".join(s.full_name for s in started if s)} artıq başlayıb – çıxarmaq olmaz (nəticəsi itər)')
        t.student_ids = body.student_ids
    for k in ('title', 'description', 'duration_min', 'shuffle', 'show_answers'):
        if k in data and data[k] is not None:
            setattr(t, k, data[k])
    if c != aware(t.closes_at):
        t.journal_done_at = None                      # yeni bitmə vaxtında jurnala yenidən yazılsın
        clamp_open_attempts(db, t, c)
    t.opens_at, t.closes_at = o, c
    _forget(t.batch_id)
    audit(db, user, 'update', 'task', t.id, fields=sorted(data))
    db.commit()
    return task_out(t)


def clamp_open_attempts(db: Session, t: OnlineTask, closes: dt.datetime) -> None:
    """Müddətsiz testə yeni bağlanma vaxtı qoyulanda: təhvil verilməmiş cəhdlər də həmin vaxtda bitir."""
    for a in db.scalars(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.submitted_at.is_(None))):
        if aware(a.deadline) > closes:
            a.deadline = closes


def close_task(db: Session, t: OnlineTask) -> int:
    """Müəllim testi əl ilə bağlayır (closes_at = indi): yarımçıq cəhdlər avtomatik təhvil verilir. Qaytarır: təhvil sayı."""
    at = now()
    t.closes_at = at
    t.journal_done_at = None
    clamp_open_attempts(db, t, at)
    n = 0
    for a in db.scalars(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.submitted_at.is_(None))):
        finalize(db, t, a, at, auto=True)
        n += 1
    _forget(t.batch_id)
    return n


@router.post('/{ta_id}/{task_id}/close')
def close_one(ta_id: int, task_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """«Bağla»: test dərhal bağlanır (müddətsiz testi bitirmək üçün də)."""
    t = _own_task(db, user, ta_id, task_id)
    if t.kind == 'ksq':
        raise HTTPException(400, 'KSQ/BSQ bu yolla bağlanmır')
    n = close_task(db, t)
    audit(db, user, 'update', 'online_task', t.id, closed=True, auto_submitted=n)
    db.commit()
    return {'ok': True, 'auto_submitted': n}


# ---------------------------------------------------------------- səliqə (miqrasiya f7b9d1e3a5c8)
def tidy_tasks(bind, at: dt.datetime | None = None) -> dict:
    """Köhnə mövzu testləri və sınaqlar:
    1) bağlanmamışların həll müddəti ən azı 45 dəq (açıq qalma aralığı imkan verdikcə), sınaq seriyaları da;
    2) təkrarlar – eyni sinif, növ, mövzu, ad, suallar və şagirdlər: heç kimin başlamadığı surətlər silinir
       (nəticəsi olan test HEÇ VAXT silinmir; qalan – ən çox cəhdi olan, bərabərdirsə ən köhnəsi)."""
    import json
    import sqlalchemy as sa
    t0 = at or now()

    def ts(v):
        if v is None or isinstance(v, dt.datetime):
            return aware(v) if v else None
        return aware(dt.datetime.fromisoformat(str(v)))

    def js(v):
        return json.loads(v) if isinstance(v, str) else v

    out = {'duration': 0, 'series': 0, 'deleted': 0, 'kept_with_results': 0}
    rows = bind.execute(sa.text("SELECT id, assignment_id, kind, plan_lesson_id, title, questions, student_ids, opens_at, "
                                "closes_at, duration_min FROM online_tasks WHERE kind IN ('movzu', 'sinaq') "
                                "AND archived_at IS NULL")).fetchall()
    for r in rows:
        o, c = ts(r.opens_at), ts(r.closes_at)
        if c and t0 < c < NO_DEADLINE and 0 < r.duration_min < MIN_TEST_MIN:   # müddətsiz (0) testlərə toxunulmur
            new = min(MIN_TEST_MIN, int((c - o).total_seconds() // 60))
            if new > r.duration_min:
                bind.execute(sa.text('UPDATE online_tasks SET duration_min = :d WHERE id = :i'), {'d': new, 'i': r.id})
                out['duration'] += 1
    out['series'] = bind.execute(sa.text('UPDATE exam_series SET duration_min = :d WHERE duration_min < :d AND window_hours * 60 >= :d'),
                                 {'d': MIN_TEST_MIN}).rowcount or 0
    att = {k: n for k, n in bind.execute(sa.text('SELECT task_id, COUNT(*) FROM task_attempts GROUP BY task_id')).fetchall()}
    groups: dict[tuple, list] = {}
    for r in rows:
        qs = js(r.questions) or []
        sig = tuple(q.get('bank_id') or json.dumps(q.get('text'), ensure_ascii=False, sort_keys=True) for q in qs if isinstance(q, dict))
        sids = tuple(sorted(js(r.student_ids) or [])) if r.student_ids is not None else None
        key = (r.assignment_id, r.kind, r.plan_lesson_id, (r.title or '').strip().casefold(), sig, sids)
        groups.setdefault(key, []).append(r)
    drop, batches = [], set()
    for g in groups.values():
        if len(g) < 2:
            continue
        g.sort(key=lambda r: (-att.get(r.id, 0), r.id))
        for r in g[1:]:
            if att.get(r.id):
                out['kept_with_results'] += 1
            else:
                drop.append(r.id)
    if drop:
        for bid, in bind.execute(sa.text('SELECT DISTINCT batch_id FROM online_tasks WHERE id IN :ids AND batch_id IS NOT NULL')
                                 .bindparams(sa.bindparam('ids', expanding=True)), {'ids': drop}).fetchall():
            batches.add(bid)
        bind.execute(sa.text('UPDATE marks SET task_id = NULL WHERE task_id IN :ids').bindparams(sa.bindparam('ids', expanding=True)), {'ids': drop})
        bind.execute(sa.text('DELETE FROM online_tasks WHERE id IN :ids').bindparams(sa.bindparam('ids', expanding=True)), {'ids': drop})
        for bid in batches:
            if not bind.execute(sa.text('SELECT 1 FROM online_tasks WHERE batch_id = :b LIMIT 1'), {'b': bid}).first():
                bind.execute(sa.text('DELETE FROM test_batches WHERE id = :b'), {'b': bid})
        out['deleted'] = len(drop)
    return out


# ---------------------------------------------------------------- «cavabları müəllim göndərir» (show_answers='teacher')
class ReleaseIn(BaseModel):
    student_ids: list[int] | None = Field(None, max_length=500)       # boş / yox – təhvil verənlərin hamısı


def release_answers(db: Session, t: OnlineTask, student_ids: list[int] | None, release: bool = True) -> dict:
    """Təhvil vermiş cəhdlərdə düzgün cavabları açır / geri alır. Təhvil verməyənlər `not_submitted` siyahısındadır."""
    atts = {a.student_id: a for a in db.scalars(select(TaskAttempt).where(TaskAttempt.task_id == t.id))}
    ids = set(student_ids) if student_ids else None
    n, missing = 0, []
    if ids is None:
        ids = {i for i, a in atts.items() if a.submitted_at}
    for st in db.scalars(select(Student).where(Student.id.in_(ids or [0]))):
        a = atts.get(st.id)
        if not a or not a.submitted_at:
            missing.append(st.full_name)
            continue
        a.answers_released_at = now() if release else None
        n += 1
    return {'released' if release else 'withdrawn': n, 'not_submitted': sorted(missing)}


@router.post('/{ta_id}/{task_id}/release-answers')
def release_answers_ep(ta_id: int, task_id: int, body: ReleaseIn | None = None, user: User = Depends(staff), db: Session = Depends(get_db)):
    t = _own_task(db, user, ta_id, task_id)
    res = release_answers(db, t, body.student_ids if body else None)
    audit(db, user, 'update', 'task', t.id, release_answers=res['released'])
    db.commit()
    return res


@router.delete('/{ta_id}/{task_id}/release-answers')
def withdraw_answers_ep(ta_id: int, task_id: int, body: ReleaseIn | None = None, user: User = Depends(staff), db: Session = Depends(get_db)):
    t = _own_task(db, user, ta_id, task_id)
    res = release_answers(db, t, body.student_ids if body else None, release=False)
    audit(db, user, 'update', 'task', t.id, withdraw_answers=res['withdrawn'])
    db.commit()
    return res
