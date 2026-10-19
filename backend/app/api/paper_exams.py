"""Yazılı (kağız) rejim: mövzu testi, sınaq və sərbəst yazılı iş (docs/yazili-sinaq-ve-skan-duymesi-promtu.md §A).

Kart/skan/apelyasiya mexanizmi imtahana (exam_id) bağlıdır → yazılı iş üçün Exam yazısı yaradılır (kind: TEST | SINAQ | YI | VIK;
online_task_id / batch_id – bağlı onlayn tapşırıq / sınaq paketi) və ExamVariant-lar (sual surətləri). Sonrası – dəyişməz:
variants/print (çap), /api/scans/any (skan), exam_scans (oxunuş, qiymətləndirmə). Perspektiv plan və has_summative tələb olunmur;
məktəb və fərdi məkanda eyni işləyir. Nəticə testin öz nəticəsidir; jurnala yalnız Exam.to_journal=True olarsa düşür."""
from __future__ import annotations

import copy
import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..appeals import freeze_refs
from ..db import get_db
from ..deps import staff
from ..domain import own_numbers
from ..domain.ksq_variants import RULES_V, Shortage, bank_candidates, card_answer, generate_auto, same_variant
from ..domain.scoring import difficulty_of, question_points
from ..exam_logic import exam_label
from ..models import BankFile, Exam, ExamScan, ExamVariant, OnlineTask, TaskAttempt, User
from ..services import own_assignment, plan_ctx, today
from .common import audit, get_or_404
from .exams import _history, exam_out, exam_result

router = APIRouter(prefix='/api/paper-exams', tags=['paper-exams'])
PAPER_KINDS = ('TEST', 'SINAQ', 'YI', 'VIK')


class PaperIn(BaseModel):
    task_id: int | None = None                      # mövcud mövzu testi / sınaq (onlayn tapşırıq) → kağız variantı
    file_ids: list[int] | None = Field(None, max_length=300)   # sərbəst yazılı iş: müəllimin seçdiyi test faylları
    n: int = Field(20, ge=5, le=30)                 # sərbəst iş: sual sayı
    mcq_only: bool = False
    title: str | None = Field(None, max_length=200)
    date: dt.date | None = None
    variant_mode: Literal['same', 'different', 'same_numbers'] = 'same'
    to_journal: bool = False                        # nəticə jurnala düşsün? (standart – yox, testin öz nəticəsidir)
    viktorina: bool = False                         # file_ids bütün viktorina bazasından (bir neçə mənbə) → növ VIK
    student_ids: list[int] | None = None            # yalnız bu şagirdlər (standart: bütün sinif / tapşırığın şagirdləri)


class PaperPatch(BaseModel):
    to_journal: bool | None = None
    title: str | None = Field(None, max_length=200)
    date: dt.date | None = None


def _semester(db: Session, ta, d: dt.date) -> int:
    y = plan_ctx(db, ta).year
    return 1 if d <= y.sem1_end else 2


def _task_questions(task: OnlineTask) -> list[dict]:
    """Onlayn tapşırığın sualları → variant sualı: test (A–E), kart xanasına sığan açıq cavab, qalanı – «müəllim balı» (score)."""
    qs = [q for q in task.questions if isinstance(q, dict)]
    pts = question_points(qs)
    out = []
    for i, (q, p) in enumerate(zip(qs, pts)):
        opts = q.get('options') or []
        ans = q.get('answer')
        if q.get('kind') == 'mcq' and 2 <= len(opts) <= 5 and q.get('correct') is not None:
            kind = 'mcq'
        elif q.get('kind') == 'open' and card_answer(ans):
            kind = 'open'
        else:
            kind = 'score'
        out.append({'slot': i + 1, 'key': f'b:{q["bank_id"]}' if q.get('bank_id') else f't:{task.id}:{i}', 'kind': kind,
                    'level': difficulty_of(q)[0], 'level_actual': difficulty_of(q)[0], 'points': p, 'topic': task.title,
                    'text': q.get('text'), 'options': opts if kind == 'mcq' else None,
                    'correct': q.get('correct') if kind == 'mcq' else None,
                    'answer': ans if kind != 'mcq' else None, 'image': q.get('image'), 'bank_id': q.get('bank_id'),
                    'source': q.get('source'), 'lesson': q.get('lesson'), 'v': RULES_V})
    return out


def _next_no(db: Session, ta_id: int, kind: str) -> int:
    return 1 + (db.scalar(select(func.max(Exam.no)).where(Exam.assignment_id == ta_id, Exam.kind == kind)) or 0)


def _stats(db: Session, e: Exam) -> dict:
    vs = list(db.scalars(select(ExamVariant).where(ExamVariant.exam_id == e.id)))
    scans = [s for s in db.scalars(select(ExamScan).where(ExamScan.exam_id == e.id, ExamScan.source == 'paper'))]
    return {'variants': len(vs), 'printed': any(v.printed_at for v in vs), 'scanned': len(scans),
            'graded': sum(s.status == 'graded' for s in scans)}


@router.get('/{ta_id}/grade')
def paper_grade(ta_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Dərsin sinif rəqəmi (viktorina mövzularını sinfə görə süzmək üçün standart)."""
    from ..models import SchoolClass
    from ..services import class_grade
    ta = own_assignment(db, user, ta_id)
    return {'grade': class_grade(db, db.get(SchoolClass, ta.class_id))}


@router.get('/{ta_id}')
def list_paper(ta_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    out = []
    for e in db.scalars(select(Exam).where(Exam.assignment_id == ta.id, Exam.kind.in_(PAPER_KINDS))
                        .order_by(Exam.date.desc(), Exam.id.desc())):
        out.append({**exam_out(e), **_stats(db, e)})
    return out


@router.post('/{ta_id}')
def create_paper(ta_id: int, body: PaperIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Yazılı iş yaradır: mövcud test/sınaq (task_id) və ya sərbəst iş (file_ids). Variantlar dərhal hazır olur."""
    ta = own_assignment(db, user, ta_id)
    students = exam_roster_ids(db, ta)
    task = None
    if body.task_id is not None:
        task = get_or_404(db, OnlineTask, body.task_id, 'Test')
        if task.assignment_id != ta.id or task.exam_id is not None or task.kind == 'ksq':
            raise HTTPException(404, 'Test tapılmadı')
        if db.scalar(select(Exam.id).where(Exam.assignment_id == ta.id, Exam.online_task_id == task.id)):
            raise HTTPException(409, 'Bu test üçün yazılı variant artıq var')
        if body.variant_mode == 'different':
            raise HTTPException(400, 'Hazır testin sualları dəyişmir – «hamıya eyni» seçin (hər şagirdə fərqli sual yalnız sərbəst işdə)')
        if task.student_ids:
            students = [s for s in students if s in set(task.student_ids)]
        kind = 'SINAQ' if task.kind == 'sinaq' else 'TEST'
    elif body.file_ids:
        kind = 'VIK' if body.viktorina else 'YI'
    else:
        raise HTTPException(400, 'Hazır test seçin və ya sərbəst iş üçün test faylları göstərin')
    if body.student_ids is not None:
        students = [s for s in students if s in set(body.student_ids)]
    if not students:
        raise HTTPException(400, 'Şagird yoxdur')
    d = body.date or today()
    e = Exam(assignment_id=ta.id, kind=kind, no=_next_no(db, ta.id, kind), semester=_semester(db, ta, d), date=d, max_points=100,
             title=(body.title or (task.title if task else 'Viktorina' if body.viktorina else 'Yazılı iş'))[:200], online_task_id=task.id if task else None,
             batch_id=task.batch_id if task else None, to_journal=body.to_journal, variant_mode='numbers' if body.variant_mode == 'same_numbers' else body.variant_mode,
             extra_students=sorted(students) if body.student_ids is not None or (task and task.student_ids) else None)
    db.add(e)
    db.flush()
    try:
        if task:
            one = _task_questions(task)
            res = {sid: copy.deepcopy(one) for sid in students}
        else:
            files = list(dict.fromkeys(body.file_ids or []))
            fs = list(db.scalars(select(BankFile).where(BankFile.id.in_(files), BankFile.active.is_(True))))
            if len(fs) != len(files):
                raise HTTPException(400, 'Test faylı tapılmadı')
            topics = [(e.title or 'Yazılı iş', None)]
            by_src: dict[str, list[int]] = {}
            for f in fs:                                     # fayllar bir neçə mənbədən ola bilər (viktorina) – mənbə üzrə qruplaşdır
                by_src.setdefault(f.source_key, []).append(f.id)
            cands, seen = [], set()
            for src_key, ids in by_src.items():
                for c in bank_candidates(db, topics, src_key, {0: ids}):
                    if c.key not in seen:                    # eyni sualın (content_hash) dublikatı atılır
                        seen.add(c.key)
                        cands.append(c)
            if body.variant_mode in ('same', 'same_numbers'):
                one = same_variant(cands, body.n, seed=e.id * 7919, mcq_only=body.mcq_only)
                res = {sid: copy.deepcopy(one) for sid in students}
            else:
                res, _share = generate_auto(students, [(e.title or 'Yazılı iş', None)], cands, _history(db, ta, e, students),
                                            seed=e.id * 7919, n=body.n, mcq_only=body.mcq_only)
    except Shortage as sh:
        db.rollback()
        raise HTTPException(409, {'message': 'Seçilən fayllarda sual çatmır – sual sayını azaldın və ya fayl əlavə edin: ' + sh.message(),
                                  'shortage': sh.items})
    report = None
    if body.variant_mode == 'same_numbers':                  # eyni suallar, hər şagirdə öz ədədləri (nəticə variantda donur)
        res, report = own_numbers.apply(next(iter(res.values())), students, f'{kind}{e.no}-{e.id}')
    for i, sid in enumerate(students):
        db.add(ExamVariant(exam_id=e.id, student_id=sid, code=f'{kind}{e.no}-{i + 1:02d}', questions=freeze_refs(db, res[sid])))
    plan_ = next(iter(res.values()))
    e.items = [{'n': q['slot'], 'points': q['points'], 'standard': None, 'kind': q['kind'], 'level': q.get('level')} for q in plan_]
    e.max_points = round(sum(q['points'] for q in plan_), 2)
    audit(db, user, 'create', 'exam', e.id, kind=kind, paper=True, students=len(students), task=body.task_id)
    db.commit()
    return {'exam': exam_out(e), 'variants': len(students), 'own_numbers': report}


def exam_roster_ids(db: Session, ta) -> list[int]:
    from ..services import roster
    return [s.id for s in roster(db, ta)]


@router.patch('/{ta_id}/{exam_id}')
def patch_paper(ta_id: int, exam_id: int, body: PaperPatch, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    e = _paper(db, ta.id, exam_id)
    if body.to_journal is not None:
        e.to_journal = body.to_journal
    if body.title is not None:
        e.title = body.title
    if body.date is not None:
        e.date, e.semester = body.date, _semester(db, ta, body.date)
    audit(db, user, 'update', 'exam', e.id, to_journal=e.to_journal)
    db.commit()
    return exam_out(e)


def _paper(db: Session, ta_id: int, exam_id: int) -> Exam:
    e = get_or_404(db, Exam, exam_id, 'Yazılı iş')
    if e.assignment_id != ta_id or e.kind not in PAPER_KINDS:
        raise HTTPException(404, 'Yazılı iş tapılmadı')
    return e


@router.delete('/{ta_id}/{exam_id}')
def delete_paper(ta_id: int, exam_id: int, force: bool = False, user: User = Depends(staff), db: Session = Depends(get_db)):
    own_assignment(db, user, ta_id)
    e = _paper(db, ta_id, exam_id)
    if not force and db.scalar(select(ExamScan.id).where(ExamScan.exam_id == e.id, ExamScan.status == 'graded').limit(1)):
        raise HTTPException(409, 'Skan edilmiş nəticələr var – silmək üçün təsdiq lazımdır (force=true)')
    audit(db, user, 'delete', 'exam', e.id, kind=e.kind, paper=True)
    db.delete(e)
    db.commit()
    return {'ok': True}


@router.get('/{ta_id}/{exam_id}/results')
def paper_results(ta_id: int, exam_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Testin öz nəticəsi: kağız bal + (bağlı onlayn tapşırıq varsa) onlayn bal yanaşı, fərq ⚠."""
    own_assignment(db, user, ta_id)
    e = _paper(db, ta_id, exam_id)
    res = exam_result(ta_id, exam_id, user, db)
    online = {}
    if e.online_task_id:
        online = {a.student_id: a.points for a in db.scalars(select(TaskAttempt).where(TaskAttempt.task_id == e.online_task_id,
                                                                                         TaskAttempt.submitted_at.is_not(None)))}
    paper = {s.student_id: s.points for s in db.scalars(select(ExamScan).where(ExamScan.exam_id == e.id, ExamScan.source == 'paper',
                                                                                ExamScan.status == 'graded'))}
    for r in res['rows']:
        r['paper_points'] = paper.get(r['student_id'])
        r['online_points'] = online.get(r['student_id'])
        r['differs'] = (r['paper_points'] is not None and r['online_points'] is not None
                        and abs(r['paper_points'] - r['online_points']) >= 10)
    return {**res, 'label': exam_label(e)}
