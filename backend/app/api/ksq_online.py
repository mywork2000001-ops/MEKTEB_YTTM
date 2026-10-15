"""KSQ/BSQ onlayn (docs/ksq-skan-ekran-ve-onlayn-promtu.md, 13.10.2026): şagirdin ÖZ kağız variantı (ExamVariant) onlayn test kimi.

Hər şagirdə ayrıca OnlineTask(kind='ksq', exam_id, student_ids=[sid]) – mövcud test ekranı (tam ekran, taymer, avtomatik
saxlama) işləyir. Təhvil zamanı cavablar kartın oxunuşuna çevrilir → ExamScan(read_by='online') → eyni qiymətləndirmə (apply) →
ExamScore. Kağız və onlayn bir jurnalda; açar düzəlişi / «Yenilə» onlayn nəticələri də yenidən hesablayır. Nəticə şagirdə
dərhal göstərilmir (müəllim yoxlayır)."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import staff
from ..models import Exam, ExamScan, ExamScore, ExamVariant, OnlineTask, TaskAttempt, User, now
from ..exam_logic import exam_roster
from ..services import own_assignment
from .common import audit, get_or_404
from .tasks import aware

router = APIRouter(prefix='/api/ksq-online', tags=['ksq-online'])
Q_FIELDS = ('slot', 'kind', 'text', 'options', 'correct', 'answer', 'image', 'points', 'bank_id', 'raw')


def _exam(db: Session, user: User, ta_id: int, exam_id: int) -> tuple:
    ta = own_assignment(db, user, ta_id)
    e = get_or_404(db, Exam, exam_id, 'İmtahan')
    if e.assignment_id != ta.id:
        raise HTTPException(404, 'İmtahan tapılmadı')
    return ta, e


def _questions(v: ExamVariant) -> list[dict]:
    return [{k: q[k] for k in Q_FIELDS if k in q} for q in sorted(v.questions, key=lambda q: q['slot'])]


def _tasks(db: Session, e: Exam) -> dict[int, OnlineTask]:
    """Şagird → onun onlayn KSQ tapşırığı (ən sonuncusu)."""
    out: dict[int, OnlineTask] = {}
    for t in db.scalars(select(OnlineTask).where(OnlineTask.exam_id == e.id, OnlineTask.archived_at.is_(None)).order_by(OnlineTask.id)):
        for sid in t.student_ids or []:
            out[sid] = t
    return out


def _attempt(db: Session, t: OnlineTask, sid: int) -> TaskAttempt | None:
    return db.scalar(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.student_id == sid))


def _status(t: OnlineTask | None, a: TaskAttempt | None, at: dt.datetime) -> str:
    if t is None:
        return 'none'
    if a and a.submitted_at:
        return 'done'
    if a and at < aware(a.deadline):
        return 'doing'
    if at < aware(t.opens_at):
        return 'waiting'
    if at >= aware(t.closes_at) or a:
        return 'missed'
    return 'open'


def record(db: Session, t: OnlineTask, a: TaskAttempt) -> None:
    """Təhvil (tasks.finalize): cavablar → oxunuş → bal → jurnal. Kağız skanı varsa – tarixçəyə keçir, onlayn əvəz edir."""
    from .exam_scans import apply
    from ..domain.ksq_card import MCQ_LETTERS
    e = db.get(Exam, t.exam_id) if t.exam_id else None
    if e is None:
        return
    v = db.get(ExamVariant, (e.id, a.student_id))
    if v is None:
        return
    answers = a.answers or {}
    reading = []
    for i, q in enumerate(t.questions):
        val = answers.get(str(i))
        if q.get('kind') == 'mcq':
            val = MCQ_LETTERS[val] if isinstance(val, int) and 0 <= val < len(MCQ_LETTERS) else None
        else:
            val = str(val).strip()[:40] if val not in (None, '') else None
        reading.append({'slot': q['slot'], 'value': val, 'confidence': 1.0, 'by': 'online'})
    sc = db.scalar(select(ExamScan).where(ExamScan.exam_id == e.id, ExamScan.student_id == a.student_id))
    if sc is None:
        sc = ExamScan(exam_id=e.id, student_id=a.student_id, code=v.code, history=[])
        db.add(sc)
    elif sc.reading:
        sc.history = [*(sc.history or []), {'at': now().isoformat(), 'reading': sc.reading, 'points': sc.points,
                                            'read_by': sc.read_by}][-5:]
    sc.code, sc.reading, sc.read_by, sc.error, sc.lost = v.code, reading, 'online', None, None
    apply(db, e, sc)


@router.get('/{ta_id}/{exam_id}')
def status(ta_id: int, exam_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    from .tasks import expire_due
    ta, e = _exam(db, user, ta_id, exam_id)
    names = {s.id: s.full_name for s in exam_roster(db, ta, e)}
    tasks = _tasks(db, e)
    for t in {t.id: t for t in tasks.values()}.values():
        expire_due(db, t)
    scans = {sc.student_id: sc for sc in db.scalars(select(ExamScan).where(ExamScan.exam_id == e.id))}
    scores = {s.student_id: s for s in db.scalars(select(ExamScore).where(ExamScore.exam_id == e.id))}
    at = now()
    rows = []
    for sid in db.scalars(select(ExamVariant.student_id).where(ExamVariant.exam_id == e.id)):
        if sid not in names:
            continue
        t = tasks.get(sid)
        a = _attempt(db, t, sid) if t else None
        sc, s = scans.get(sid), scores.get(sid)
        rows.append({'student_id': sid, 'full_name': names[sid], 'status': _status(t, a, at),
                     'opens_at': aware(t.opens_at) if t else None, 'closes_at': aware(t.closes_at) if t else None,
                     'duration_min': t.duration_min if t else None,
                     'submitted_at': a.submitted_at if a and a.submitted_at else None, 'auto': bool(a and a.auto_submitted),
                     'paper': bool(sc and sc.crop_key), 'online': bool(sc and sc.read_by == 'online'),
                     'points': s.points if s and not s.absent else None})
    rows.sort(key=lambda r: r['full_name'] or '')
    return {'rows': rows, 'counts': {k: sum(r['status'] == k for r in rows) for k in ('none', 'waiting', 'open', 'doing', 'done', 'missed')}}


class SendIn(BaseModel):
    student_ids: list[int] | None = None          # None – variantı olan, nəticəsi olmayan hamı
    opens_at: dt.datetime | None = None           # None – indi
    window_hours: int = Field(24, ge=1, le=24 * 14)
    duration_min: int = Field(45, ge=5, le=240)
    shuffle: bool = True
    resend: bool = False                          # təhvil vermiş / buraxmış şagirdə yeni cəhd (köhnə onlayn cəhd silinir)


@router.post('/{ta_id}/{exam_id}')
def send(ta_id: int, exam_id: int, body: SendIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta, e = _exam(db, user, ta_id, exam_id)
    names = {s.id: s.full_name for s in exam_roster(db, ta, e)}
    variants = {v.student_id: v for v in db.scalars(select(ExamVariant).where(ExamVariant.exam_id == e.id)) if v.student_id in names}
    if not variants:
        raise HTTPException(409, 'Əvvəl variantları yaradın (1-ci addım)')
    graded = {sc.student_id for sc in db.scalars(select(ExamScan).where(ExamScan.exam_id == e.id, ExamScan.status == 'graded'))}
    picked = body.student_ids if body.student_ids is not None else [sid for sid in variants if sid not in graded]
    picked = [sid for sid in dict.fromkeys(picked) if sid in variants]
    if not picked:
        raise HTTPException(409, 'Göndəriləcək şagird yoxdur – hamısının nəticəsi var (yenidən göndərmək üçün şagirdləri seçin)')
    opens = aware(body.opens_at) if body.opens_at else now()
    closes = opens + dt.timedelta(hours=body.window_hours)
    if closes <= now():
        raise HTTPException(400, 'Bağlanma vaxtı keçib')
    tasks, at = _tasks(db, e), now()
    title = f'{e.kind}-{e.no}' + (f' · {e.title}' if e.title else '')
    sent, updated, skipped = 0, 0, []
    for sid in picked:
        t = tasks.get(sid)
        a = _attempt(db, t, sid) if t else None
        if t is not None and a is not None and (a.submitted_at or at >= aware(a.deadline)) and not body.resend:
            skipped.append(names[sid])               # artıq yazıb – «↻ Yenidən göndər» ilə
            continue
        if t is not None and a is not None and not a.submitted_at and at < aware(a.deadline):
            skipped.append(names[sid])               # hazırda yazır – toxunulmur
            continue
        if t is not None and a is None:              # hələ başlamayıb – vaxt və suallar yenilənir
            t.opens_at, t.closes_at, t.duration_min, t.shuffle = opens, closes, body.duration_min, body.shuffle
            t.questions, t.title = _questions(variants[sid]), title
            updated += 1
            continue
        if t is not None:                            # yenidən göndər: köhnə onlayn cəhd silinir (nəticə skanın tarixçəsində qalır)
            db.execute(delete(TaskAttempt).where(TaskAttempt.task_id == t.id))
            db.delete(t)
            db.flush()
        db.add(OnlineTask(assignment_id=ta.id, title=title, description=None, opens_at=opens, closes_at=closes,
                          duration_min=body.duration_min, questions=_questions(variants[sid]), shuffle=body.shuffle,
                          show_answers='never', student_ids=[sid], created_by=user.id, kind='ksq', exam_id=e.id))
        sent += 1
    audit(db, user, 'create', 'ksq_online', e.id, sent=sent, updated=updated, skipped=len(skipped))
    db.commit()
    return {'sent': sent, 'updated': updated, 'skipped': skipped}


class CancelIn(BaseModel):
    student_ids: list[int] | None = None          # None – başlamamış hamı


@router.post('/{ta_id}/{exam_id}/cancel')
def cancel(ta_id: int, exam_id: int, body: CancelIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Göndərişi geri götür: yalnız hələ başlamamış şagirdlər (yazmağa başlayan / təhvil verən – toxunulmur)."""
    _, e = _exam(db, user, ta_id, exam_id)
    n = 0
    for sid, t in _tasks(db, e).items():
        if body.student_ids is not None and sid not in body.student_ids:
            continue
        if _attempt(db, t, sid) is None:
            db.delete(t)
            n += 1
    audit(db, user, 'delete', 'ksq_online', e.id, cancelled=n)
    db.commit()
    return {'cancelled': n}
