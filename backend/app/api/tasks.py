"""Onlayn tapşırıqlar (müəllim): test bazasından və ya öz suallarından, tarix + saat aralığı + həll müddəti.
Məsələn: 29.09.2026 15:00–16:00, müddət 40 dəq. Vaxt bitəndə cavablar avtomatik təhvil verilir (serverdə)."""
from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import staff
from ..domain.answers import check
from ..domain.rules import summative_grade
from ..models import (BankFile, BankQuestion, BankSource, Mark, OnlineTask, PlanLesson, TaskAttempt, TeachingAssignment,
                      TestBatch, User, now)
from ..services import own_assignment, roster
from .common import audit, get_or_404

router = APIRouter(prefix='/api/tasks', tags=['tasks'])


def aware(t: dt.datetime) -> dt.datetime:
    # SQLite tz saxlamır: oxunan vaxt UTC sayılır, yazılan vaxt UTC-yə çevrilir (+04:00 ilə gələn vaxt sürüşməsin)
    return t.astimezone(dt.timezone.utc) if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def is_ok(task: OnlineTask, a: TaskAttempt, i: int) -> bool:
    """Sual düzgündür: müəllimin düzəlişi (açıq sual) avtomatik yoxlamadan üstündür."""
    m = (a.manual or {}).get(str(i))
    return bool(m) if m is not None else check(task.questions[i], (a.answers or {}).get(str(i)))


def score(task: OnlineTask, a: TaskAttempt):
    """Düzgün cavab sayı, faiz və qiymət yenidən hesablanır (düzəlişdən sonra da)."""
    ok = sum(is_ok(task, a, i) for i in range(len(task.questions)))
    a.correct, a.total = ok, len(task.questions)
    a.grade = summative_grade(ok * 100 / a.total) if a.total else None


def finalize(db: Session, task: OnlineTask, a: TaskAttempt, at: dt.datetime | None = None, auto: bool = False):
    """Cavabları yoxlayır və təhvil verir (bir dəfə)."""
    if a.submitted_at:
        return a
    at = at or now()
    score(task, a)
    a.submitted_at, a.auto_submitted = min(at, aware(a.deadline)), auto
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
    closes_at: dt.datetime
    duration_min: int = Field(ge=1, le=300)
    bank_ids: list[int] = Field(default_factory=list)
    custom: list[CustomQ] = Field(default_factory=list)
    shuffle: bool = True
    show_answers: Literal['after_close', 'after_submit', 'never'] = 'after_close'
    student_ids: list[int] | None = None

    @model_validator(mode='after')
    def _v(self):
        o, c = aware(self.opens_at), aware(self.closes_at)
        if c <= o:
            raise ValueError('bağlanma vaxtı açılmadan sonra olmalıdır')
        if self.duration_min > (c - o).total_seconds() / 60:
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
    if q.raw and q.raw.get('kind') in ('mcq', 'open') and isinstance(q.raw.get('text'), dict):
        return {k: q.raw[k] for k in RAW_KEYS if k in q.raw}
    return {'bank_id': q.bank_id, 'source': q.source or 'müəllim', 'lesson': q.lesson, 'kind': q.kind,
            'text': {'az': q.text}, 'options': [{'az': o} for o in q.options] if q.options else None,
            'correct': q.correct if q.kind == 'mcq' else None, 'answer': q.answer if q.kind == 'open' else None,
            'image': q.image, 'explanation': {'az': q.explanation} if q.explanation else None, 'edited': True}


def task_out(t: OnlineTask) -> dict:
    return {'id': t.id, 'title': t.title, 'description': t.description, 'opens_at': aware(t.opens_at),
            'closes_at': aware(t.closes_at), 'duration_min': t.duration_min, 'questions': len(t.questions),
            'shuffle': t.shuffle, 'show_answers': t.show_answers, 'student_ids': t.student_ids,
            'archived': t.archived_at is not None, 'kind': t.kind, 'batch_id': t.batch_id,
            'plan_lesson_id': t.plan_lesson_id, 'journal_auto': bool(t.journal_auto),
            'journal_done_at': aware(t.journal_done_at) if t.journal_done_at else None,
            'created_at': aware(t.created_at) if t.created_at else None}   # kim/nə vaxt – təsadüfi yaradılanı tanımaq üçün


@router.post('/{ta_id}')
def create_task(ta_id: int, body: TaskIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    if body.student_ids is not None:
        bad = set(body.student_ids) - {s.id for s in roster(db, ta)}
        if bad or not body.student_ids:
            raise HTTPException(400, 'Şagirdlər bu sinifdən/qrupdan seçilməlidir')
    qs = _snapshot(db, body.bank_ids) + [custom_snapshot(q) for q in body.custom]
    t = OnlineTask(assignment_id=ta.id, title=body.title, description=body.description,
                   opens_at=aware(body.opens_at), closes_at=aware(body.closes_at), duration_min=body.duration_min,
                   questions=qs, shuffle=body.shuffle, show_answers=body.show_answers,
                   student_ids=body.student_ids, created_by=user.id)
    db.add(t)
    db.flush()
    audit(db, user, 'create', 'task', t.id, questions=len(qs))
    db.commit()
    return task_out(t)


@router.get('/{ta_id}')
def list_tasks(ta_id: int, archived: bool = False, user: User = Depends(staff), db: Session = Depends(get_db)):
    """archived=true – silinmiş (arxivdəki) testlər: geri qaytarmaq və ya yenidən göndərmək üçün."""
    ta = own_assignment(db, user, ta_id)
    out = []
    flt = OnlineTask.archived_at.is_not(None) if archived else OnlineTask.archived_at.is_(None)
    for t in db.scalars(select(OnlineTask).where(OnlineTask.assignment_id == ta.id, flt)
                        .order_by(OnlineTask.opens_at.desc())):
        expire_due(db, t)
        done = [a for a in db.scalars(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.submitted_at.is_not(None)))
                if a.total]                           # sualsız (boş) tapşırıq ortanı sıfıra bölməsin
        pl = db.get(PlanLesson, t.plan_lesson_id) if t.plan_lesson_id else None
        out.append({**task_out(t), 'submitted': len(done), 'topic': pl and {'seq': pl.seq, 'topic': pl.topic},
                    'avg_pct': round(sum(a.correct * 100 / a.total for a in done) / len(done), 1) if done else None})
    return out


@router.get('/{ta_id}/{task_id}')
def task_results(ta_id: int, task_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    t = get_or_404(db, OnlineTask, task_id, 'Tapşırıq')
    if t.assignment_id != ta.id:
        raise HTTPException(404, 'Tapşırıq tapılmadı')
    expire_due(db, t)
    atts = {a.student_id: a for a in db.scalars(select(TaskAttempt).where(TaskAttempt.task_id == t.id))}
    targets = [s for s in roster(db, ta) if t.student_ids is None or s.id in t.student_ids]
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
                     'total': a.total if a else None, 'grade': a.grade if a else None,
                     'pct': round(a.correct * 100 / a.total, 1) if a and a.submitted_at and a.total else None})
    done = [a for a in atts.values() if a.submitted_at]
    per_q = []
    for i, q in enumerate(t.questions):
        ok = sum(is_ok(t, a, i) for a in done)
        per_q.append({'index': i, 'text': q['text'], 'kind': q['kind'], 'correct': ok, 'of': len(done),
                      'pct': round(ok * 100 / len(done), 1) if done else None})
    summary = {k: sum(r['status'] == k for r in rows) for k in ('başlamayıb', 'həll edir', 'təhvil verib')}
    return {'task': task_out(t), 'rows': rows, 'questions': per_q, 'summary': summary, 'server_time': now()}


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
    audit(db, user, 'archive', 'task', t.id)
    db.commit()
    return {'ok': True}


def purge_tasks(db: Session, tasks: list[OnlineTask]) -> int:
    """Tapşırıqları cəhdləri ilə birlikdə birdəfəlik silir; boş qalan sınaq paketi də silinir."""
    batches = {t.batch_id for t in tasks if t.batch_id}
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
    audit(db, user, 'restore', 'task', t.id)
    db.commit()
    return task_out(t)


class CopyIn(BaseModel):
    target_ta_id: int                              # eyni və ya başqa sinif/qrup (müəllimin öz dərsi)
    opens_at: dt.datetime
    closes_at: dt.datetime
    duration_min: int | None = Field(None, ge=1, le=300)    # boş – əvvəlki müddət
    title: str | None = Field(None, min_length=2, max_length=200)
    student_ids: list[int] | None = None           # boş – bütün sinif/qrup


@router.post('/{ta_id}/{task_id}/copy')
def copy_task(ta_id: int, task_id: int, body: CopyIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Yenidən göndər: testin surəti (eyni suallar) yeni vaxtla həmin və ya başqa sinfə. Köhnə nəticələr yerində qalır,
    şagirdlər yeni testi təzədən həll edir. Silinmiş testdən də surət çıxarmaq olar."""
    own_assignment(db, user, ta_id)
    src = get_or_404(db, OnlineTask, task_id, 'Tapşırıq')
    if src.assignment_id != ta_id:
        raise HTTPException(404, 'Tapşırıq tapılmadı')
    target = own_assignment(db, user, body.target_ta_id)
    o, c = aware(body.opens_at), aware(body.closes_at)
    dur = body.duration_min or src.duration_min
    if c <= o:
        raise HTTPException(400, 'Bağlanma vaxtı açılmadan sonra olmalıdır')
    if c <= now():
        raise HTTPException(400, 'Bağlanma vaxtı keçmişdədir – gələcək vaxt seçin')
    if dur > (c - o).total_seconds() / 60:
        raise HTTPException(400, f'Həll müddəti ({dur} dəq) açıq qalma aralığından uzun ola bilməz')
    if body.student_ids is not None:
        bad = set(body.student_ids) - {x.id for x in roster(db, target)}
        if bad or not body.student_ids:
            raise HTTPException(400, 'Şagirdlər seçilən sinifdən/qrupdan olmalıdır')
    import copy as _copy
    t = OnlineTask(assignment_id=target.id, title=body.title or src.title, description=src.description,
                   opens_at=o, closes_at=c, duration_min=dur, questions=_copy.deepcopy(src.questions),
                   shuffle=src.shuffle, show_answers=src.show_answers, student_ids=body.student_ids, created_by=user.id)
    db.add(t)
    db.flush()
    audit(db, user, 'create', 'task', t.id, copied_from=src.id, target_ta=target.id)
    db.commit()
    return task_out(t)


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
    for m in db.scalars(select(Mark).where(Mark.task_id == t.id, Mark.student_id == student_id)):
        db.delete(m)                                  # mövzu testindən jurnala yazılmış qiymət də götürülür
    audit(db, user, 'delete', 'task_attempt', t.id, student_id=student_id)
    db.commit()
    return {'ok': True}


def _own_task(db: Session, user: User, ta_id: int, task_id: int) -> OnlineTask:
    ta = own_assignment(db, user, ta_id)
    t = get_or_404(db, OnlineTask, task_id, 'Tapşırıq')
    if t.assignment_id != ta.id or t.archived_at:
        raise HTTPException(404, 'Tapşırıq tapılmadı')
    return t


class ToJournalIn(BaseModel):
    date: dt.date | None = None          # boş – testin açıldığı gün (Bakı vaxtı)
    period: int | None = Field(None, ge=0, le=9)


@router.post('/{ta_id}/{task_id}/to-journal')
def to_journal(ta_id: int, task_id: int, body: ToJournalIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Onlayn testin nəticəsi bir düymə ilə formativ «test» qiyməti kimi jurnala: düzgün / sual → faiz → qiymət.
    Seçilən dərsdə qayıb/üzrlü olan şagird ötürülür; KSQ/BSQ dərsinə və gələcək dərsə köçürülmür."""
    from zoneinfo import ZoneInfo
    from ..domain.plan import slot_at
    from ..models import Attendance, JournalEntry, Mark
    from ..services import SCHOOL_TZ, plan_ctx, taught_lesson, today
    from .journal import SUMMATIVE
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
    e = db.scalar(select(JournalEntry).where(JournalEntry.assignment_id == ta.id, JournalEntry.date == d,
                                             JournalEntry.period == s.period))
    pl = taught_lesson(ctx, s, e)
    if pl and pl.assessment_type in SUMMATIVE:
        raise HTTPException(400, f'{pl.assessment_type} dərsinə formativ qiymət köçürülmür – başqa dərs seçin')
    if e is None:
        e = JournalEntry(assignment_id=ta.id, date=d, period=s.period, plan_lesson_id=pl.id if pl else None)
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
        m.grade = summative_grade(a.correct * 100 / a.total)
        m.comment, m.task_id = f'Onlayn test: {t.title}'[:300], t.id
    audit(db, user, 'update', 'journal', e.id, from_task=t.id, copied=copied, updated=updated)
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
    duration_min: int | None = Field(None, ge=1, le=300)
    shuffle: bool | None = None
    show_answers: Literal['after_close', 'after_submit', 'never'] | None = None
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
    d = body.duration_min or t.duration_min
    if c <= o:
        raise HTTPException(400, 'Bağlanma vaxtı açılmadan sonra olmalıdır')
    if d > (c - o).total_seconds() / 60:
        raise HTTPException(400, 'Həll müddəti açıq qalma aralığından uzun ola bilməz')
    if body.questions is not None:
        if db.scalar(select(func.count()).select_from(TaskAttempt).where(TaskAttempt.task_id == t.id)):
            raise HTTPException(409, 'Şagirdlər artıq başlayıb – suallar dəyişdirilə bilməz (ad və vaxt dəyişə bilər)')
        if not body.questions or len(body.questions) > 100:
            raise HTTPException(400, '1–100 sual olmalıdır')
        t.questions = [custom_snapshot(q) for q in body.questions]
    if body.all_students:
        t.student_ids = None
    elif 'student_ids' in data and body.student_ids is not None:
        if not body.student_ids or set(body.student_ids) - {s.id for s in roster(db, ta)}:
            raise HTTPException(400, 'Şagirdlər bu sinifdən/qrupdan seçilməlidir')
        t.student_ids = body.student_ids
    for k in ('title', 'description', 'duration_min', 'shuffle', 'show_answers'):
        if k in data and data[k] is not None:
            setattr(t, k, data[k])
    if c != aware(t.closes_at):
        t.journal_done_at = None                      # yeni bitmə vaxtında jurnala yenidən yazılsın
    t.opens_at, t.closes_at = o, c
    audit(db, user, 'update', 'task', t.id, fields=sorted(data))
    db.commit()
    return task_out(t)
