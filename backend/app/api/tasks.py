"""Onlayn tapşırıqlar (müəllim): test bazasından və ya öz suallarından, tarix + saat aralığı + həll müddəti.
Məsələn: 29.09.2026 15:00–16:00, müddət 40 dəq. Vaxt bitəndə cavablar avtomatik təhvil verilir (serverdə)."""
from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import staff
from ..domain.answers import check
from ..domain.rules import summative_grade
from ..models import BankFile, BankQuestion, BankSource, OnlineTask, TaskAttempt, User, now
from ..services import own_assignment, roster
from .common import audit, get_or_404

router = APIRouter(prefix='/api/tasks', tags=['tasks'])


def aware(t: dt.datetime) -> dt.datetime:
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)      # SQLite tz saxlamır


def finalize(db: Session, task: OnlineTask, a: TaskAttempt, at: dt.datetime | None = None, auto: bool = False):
    """Cavabları yoxlayır və təhvil verir (bir dəfə)."""
    if a.submitted_at:
        return a
    at = at or now()
    ok = sum(check(task.questions[int(i)], v) for i, v in (a.answers or {}).items() if int(i) < len(task.questions))
    a.correct, a.total = ok, len(task.questions)
    a.grade = summative_grade(ok * 100 / a.total) if a.total else None
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
    image: str | None = None

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


def task_out(t: OnlineTask) -> dict:
    return {'id': t.id, 'title': t.title, 'description': t.description, 'opens_at': aware(t.opens_at),
            'closes_at': aware(t.closes_at), 'duration_min': t.duration_min, 'questions': len(t.questions),
            'shuffle': t.shuffle, 'show_answers': t.show_answers, 'student_ids': t.student_ids,
            'archived': t.archived_at is not None}


@router.post('/{ta_id}')
def create_task(ta_id: int, body: TaskIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    if body.student_ids is not None:
        bad = set(body.student_ids) - {s.id for s in roster(db, ta)}
        if bad or not body.student_ids:
            raise HTTPException(400, 'Şagirdlər bu sinifdən/qrupdan seçilməlidir')
    qs = _snapshot(db, body.bank_ids) + [
        {'bank_id': None, 'source': 'müəllim', 'lesson': None, 'kind': q.kind, 'text': {'az': q.text},
         'options': [{'az': o} for o in q.options] if q.options else None, 'correct': q.correct, 'answer': q.answer,
         'image': q.image, 'explanation': {'az': q.explanation} if q.explanation else None} for q in body.custom]
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
def list_tasks(ta_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    out = []
    for t in db.scalars(select(OnlineTask).where(OnlineTask.assignment_id == ta.id, OnlineTask.archived_at.is_(None))
                        .order_by(OnlineTask.opens_at.desc())):
        expire_due(db, t)
        done = db.scalars(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.submitted_at.is_not(None))).all()
        out.append({**task_out(t), 'submitted': len(done),
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
        rows.append({'student_id': s.id, 'full_name': s.full_name, 'status': status,
                     'auto_submitted': bool(a and a.auto_submitted), 'correct': a.correct if a else None,
                     'total': a.total if a else None, 'grade': a.grade if a else None,
                     'pct': round(a.correct * 100 / a.total, 1) if a and a.submitted_at and a.total else None})
    done = [a for a in atts.values() if a.submitted_at]
    per_q = []
    for i, q in enumerate(t.questions):
        ok = sum(check(q, (a.answers or {}).get(str(i))) for a in done)
        per_q.append({'index': i, 'text': q['text'], 'kind': q['kind'], 'correct': ok, 'of': len(done),
                      'pct': round(ok * 100 / len(done), 1) if done else None})
    return {'task': task_out(t), 'rows': rows, 'questions': per_q}


@router.post('/{ta_id}/{task_id}/archive')
def archive_task(ta_id: int, task_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    own_assignment(db, user, ta_id)
    t = get_or_404(db, OnlineTask, task_id, 'Tapşırıq')
    if t.assignment_id != ta_id:
        raise HTTPException(404, 'Tapşırıq tapılmadı')
    t.archived_at = now()
    audit(db, user, 'archive', 'task', t.id)
    db.commit()
    return {'ok': True}
