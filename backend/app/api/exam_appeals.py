"""Müəllim: şagirdlərin KSQ/BSQ apelyasiyaları (docs/tasks/ksq-bsq-elave-ve-iki-netice.md, mərhələ 4). Qərar – qəbul (həmin slot düz
sayılır; «hamıya tətbiq et» – eyni bank sualını alan hamıda eyni cavab) və ya rədd (cavab məcburi); bal yenidən hesablanır,
skanın history-sinə və audit jurnalına yazılır. Bank sualı avtomatik dəyişmir – yalnız «yoxlanmalı» işarələnir."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..appeals import ref_of, topic_of
from ..db import get_db
from ..deps import staff
from ..exam_logic import exam_roster
from ..models import BankQuestion, Exam, ExamAppeal, ExamScan, ExamScore, ExamVariant, TeachingAssignment, User, now
from ..services import own_assignment
from .common import audit, get_or_404

router = APIRouter(prefix='/api/exam-appeals', tags=['exam-appeals'])


@router.get('/open-count')
def open_count(user: User = Depends(staff), db: Session = Depends(get_db)):
    """Ana səhifə nişanı: müəllimin sinifləri üzrə cavabsız apelyasiyalar."""
    where = (ExamAppeal.status == 'open', TeachingAssignment.teacher_id == user.id)
    n = db.scalar(select(func.count()).select_from(ExamAppeal).join(Exam, Exam.id == ExamAppeal.exam_id)
                  .join(TeachingAssignment, TeachingAssignment.id == Exam.assignment_id).where(*where)) or 0
    # ən köhnə cavabsız apelyasiya – nişana toxunanda birbaşa onun imtahanının apelyasiya pəncərəsi açılır
    first = db.execute(select(Exam.assignment_id, Exam.id).join(ExamAppeal, ExamAppeal.exam_id == Exam.id)
                       .join(TeachingAssignment, TeachingAssignment.id == Exam.assignment_id).where(*where)
                       .order_by(ExamAppeal.id).limit(1)).first()
    return {'open': n, 'first': {'ta_id': first[0], 'exam_id': first[1]} if first else None}


def _exam(db: Session, user: User, ta_id: int, exam_id: int):
    ta = own_assignment(db, user, ta_id)
    e = get_or_404(db, Exam, exam_id, 'İmtahan')
    if e.assignment_id != ta.id:
        raise HTTPException(404, 'İmtahan tapılmadı')
    return ta, e


def _out(db: Session, e: Exam, a: ExamAppeal, names: dict, variants: dict, scans: dict) -> dict:
    from ..domain.ksq_card import key_value
    v = variants.get(a.student_id)
    q = next((x for x in (v.questions if v else []) if x['slot'] == a.slot), None)
    bq = db.get(BankQuestion, a.bank_id) if a.bank_id else None
    sc = scans.get((a.student_id, a.source))
    return {'id': a.id, 'student_id': a.student_id, 'full_name': names.get(a.student_id), 'slot': a.slot, 'source': a.source,
            'status': a.status, 'reason': a.reason, 'my_answer': a.my_answer, 'correct_at_time': a.correct_at_time,
            'key_now': key_value(q) if q else None, 'teacher_reply': a.teacher_reply, 'apply_all': a.apply_all,
            'created_at': a.created_at, 'decided_at': a.decided_at,
            'question': {'text': q.get('text'), 'options': q.get('options'), 'image': q.get('image'), 'kind': q.get('kind')} if q else None,
            'bank_id': a.bank_id, 'topic': topic_of(db, q) if q else ((a.bank_ref or {}).get('text') or '').split(' · ')[0] or None,
            'bank_ref': a.bank_ref or (ref_of(db, q) if q else None),
            # bankdakı sualın indiki halı: açar sonradan dəyişibsə – müəllim fərqi görür
            'bank': {'text': bq.text, 'answer': bq.answer, 'correct': bq.correct, 'needs_review': bq.needs_review} if bq else None,
            'scan_id': sc.id if sc else None, 'crop': bool(sc and sc.crop_key)}


@router.get('/{ta_id}/{exam_id}')
def list_appeals(ta_id: int, exam_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta, e = _exam(db, user, ta_id, exam_id)
    names = {s.id: s.full_name for s in exam_roster(db, ta, e)}
    rows = list(db.scalars(select(ExamAppeal).where(ExamAppeal.exam_id == e.id).order_by(ExamAppeal.status.desc(), ExamAppeal.id)))
    variants = {v.student_id: v for v in db.scalars(select(ExamVariant).where(ExamVariant.exam_id == e.id))}
    scans = {(s.student_id, s.source): s for s in db.scalars(select(ExamScan).where(ExamScan.exam_id == e.id))}
    return {'appeal_until': e.appeal_until, 'open': sum(a.status == 'open' for a in rows),
            'appeals': [_out(db, e, a, names, variants, scans) for a in rows]}


class DecisionIn(BaseModel):
    decision: Literal['accept', 'reject']
    reply: str | None = Field(None, max_length=1000)
    apply_all: bool = False                      # açar səhv idi: bu bank sualını alan hamıda eyni cavab düz sayılır


def regrade_for(db: Session, e: Exam, a: ExamAppeal, wide: bool = False) -> list[dict]:
    """Apelyasiyanın təsir etdiyi skanlar yenidən qiymətləndirilir (accepted_slots ilə), fərq history-yə yazılır."""
    from .exam_scans import apply
    sids = {a.student_id}
    if (a.apply_all or wide) and a.bank_id:
        sids = {v.student_id for v in db.scalars(select(ExamVariant).where(ExamVariant.exam_id == e.id))
                if any(q.get('bank_id') == a.bank_id for q in v.questions)}
    changes = []
    for sc in db.scalars(select(ExamScan).where(ExamScan.exam_id == e.id, ExamScan.student_id.in_(sids or {0}), ExamScan.status == 'graded')):
        if not (a.apply_all or wide) and sc.source != a.source:
            continue
        before = sc.points
        apply(db, e, sc)
        if sc.points != before:
            sc.history = [*(sc.history or []), {'at': now().isoformat(), 'appeal': a.id, 'slot': a.slot, 'status': a.status,
                                                'points': before, 'new_points': sc.points, 'read_by': 'appeal'}][-8:]
            changes.append({'student_id': sc.student_id, 'source': sc.source, 'old': before, 'new': sc.points})
    return changes


@router.put('/{ta_id}/{exam_id}/{appeal_id}')
def decide(ta_id: int, exam_id: int, appeal_id: int, body: DecisionIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta, e = _exam(db, user, ta_id, exam_id)
    a = get_or_404(db, ExamAppeal, appeal_id, 'Apelyasiya')
    if a.exam_id != e.id:
        raise HTTPException(404, 'Apelyasiya tapılmadı')
    if body.decision == 'reject' and not (body.reply or '').strip():
        raise HTTPException(400, 'Rədd edəndə şagirdə cavab yazın')
    if body.apply_all and body.decision != 'accept':
        raise HTTPException(400, '«Hamıya tətbiq et» yalnız qəbul zamanı olur')
    old_status, old_all = a.status, a.apply_all
    a.status = 'accepted' if body.decision == 'accept' else 'rejected'
    a.teacher_reply, a.apply_all = (body.reply or '').strip() or None, body.apply_all and body.decision == 'accept'
    a.decided_by, a.decided_at = user.id, now()
    db.flush()
    changes = regrade_for(db, e, a, wide=old_all)
    if a.apply_all and a.bank_id:
        bq = db.get(BankQuestion, a.bank_id)
        if bq is not None:
            bq.needs_review = True               # bankı müəllim/admin düzəldir – avtomatik dəyişmə yoxdur
    manual = []
    names = {s.id: s.full_name for s in exam_roster(db, ta, e)}
    for c in changes:
        sc = db.get(ExamScore, (e.id, c['student_id']))
        if sc is not None and sc.chosen == 'manual':
            manual.append(names.get(c['student_id']) or c['student_id'])
    audit(db, user, 'update', 'exam_appeal', a.id, exam_id=e.id, student_id=a.student_id, slot=a.slot, source=a.source,
          old_status=old_status, new_status=a.status, apply_all=a.apply_all, changes=changes)
    db.commit()
    return {'ok': True, 'status': a.status, 'changes': [{**c, 'full_name': names.get(c['student_id'])} for c in changes],
            'manual_students': sorted(set(manual))}
