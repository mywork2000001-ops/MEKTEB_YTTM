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
from ..models import BankQuestion, Exam, ExamAppeal, ExamScan, ExamScore, ExamVariant, Student, TeachingAssignment, User, now
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
    from .task_appeals import open_count as task_open
    return {'open': n + task_open(db, user), 'first': {'ta_id': first[0], 'exam_id': first[1]} if first else None}


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
    ref = dict(a.bank_ref or {})
    snap = ref.pop('q', None)                    # apelyasiya anında dondurulmuş sual (B.1); köhnə apelyasiyalarda yoxdur
    # sual: variantdakı, yoxdursa (variant silinib) snapshot; sonradan dəyişibsə – şagirdin gördüyü (snapshot) göstərilir
    changed = bool(q and snap and (q.get('text') != snap.get('text') or q.get('options') != snap.get('options')))
    shown = snap if changed else (q or snap)
    bq = db.get(BankQuestion, a.bank_id) if a.bank_id else None
    sc = scans.get((a.student_id, a.source))
    key_now = key_value(q) if q else (snap.get('key') if snap else None)
    return {'id': a.id, 'student_id': a.student_id, 'full_name': names.get(a.student_id), 'slot': a.slot, 'source': a.source,
            'status': a.status, 'reason': a.reason, 'my_answer': a.my_answer, 'correct_at_time': a.correct_at_time,
            'key_now': key_now, 'teacher_reply': a.teacher_reply, 'apply_all': a.apply_all,
            'created_at': a.created_at, 'decided_at': a.decided_at,
            'question': {'text': shown.get('text'), 'options': shown.get('options'), 'image': shown.get('image'), 'kind': shown.get('kind')} if shown else None,
            'question_changed': changed,
            'bank_id': a.bank_id, 'topic': topic_of(db, q) if q else (ref.get('text') or '').split(' · ')[0] or None,
            'bank_ref': ref or (ref_of(db, q) if q else None),
            # bankdakı sualın indiki halı: açar sonradan dəyişibsə – müəllim fərqi görür
            'bank': {'text': bq.text, 'answer': bq.answer, 'correct': bq.correct, 'needs_review': bq.needs_review} if bq else None,
            'scan_id': sc.id if sc else None, 'crop': bool(sc and sc.crop_key),
            'fix_replies': _fix_replies(db, a.student_id)}


@router.get('/inbox')
def inbox(status: Literal['open', 'all'] = 'open', user: User = Depends(staff), db: Session = Depends(get_db)):
    """Müəllimin bütün imtahanları üzrə apelyasiyalar bir yerdə (open-count ilə eyni hüquq: yalnız öz dərs bağlılıqları).
    Sıralama: əvvəl gözləyənlər, daxildə köhnədən yeniyə."""
    from ..models import SchoolClass
    where = [TeachingAssignment.teacher_id == user.id]
    if status == 'open':
        where.append(ExamAppeal.status == 'open')
    rows = db.execute(select(ExamAppeal, Exam, TeachingAssignment).join(Exam, Exam.id == ExamAppeal.exam_id)
                      .join(TeachingAssignment, TeachingAssignment.id == Exam.assignment_id).where(*where)
                      .order_by(ExamAppeal.id)).all()
    rows.sort(key=lambda r: r[0].status != 'open')          # sort sabitdir
    names = {s.id: s.full_name for s in db.scalars(select(Student).where(Student.id.in_({r[0].student_id for r in rows} or {0})))}
    classes = {c.id: c.name for c in db.scalars(select(SchoolClass).where(SchoolClass.id.in_({r[2].class_id for r in rows} or {0})))}
    exam_ids = {r[1].id for r in rows}
    variants: dict[int, dict] = {}
    for v in db.scalars(select(ExamVariant).where(ExamVariant.exam_id.in_(exam_ids or {0}))):
        variants.setdefault(v.exam_id, {})[v.student_id] = v
    scans: dict[int, dict] = {}
    for sc in db.scalars(select(ExamScan).where(ExamScan.exam_id.in_(exam_ids or {0}))):
        scans.setdefault(sc.exam_id, {})[(sc.student_id, sc.source)] = sc
    out = [{**_out(db, e, a, names, variants.get(e.id, {}), scans.get(e.id, {})), 'ta_id': t.id, 'appeal_until': e.appeal_until,
            'exam': {'id': e.id, 'title': e.title, 'kind': e.kind, 'no': e.no, 'date': e.date, 'ta_id': t.id, 'class_name': classes.get(t.class_id)}}
           for a, e, t in rows]
    from .task_appeals import inbox_cards
    out += inbox_cards(db, user, status == 'open')                 # onlayn sınaq apelyasiyaları (kind='sinaq')
    out.sort(key=lambda x: x['status'] != 'open')
    return {'open': sum(x['status'] == 'open' for x in out), 'appeals': out}


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


def _apply_decision(db: Session, ta: TeachingAssignment, e: Exam, a: ExamAppeal, user: User, decision: str, reply: str | None,
                    apply_all: bool) -> None:
    """Qərarın qeydi (decide və fix üçün ortaq)."""
    a.status = 'accepted' if decision == 'accept' else 'rejected'
    a.teacher_reply, a.apply_all = (reply or '').strip() or None, apply_all and decision == 'accept'
    a.decided_by, a.decided_at = user.id, now()


def _decide_core(db: Session, ta: TeachingAssignment, e: Exam, a: ExamAppeal, user: User, decision: str, reply: str | None,
                 apply_all: bool, needs_review: bool = True) -> tuple[list[dict], list, dict]:
    old_all = a.apply_all
    _apply_decision(db, ta, e, a, user, decision, reply, apply_all)
    db.flush()
    changes = regrade_for(db, e, a, wide=old_all)
    if a.apply_all and a.bank_id and needs_review:
        bq = db.get(BankQuestion, a.bank_id)
        if bq is not None:
            bq.needs_review = True               # bankı müəllim/admin düzəldir – avtomatik dəyişmə yoxdur
    manual = []
    names = {s.id: s.full_name for s in exam_roster(db, ta, e)}
    for c in changes:
        sc = db.get(ExamScore, (e.id, c['student_id']))
        if sc is not None and sc.chosen == 'manual':
            manual.append(names.get(c['student_id']) or c['student_id'])
    return changes, manual, names


@router.put('/{ta_id}/{exam_id}/{appeal_id}')
def decide(ta_id: int, exam_id: int, appeal_id: int, body: DecisionIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta, e = _exam(db, user, ta_id, exam_id)
    a = _appeal(db, e, appeal_id)
    if body.decision == 'reject' and not (body.reply or '').strip():
        raise HTTPException(400, 'Rədd edəndə şagirdə cavab yazın')
    if body.apply_all and body.decision != 'accept':
        raise HTTPException(400, '«Hamıya tətbiq et» yalnız qəbul zamanı olur')
    old_status = a.status
    changes, manual, names = _decide_core(db, ta, e, a, user, body.decision, body.reply, body.apply_all)
    audit(db, user, 'update', 'exam_appeal', a.id, exam_id=e.id, student_id=a.student_id, slot=a.slot, source=a.source,
          old_status=old_status, new_status=a.status, apply_all=a.apply_all, changes=changes)
    db.commit()
    return {'ok': True, 'status': a.status, 'changes': [{**c, 'full_name': names.get(c['student_id'])} for c in changes],
            'manual_students': sorted(set(manual))}


# ---- apelyasiyanın içindən düzəliş: açar / skanın oxunuşu / sualı ləğv et --------------------------------------------
_FIX_REPLY = {
    'key': {'az': 'Açar səhv idi, düzəldildi – balınız yenidən hesablandı.',
            'ru': 'Ключ был неверным, исправлено – ваш балл пересчитан.',
            'en': 'The answer key was wrong and has been corrected – your score has been recalculated.'},
    'reading': {'az': 'Kartınız səhv oxunmuşdu, düzəldildi – balınız yenidən hesablandı.',
                'ru': 'Ваша карточка была прочитана неверно, исправлено – ваш балл пересчитан.',
                'en': 'Your card was read incorrectly and has been corrected – your score has been recalculated.'},
    'annul': {'az': 'Sual ləğv edildi, bal yenidən hesablandı.',
              'ru': 'Вопрос аннулирован, балл пересчитан.',
              'en': 'The question has been annulled and the score recalculated.'},
    'wrong': {'az': 'Yoxlandı: düzəlişdən sonra da cavabınız düzgün deyil.',
              'ru': 'Проверено: и после исправления ваш ответ неверный.',
              'en': 'Checked: your answer is still incorrect after the correction.'},
}


def _fix_replies(db: Session, student_id: int) -> dict[str, str]:
    """Şagirdə hazır cavab mətnləri – şagirdin dilində (portal hesabı yoxdursa AZ)."""
    st = db.get(Student, student_id)
    u = db.get(User, st.user_id) if st is not None and st.user_id else None
    lang = u.language if u is not None and u.language in ('ru', 'en') else 'az'
    return {k: v[lang] for k, v in _FIX_REPLY.items()}


def _appeal(db: Session, e: Exam, appeal_id: int) -> ExamAppeal:
    a = get_or_404(db, ExamAppeal, appeal_id, 'Apelyasiya')
    if a.exam_id != e.id:
        raise HTTPException(404, 'Apelyasiya tapılmadı')
    return a


class FixIn(BaseModel):
    kind: Literal['key', 'reading', 'annul']
    correct: int | None = Field(None, ge=0, le=4)      # key, test sualı: düzgün variantın indeksi
    answer: str | None = Field(None, max_length=60)    # key, açıq sual
    value: str | None = Field(None, max_length=12)     # reading: kartda düzgün oxunuş (hərf / rəqəm)
    all_same: bool = True                              # key: bu bank sualını alan hamıda
    bank: bool = True                                  # key: bankdakı sualın açarı da
    reply: str | None = Field(None, max_length=1000)


def _points(db: Session, e: Exam) -> dict[tuple[int, str], float | None]:
    return {(s.student_id, s.source): s.points for s in db.scalars(select(ExamScan).where(ExamScan.exam_id == e.id))}


@router.post('/{ta_id}/{exam_id}/{appeal_id}/fix')
def fix(ta_id: int, exam_id: int, appeal_id: int, body: FixIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Apelyasiyanın içindən düzəliş (bir tranzaksiya, bir audit): açar / oxunuş / sualı ləğv; sonra apelyasiya avtomatik qəbul
    olunur və şagirdə hazır cavab yazılır. Düzəlişdən sonra şagirdin cavabı hələ də səhvdirsə – apelyasiya rədd olunur."""
    from .exam_scans import apply_slot_fix
    from .exams import QuestionEditIn, apply_annul, apply_key_edit
    ta, e = _exam(db, user, ta_id, exam_id)
    a = _appeal(db, e, appeal_id)
    before = _points(db, e)
    old_status = a.status
    extra: dict = {}
    if body.kind == 'key':
        q, students, _ = apply_key_edit(db, e, a.student_id, a.slot, QuestionEditIn(
            correct=body.correct, answer=body.answer, all_same=body.all_same))
        extra['students'] = len(students)
        bq = db.get(BankQuestion, a.bank_id) if (body.bank and a.bank_id) else None
        if bq is not None:                       # bankdakı sualın açarı da (yalnız açar; mətn toxunulmaz)
            if q['kind'] == 'mcq':
                bq.correct = body.correct
            else:
                bq.answer = body.answer
            bq.needs_review = False
            extra['bank_id'] = bq.id
    elif body.kind == 'reading':
        sc = db.scalar(select(ExamScan).where(ExamScan.exam_id == e.id, ExamScan.student_id == a.student_id, ExamScan.source == a.source))
        if sc is None:
            raise HTTPException(404, 'Bu apelyasiyanın skanı yoxdur')
        apply_slot_fix(db, e, sc, a.slot, body.value)
        extra['value'] = body.value
    else:
        apply_annul(db, e, a.slot, True)
    # həmin slot indi düzdürmü (ləğv – hə)? Yox – düzəlişə baxmayaraq cavab səhvdir, apelyasiya rədd olunur
    ok = True
    if body.kind != 'annul':
        sc = db.scalar(select(ExamScan).where(ExamScan.exam_id == e.id, ExamScan.student_id == a.student_id, ExamScan.source == a.source))
        v = db.get(ExamVariant, (e.id, a.student_id))
        if sc is not None and sc.marks and v is not None:
            slots = sorted(x['slot'] for x in v.questions)
            ok = a.slot in slots and slots.index(a.slot) < len(sc.marks) and bool(sc.marks[slots.index(a.slot)])
    replies = _fix_replies(db, a.student_id)
    reply = (body.reply or '').strip() or replies[body.kind if ok else 'wrong']
    _, manual, names = _decide_core(db, ta, e, a, user, 'accept' if ok else 'reject', reply,
                                    apply_all=ok and body.kind == 'key' and body.all_same, needs_review=False)
    after = _points(db, e)
    diff = [{'student_id': k[0], 'source': k[1], 'full_name': names.get(k[0]), 'old': before.get(k), 'new': after[k]}
            for k in after if after[k] != before.get(k)]
    audit(db, user, 'update', 'exam_appeal', a.id, exam_id=e.id, student_id=a.student_id, slot=a.slot, source=a.source, op='fix',
          kind=body.kind, old_status=old_status, new_status=a.status, apply_all=a.apply_all, changes=diff, **extra)
    db.commit()
    return {'ok': True, 'status': a.status, 'changes': diff, 'manual_students': sorted(set(manual)), 'reply': reply, 'still_wrong': not ok}
