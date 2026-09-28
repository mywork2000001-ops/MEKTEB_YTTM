"""KSQ / BSQ: bal -> faiz -> qiymət (0–30→2, 31–60→3, 61–80→4, 81–100→5), tapşırıq üzrə ✓/✗,
tapşırıq və standart təhlili, yarımil qiyməti = (KSQ qiymətləri cəmi / sayı) × 0,4 + BSQ × 0,6."""
from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import staff
from ..domain.rules import grade_from_points, semester_grade
from ..models import Exam, ExamScore, User
from ..services import own_assignment, plan_ctx, roster
from .common import audit, get_or_404

router = APIRouter(prefix='/api/exams', tags=['exams'])


class ItemIn(BaseModel):
    n: int = Field(ge=1)
    points: float = Field(gt=0)
    standard: str | None = Field(None, max_length=20)


class ExamIn(BaseModel):
    kind: Literal['KSQ', 'BSQ']
    no: int = Field(ge=1, le=20)
    semester: Literal[1, 2]
    date: dt.date
    max_points: float | None = Field(None, gt=0, le=1000)
    items: list[ItemIn] | None = None
    title: str | None = Field(None, max_length=3000)

    @model_validator(mode='after')
    def _max(self):
        if self.items:
            total = round(sum(i.points for i in self.items), 2)
            if self.max_points is not None and abs(self.max_points - total) > 1e-6:
                raise ValueError(f'tapşırıqların balları cəmi ({total}) maksimal bala bərabər olmalıdır')
            self.max_points = total
        if self.max_points is None:
            raise ValueError('maksimal bal və ya tapşırıqlar lazımdır')
        return self


def exam_out(e: Exam) -> dict:
    return {'id': e.id, 'kind': e.kind, 'no': e.no, 'semester': e.semester, 'date': e.date,
            'max_points': e.max_points, 'items': e.items, 'title': e.title}


def _exam(db: Session, ta_id: int, exam_id: int) -> Exam:
    e = get_or_404(db, Exam, exam_id, 'İmtahan')
    if e.assignment_id != ta_id:
        raise HTTPException(404, 'İmtahan tapılmadı')
    return e


@router.get('/{ta_id}')
def list_exams(ta_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    created = list(db.scalars(select(Exam).where(Exam.assignment_id == ta.id)
                              .order_by(Exam.semester, Exam.date, Exam.kind)))
    have = {(e.kind, e.semester, e.no) for e in created}
    planned = [{'kind': pl.assessment_type, 'no': pl.exam_no, 'semester': pl.semester, 'date': pl.date,
                'topic': pl.topic, 'created': (pl.assessment_type, pl.semester, pl.exam_no) in have}
               for pl in plan_ctx(db, ta).lessons if pl.assessment_type in ('KSQ', 'BSQ')]
    # BSQ-2 bir gündə iki saat ola bilər – bir imtahan kimi göstərilir
    seen, uniq = set(), []
    for p in planned:
        k = (p['kind'], p['semester'], p['no'])
        if k not in seen:
            seen.add(k)
            uniq.append(p)
    return {'has_summative': ta.has_summative, 'exams': [exam_out(e) for e in created], 'planned': uniq}


@router.post('/{ta_id}')
def create_exam(ta_id: int, body: ExamIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    if not ta.has_summative:
        raise HTTPException(400, 'Bu qrupda KSQ/BSQ keçirilmir (bütöv sinifdə keçirilir)')
    if db.scalar(select(Exam).where(Exam.assignment_id == ta.id, Exam.kind == body.kind,
                                    Exam.semester == body.semester, Exam.no == body.no)):
        raise HTTPException(409, f'{body.kind}-{body.no} ({body.semester}-ci yarımil) artıq var')
    e = Exam(assignment_id=ta.id, kind=body.kind, no=body.no, semester=body.semester, date=body.date,
             max_points=body.max_points, items=[i.model_dump() for i in body.items] if body.items else None,
             title=body.title)
    db.add(e)
    db.flush()
    audit(db, user, 'create', 'exam', e.id, kind=e.kind, no=e.no)
    db.commit()
    return exam_out(e)


@router.patch('/{ta_id}/{exam_id}')
def update_exam(ta_id: int, exam_id: int, body: ExamIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    has_scores = db.scalar(select(ExamScore).where(ExamScore.exam_id == e.id, ExamScore.points.is_not(None)))
    if has_scores and (body.max_points != e.max_points or (body.items and len(body.items) != len(e.items or []))):
        raise HTTPException(409, 'Nəticələr yazılıb – maksimal bal və tapşırıq sayı dəyişdirilə bilməz')
    e.kind, e.no, e.semester, e.date, e.title = body.kind, body.no, body.semester, body.date, body.title
    e.max_points = body.max_points
    e.items = [i.model_dump() for i in body.items] if body.items else None
    audit(db, user, 'update', 'exam', e.id)
    db.commit()
    return exam_out(e)


class ScoreIn(BaseModel):
    student_id: int
    points: float | None = Field(None, ge=0)
    item_marks: list[int] | None = None            # 1 = ✓, 0 = ✗
    absent: bool = False


def _row(e: Exam, sc: ExamScore | None) -> dict:
    if not sc or sc.absent or sc.points is None:
        return {'points': None, 'pct': None, 'grade': None, 'absent': bool(sc and sc.absent),
                'item_marks': sc.item_marks if sc else None}
    return {'points': sc.points, 'pct': round(sc.points * 100 / e.max_points, 1),
            'grade': grade_from_points(sc.points, e.max_points), 'absent': False, 'item_marks': sc.item_marks}


@router.put('/{ta_id}/{exam_id}/scores')
def save_scores(ta_id: int, exam_id: int, body: list[ScoreIn], user: User = Depends(staff),
                db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    ids = {s.id for s in roster(db, ta)}
    for s in body:
        if s.student_id not in ids:
            raise HTTPException(400, f'Şagird {s.student_id} bu sinifdə deyil')
        pts = s.points
        if s.item_marks is not None:
            if not e.items or len(s.item_marks) != len(e.items) or any(m not in (0, 1) for m in s.item_marks):
                raise HTTPException(400, 'Tapşırıq üzrə qeydlər (0/1) tapşırıq sayına bərabər olmalıdır')
            pts = round(sum(it['points'] * m for it, m in zip(e.items, s.item_marks)), 2)
        if pts is not None and pts > e.max_points:
            raise HTTPException(400, f'Bal maksimal baldan ({e.max_points}) çox ola bilməz')
        sc = db.get(ExamScore, (e.id, s.student_id)) or ExamScore(exam_id=e.id, student_id=s.student_id)
        sc.points, sc.item_marks, sc.absent = (None if s.absent else pts), (None if s.absent else s.item_marks), s.absent
        db.merge(sc)
    audit(db, user, 'update', 'exam_scores', e.id, count=len(body))
    db.commit()
    return exam_result(ta_id, exam_id, user, db)


@router.get('/{ta_id}/{exam_id}')
def exam_result(ta_id: int, exam_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    scores = {sc.student_id: sc for sc in db.scalars(select(ExamScore).where(ExamScore.exam_id == e.id))}
    rows = [{'student_id': s.id, 'full_name': s.full_name, **_row(e, scores.get(s.id))} for s in roster(db, ta)]
    done = [r for r in rows if r['grade'] is not None]
    dist = {g: sum(r['grade'] == g for r in done) for g in (5, 4, 3, 2)}
    items, standards = [], {}
    if e.items:
        marked = [sc.item_marks for sc in scores.values() if sc.item_marks and not sc.absent]
        for i, it in enumerate(e.items):
            ok = sum(m[i] for m in marked)
            pct = round(ok * 100 / len(marked), 1) if marked else None
            items.append({**it, 'correct': ok, 'of': len(marked), 'pct': pct})
            if it.get('standard'):
                st = standards.setdefault(it['standard'], [0, 0])
                st[0] += ok
                st[1] += len(marked)
    return {'exam': exam_out(e), 'rows': rows,
            'summary': {'written': len(done), 'absent': sum(r['absent'] for r in rows),
                        'avg_pct': round(sum(r['pct'] for r in done) / len(done), 1) if done else None,
                        'distribution': dist},
            'items': items,
            'standards': [{'standard': k, 'pct': round(a * 100 / b, 1) if b else None}
                          for k, (a, b) in sorted(standards.items())]}


@router.get('/{ta_id}/semester/{sem}')
def semester(ta_id: int, sem: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    if sem not in (1, 2):
        raise HTTPException(400, 'yarımil: 1 və ya 2')
    exams = list(db.scalars(select(Exam).where(Exam.assignment_id == ta.id, Exam.semester == sem)
                            .order_by(Exam.kind.desc(), Exam.no)))
    scores = {(sc.exam_id, sc.student_id): sc for sc in db.scalars(
        select(ExamScore).where(ExamScore.exam_id.in_([e.id for e in exams])))}
    out = []
    for s in roster(db, ta):
        ksq = [(e.no, _row(e, scores.get((e.id, s.id)))['grade']) for e in exams if e.kind == 'KSQ']
        bsq = next((_row(e, scores.get((e.id, s.id)))['grade'] for e in exams if e.kind == 'BSQ'), None)
        ksq_grades = [g for _, g in ksq if g is not None]
        out.append({'student_id': s.id, 'full_name': s.full_name, 'ksq': ksq, 'bsq': bsq,
                    'ksq_avg': round(sum(ksq_grades) / len(ksq_grades), 2) if ksq_grades else None,
                    'semester_grade': semester_grade(ksq_grades, bsq)})
    return {'semester': sem, 'formula': '(KSQ qiymətləri cəmi / sayı) × 0,4 + BSQ × 0,6', 'students': out}
