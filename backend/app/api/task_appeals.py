"""Onlayn sınaqda apelyasiya – müəllimin tərəfi: ümumi qutu üçün kartlar (exam_appeals.inbox bunları əlavə edir) və qərar.
Şagird tərəfi – api/portal.py (POST /tasks/{id}/appeals). Qəbul → TaskAttempt.manual[sual]=True və bal yenidən hesablanır;
apply_all – eyni sınaq paketinin bütün cəhdlərində həmin sual (bank_id, yoxdursa eyni indeks) cavab verənə düz sayılır."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import staff
from ..models import OnlineTask, SchoolClass, Student, TaskAppeal, TaskAttempt, TeachingAssignment, User, now
from ..services import own_assignment
from .common import audit, get_or_404
from .tasks import _forget, aware, score

router = APIRouter(prefix='/api/task-appeals', tags=['task-appeals'])
LET = 'ABCDE'


def _letter(q: dict, v) -> str:
    """mcq üçün indeks → hərf (AppealCard hərflə müqayisə edir); açıq sualda olduğu kimi."""
    if q.get('kind') == 'mcq' and v not in (None, '') and str(v).isdigit() and int(v) < len(LET):
        return LET[int(v)]
    return '' if v is None else str(v)


def card(db: Session, ap: TaskAppeal, t: OnlineTask, names: dict, classes: dict) -> dict:
    """Müəllim qutusunda KSQ apelyasiyası ilə eyni formada kart (frontend AppealCard eyni komponentdir)."""
    q = ap.q or {}
    key = _letter(q, q.get('correct') if q.get('kind') == 'mcq' else q.get('answer'))
    return {'id': ap.id, 'kind': 'sinaq', 'task_id': t.id, 'student_id': ap.student_id, 'full_name': names.get(ap.student_id),
            'slot': ap.q_index + 1, 'source': 'online', 'status': ap.status, 'reason': ap.reason,
            'my_answer': _letter(q, ap.my_answer), 'correct_at_time': key, 'key_now': key,
            'teacher_reply': ap.teacher_reply, 'apply_all': ap.apply_all, 'created_at': ap.created_at, 'decided_at': ap.decided_at,
            'question': {'text': q.get('text'), 'options': q.get('options'), 'image': q.get('image'), 'kind': q.get('kind')},
            'question_changed': False, 'bank_id': ap.bank_id, 'topic': None, 'bank_ref': {'text': t.title}, 'bank': None,
            'scan_id': None, 'crop': False, 'fix_replies': {}, 'ta_id': t.assignment_id, 'appeal_until': None,
            'explanation': q.get('explanation'),
            'exam': {'id': t.id, 'title': t.title, 'kind': 'Sınaq', 'no': None, 'date': None, 'ta_id': t.assignment_id,
                     'class_name': classes.get(t.assignment_id)}}


def inbox_cards(db: Session, user: User, only_open: bool) -> list[dict]:
    cond = [TeachingAssignment.teacher_id == user.id]
    if only_open:
        cond.append(TaskAppeal.status == 'open')
    rows = db.execute(select(TaskAppeal, OnlineTask).join(OnlineTask, OnlineTask.id == TaskAppeal.task_id)
                      .join(TeachingAssignment, TeachingAssignment.id == OnlineTask.assignment_id).where(*cond)
                      .order_by(TaskAppeal.id)).all()
    if not rows:
        return []
    names = {s.id: s.full_name for s in db.scalars(select(Student).where(Student.id.in_({r[0].student_id for r in rows})))}
    tas = {ta.id: ta for ta in db.scalars(select(TeachingAssignment).where(TeachingAssignment.id.in_({r[1].assignment_id for r in rows})))}
    cn = {c.id: c.name for c in db.scalars(select(SchoolClass).where(SchoolClass.id.in_({x.class_id for x in tas.values()})))}
    classes = {ta_id: cn.get(ta.class_id) for ta_id, ta in tas.items()}
    return [card(db, ap, t, names, classes) for ap, t in rows]


def open_count(db: Session, user: User) -> int:
    return db.scalar(select(func.count()).select_from(TaskAppeal).join(OnlineTask, OnlineTask.id == TaskAppeal.task_id)
                     .join(TeachingAssignment, TeachingAssignment.id == OnlineTask.assignment_id)
                     .where(TaskAppeal.status == 'open', TeachingAssignment.teacher_id == user.id)) or 0


class DecisionIn(BaseModel):
    status: Literal['accepted', 'rejected']
    teacher_reply: str | None = Field(None, max_length=1000)
    apply_all: bool = False


def _q_index_in(t2: OnlineTask, ap: TaskAppeal) -> int | None:
    if ap.bank_id:
        return next((i for i, q in enumerate(t2.questions) if q.get('bank_id') == ap.bank_id), None)
    return ap.q_index if ap.q_index < len(t2.questions) else None


@router.put('/{appeal_id}')
def decide(appeal_id: int, body: DecisionIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    ap = get_or_404(db, TaskAppeal, appeal_id, 'Apelyasiya')
    t = db.get(OnlineTask, ap.task_id)
    own_assignment(db, user, t.assignment_id)                 # başqa müəllim – 404
    reply = (body.teacher_reply or '').strip() or None
    if body.status == 'rejected' and not reply:
        raise HTTPException(400, 'Rədd edəndə şagirdə cavab yazın')
    if body.apply_all and body.status != 'accepted':
        raise HTTPException(400, '«Hamıya tətbiq et» yalnız qəbul zamanı olur')
    old = ap.status
    ap.status, ap.teacher_reply, ap.apply_all = body.status, reply, body.apply_all
    ap.decided_by, ap.decided_at = user.id, now()
    changes: list[dict] = []

    def mark(task: OnlineTask, a: TaskAttempt, qi: int) -> None:
        before = a.points
        a.manual = {**(a.manual or {}), str(qi): True}
        score(task, a)
        changes.append({'student_id': a.student_id, 'old': before, 'new': a.points})

    if body.status == 'accepted':
        a0 = db.scalar(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.student_id == ap.student_id))
        if a0 is not None and a0.submitted_at:
            mark(t, a0, ap.q_index)
        if body.apply_all and t.batch_id:
            for t2 in db.scalars(select(OnlineTask).where(OnlineTask.batch_id == t.batch_id, OnlineTask.archived_at.is_(None))):
                qi = ap.q_index if t2.id == t.id else _q_index_in(t2, ap)
                if qi is None:
                    continue
                for a in db.scalars(select(TaskAttempt).where(TaskAttempt.task_id == t2.id, TaskAttempt.submitted_at.is_not(None))):
                    if (t2.id, a.student_id) == (t.id, ap.student_id):
                        continue
                    if (a.answers or {}).get(str(qi)) in (None, ''):        # cavabsız şagird açar səhv olsa da düz almır
                        continue
                    if (a.manual or {}).get(str(qi)) is True:
                        continue
                    mark(t2, a, qi)
    _forget(t.batch_id)
    audit(db, user, 'update', 'task_appeal', ap.id, task_id=t.id, student_id=ap.student_id, q_index=ap.q_index,
          old_status=old, new_status=ap.status, apply_all=ap.apply_all, changes=changes)
    db.commit()
    names = {s.id: s.full_name for s in db.scalars(select(Student).where(Student.id.in_({c['student_id'] for c in changes} or {0})))}
    return {'ok': True, 'status': ap.status, 'changes': [{**c, 'full_name': names.get(c['student_id'])} for c in changes]}
