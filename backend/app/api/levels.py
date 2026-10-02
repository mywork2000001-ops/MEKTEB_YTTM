"""Səviyyə qrupları (Zəif / Orta / Güclü): avtomatik bölgü (önizləmə → təsdiq), əl ilə köçürmə və kilid, təkliflər,
tarixçə, paralel siniflərdən səviyyə qrupu (sərbəst tədris qrupu). Səviyyə etiketi şagird portalında göstərilmir."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import staff
from ..levels import LEVELS, WEIGHTS, preview, suggestions
from ..models import (GroupMember, LevelHistory, LevelOverride, SchoolClass, Student, TeachingAssignment, User, now)
from ..services import class_grade, own_assignment, plan_ctx, roster
from .common import audit, current_year, need_school, settings_unlocked

router = APIRouter(prefix='/api/levels', tags=['levels'])
Level = Literal['Zəif', 'Orta', 'Güclü']


class Weights(BaseModel):
    buraxilis: float = Field(WEIGHTS['buraxilis'], ge=0, le=100)
    sinaq: float = Field(WEIGHTS['sinaq'], ge=0, le=100)
    reytinq: float = Field(WEIGHTS['reytinq'], ge=0, le=100)
    diaqnostik: float = Field(WEIGHTS['diaqnostik'], ge=0, le=100)


def _set(db: Session, user: User, ta_id: int, sid: int, level: str | None, source: str, locked: bool,
         score: float | None = None, comps: dict | None = None, note: str | None = None):
    o = db.get(LevelOverride, (ta_id, sid))
    old = o.level if o else None
    if level is None:
        if o:
            db.delete(o)
    else:
        if o is None:
            o = LevelOverride(assignment_id=ta_id, student_id=sid, level=level)
            db.add(o)
        o.level, o.source, o.locked, o.note = level, source, locked, note if note is not None else o.note
        if source == 'auto':
            o.score, o.components = score, comps
    if old != level:
        db.add(LevelHistory(assignment_id=ta_id, student_id=sid, old=old, new=level, source=source, score=score,
                            by=user.id, at=now()))


@router.get('/{ta_id}')
def groups(ta_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Üç sütun: Zəif / Orta / Güclü + təyin olunmayanlar (bölgüdən, müəllimdən, kilid)."""
    ta = own_assignment(db, user, ta_id)
    cur = {o.student_id: o for o in db.scalars(select(LevelOverride).where(LevelOverride.assignment_id == ta.id))}
    out: dict[str, list] = {k: [] for k in (*LEVELS, 'Təyin edilməyib')}
    for s in roster(db, ta):
        o = cur.get(s.id)
        out[o.level if o else 'Təyin edilməyib'].append({
            'student_id': s.id, 'full_name': s.full_name, 'source': o.source if o else None, 'locked': bool(o and o.locked),
            'score': o.score if o else None, 'components': o.components if o else None, 'note': o.note if o else None})
    n_sug = len(suggestions(db, plan_ctx(db, ta))) if cur else 0
    return {'groups': out, 'suggestions': n_sug}


@router.post('/{ta_id}/preview')
def make_preview(ta_id: int, mode: Literal['fixed', 'tercile'] = 'fixed', body: Weights | None = None,
                 user: User = Depends(staff), db: Session = Depends(get_db)):
    ctx = plan_ctx(db, own_assignment(db, user, ta_id))
    return preview(db, ctx, mode, (body or Weights()).model_dump())


class ApplyIn(BaseModel):
    student_ids: list[int] = Field(min_length=1, max_length=500)
    mode: Literal['fixed', 'tercile'] = 'fixed'
    weights: Weights = Field(default_factory=Weights)


@router.post('/{ta_id}/apply')
def apply(ta_id: int, body: ApplyIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Önizləmədə seçilən şagirdlərə bölgünü tətbiq edir; kilidli (müəllimin) səviyyəyə toxunmur."""
    ta = own_assignment(db, user, ta_id)
    p = preview(db, plan_ctx(db, ta), body.mode, body.weights.model_dump())
    want = set(body.student_ids)
    n = 0
    for r in p['rows']:
        if r['student_id'] in want and r['proposed'] and not r['locked']:
            _set(db, user, ta.id, r['student_id'], r['proposed'], 'auto', False, r['score'], r['components'])
            n += 1
    audit(db, user, 'update', 'levels', ta.id, applied=n, mode=body.mode)
    db.commit()
    return {'applied': n}


class LevelIn(BaseModel):
    level: Level | None = None              # None – səviyyəni götür
    locked: bool = True
    note: str | None = Field(None, max_length=300)


@router.put('/{ta_id}/{sid}')
def set_level(ta_id: int, sid: int, body: LevelIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Əl ilə köçürmə (default – kilidli: avtomatik bölgü və təkliflər toxunmur)."""
    ta = own_assignment(db, user, ta_id)
    if sid not in {s.id for s in roster(db, ta)}:
        raise HTTPException(404, 'Şagird bu sinifdə/qrupda deyil')
    _set(db, user, ta.id, sid, body.level, 'manual', body.locked, note=body.note)
    audit(db, user, 'update', 'level', sid, level=body.level, locked=body.locked)
    db.commit()
    return {'ok': True}


@router.get('/{ta_id}/suggestions')
def get_suggestions(ta_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    return suggestions(db, plan_ctx(db, own_assignment(db, user, ta_id)))


class AcceptIn(BaseModel):
    student_ids: list[int] = Field(min_length=1, max_length=500)


@router.post('/{ta_id}/suggestions/accept')
def accept(ta_id: int, body: AcceptIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    want = set(body.student_ids)
    n = 0
    for s in suggestions(db, plan_ctx(db, ta)):
        if s['student_id'] in want:
            _set(db, user, ta.id, s['student_id'], s['proposed'], 'auto', False, s['score'], s['components'])
            n += 1
    audit(db, user, 'update', 'levels', ta.id, accepted=n)
    db.commit()
    return {'accepted': n}


@router.get('/{ta_id}/history')
def history(ta_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    names = {s.id: s.full_name for s in db.scalars(select(Student).join(
        LevelHistory, LevelHistory.student_id == Student.id).where(LevelHistory.assignment_id == ta.id))}
    return [{'student_id': h.student_id, 'full_name': names.get(h.student_id), 'old': h.old, 'new': h.new,
             'source': h.source, 'score': h.score, 'at': h.at}
            for h in db.scalars(select(LevelHistory).where(LevelHistory.assignment_id == ta.id)
                                .order_by(LevelHistory.id.desc()).limit(300))]


class CrossIn(BaseModel):
    ta_ids: list[int] = Field(min_length=1, max_length=20)
    level: Level
    name: str = Field(min_length=2, max_length=60)


@router.post('/cross-class')
def cross_class(body: CrossIn, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    """Paralel siniflərdən səviyyə qrupu: seçilən dərslərdə həmin səviyyədəki şagirdlərlə sərbəst tədris qrupu
    (məs. «IX – riyaziyyat, güclü qrup»); müəllim ona əlavə məşğələ və ya test təyin edə bilər."""
    from .classes import _unique_code, class_code, norm_name
    tas = [own_assignment(db, user, i) for i in dict.fromkeys(body.ta_ids)]
    if len({t.subject for t in tas}) > 1:
        raise HTTPException(400, 'Dərslər eyni fənn üzrə olmalıdır')
    sid = need_school(user)
    year = current_year(db, sid)
    name = norm_name(body.name)
    if db.scalar(select(SchoolClass).where(SchoolClass.school_id == sid, SchoolClass.year_id == year.id,
                                           func.lower(SchoolClass.name) == name.lower())):
        raise HTTPException(409, f'«{name}» adlı sinif/qrup artıq var')
    members = []
    for t in tas:
        lv = {o.student_id for o in db.scalars(select(LevelOverride).where(LevelOverride.assignment_id == t.id,
                                                                          LevelOverride.level == body.level))}
        members += [s.id for s in roster(db, t) if s.id in lv]
    members = list(dict.fromkeys(members))
    if not members:
        raise HTTPException(400, f'Seçilən dərslərdə «{body.level}» səviyyəli şagird yoxdur – əvvəl bölgü aparın')
    grades = {class_grade(db, db.get(SchoolClass, t.class_id)) for t in tas}
    g = SchoolClass(school_id=sid, year_id=year.id, name=name, code=_unique_code(db, sid, year.id, class_code(name)),
                    kind='qrup', parent_id=None, created_by=user.id, grade=grades.pop() if len(grades) == 1 else None)
    db.add(g)
    db.flush()
    db.add_all(GroupMember(group_id=g.id, student_id=m) for m in members)
    nta = TeachingAssignment(teacher_id=user.id, class_id=g.id, subject=tas[0].subject, weekly_hours=1, slots={},
                             has_summative=False)
    db.add(nta)
    db.flush()
    audit(db, user, 'create', 'class', g.id, name=name, level=body.level, members=len(members), from_tas=body.ta_ids)
    db.commit()
    return {'class_id': g.id, 'ta_id': nta.id, 'name': name, 'members': len(members)}
