"""Perspektiv plan proqramları – kitabxana: siyahı, önbaxış, sinif/qrupa tətbiq, cari planı saxlamaq, arxiv.
Ümumi proqramlar (DİM «Sinif testləri» V–XI) hamıya görünür; sinif planlarından saxlananlar – yalnız sahibinə."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import staff
from typing import Literal

from ..models import AssignmentProgram, PlanProgram, SchoolClass, TeachingAssignment, User, now
from ..programs import ROMAN, apply, dated, ensure_builtin, ensure_current, lessons_for, snapshot
from ..services import class_grade, own_assignment
from .common import audit, settings_unlocked

router = APIRouter(prefix='/api/programs', tags=['programs'])


def _visible(db: Session, user: User, pid: int) -> PlanProgram:
    p = db.get(PlanProgram, pid)
    if not p or p.archived_at or not (p.owner_id is None or p.owner_id == user.id):
        raise HTTPException(404, 'Proqram tapılmadı')
    return p


def _count(p: PlanProgram) -> int | None:
    if p.kind == 'fixed':
        return len(p.data.get('lessons', []))
    return None


def _out(p: PlanProgram, used: dict[int, list[str]], grade: int | None = None) -> dict:
    tpl = p.data.get('template') if p.kind == 'adaptive' else None
    return {'id': p.id, 'title': p.title, 'subject': p.subject, 'grade': p.grade, 'grade_roman': ROMAN.get(p.grade),
            'kind': p.kind, 'source': p.source, 'description': p.description, 'weekly_hours': p.weekly_hours,
            'lessons': _count(p), 'topics': sum(len(s['topics']) for sem in tpl['semesters'] for s in sem) if tpl else None,
            'level': p.level, 'mine': p.owner_id is not None, 'builtin': p.key is not None, 'used_by': used.get(p.id, []),
            'fits': grade is None or p.grade is None or p.grade == grade, 'created_at': p.created_at}


@router.get('')
def list_programs(grade: int | None = None, subject: str | None = None, level: str | None = None, ta_id: int | None = None,
                  user: User = Depends(staff), db: Session = Depends(get_db)):
    """Kitabxana. ta_id verilsə – həmin sinif/qrupun səviyyəsinə (sinif rəqəmi) uyğun olanlar «fits» ilə işarələnir."""
    ensure_builtin(db)
    ensure_current(db, user)
    db.commit()
    st = select(PlanProgram).where(PlanProgram.archived_at.is_(None),
                                   or_(PlanProgram.owner_id.is_(None), PlanProgram.owner_id == user.id))
    if grade:
        st = st.where(PlanProgram.grade == grade)
    if subject:
        st = st.where(PlanProgram.subject == subject)
    if level:
        st = st.where(PlanProgram.level == level)
    tgrade = None
    if ta_id:
        ta = own_assignment(db, user, ta_id)
        tgrade = class_grade(db, db.get(SchoolClass, ta.class_id))
    used: dict[int, list[str]] = {}
    for ta, c in db.execute(select(TeachingAssignment, SchoolClass).join(SchoolClass).where(
            TeachingAssignment.teacher_id == user.id, TeachingAssignment.archived_at.is_(None),
            TeachingAssignment.program_id.is_not(None))):
        used.setdefault(ta.program_id, []).append(c.name)
    rows = list(db.scalars(st))
    for ap, c in db.execute(select(AssignmentProgram, SchoolClass).join(TeachingAssignment, TeachingAssignment.id == AssignmentProgram.assignment_id)
                            .join(SchoolClass, SchoolClass.id == TeachingAssignment.class_id).where(TeachingAssignment.teacher_id == user.id)):
        used.setdefault(ap.program_id, []).append(f'{c.name} (əlavə{" – " + ap.level if ap.level else ""})')
    rows.sort(key=lambda p: (tgrade is not None and p.grade not in (None, tgrade), p.key is None, p.grade or 0, p.title))
    return [_out(p, used, tgrade) for p in rows]


@router.get('/{pid}')
def program_detail(pid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    p = _visible(db, user, pid)
    out = _out(p, {})
    if p.kind == 'adaptive':
        tpl = p.data['template']
        rom = ROMAN.get(p.grade, '')
        out['outline'] = [{'semester': i + 1, 'sections': [{'section': s['section'], 'part': s.get('part'),
                                                           'topics': [f'{rom} sinif: {t}' for t in s['topics']]}
                                                          for s in sem]} for i, sem in enumerate(tpl['semesters'])]
        out['variants'] = tpl.get('variants')
    else:
        out['lesson_list'] = [{'seq': i, 'semester': l.get('semester'), 'section': l.get('section'), 'topic': l.get('topic'),
                               'assessment_type': l.get('assessment_type')} for i, l in enumerate(p.data.get('lessons', []), 1)]
    return out


@router.get('/{pid}/preview/{ta_id}')
def preview(pid: int, ta_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    p = _visible(db, user, pid)
    ta = own_assignment(db, user, ta_id)
    lessons, rep = lessons_for(db, p, ta)
    return {**rep, 'program': p.title,
            'list': [{'seq': i, 'semester': l['semester'], 'section': l.get('section'), 'topic': l['topic'],
                      'assessment_type': l['assessment_type'], 'standards': l.get('standards') or []} for i, l in enumerate(lessons, 1)]}


@router.post('/{pid}/apply/{ta_id}')
def apply_program(pid: int, ta_id: int, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    p = _visible(db, user, pid)
    ta = own_assignment(db, user, ta_id)
    rep = apply(db, p, ta, user)
    audit(db, user, 'update', 'plan_program', ta.id, program_id=p.id, lessons=rep['lessons'],
          previous_program_id=rep['previous_program_id'])
    db.commit()
    return rep


class SaveIn(BaseModel):
    title: str | None = Field(None, max_length=200)


@router.post('/save/{ta_id}')
def save_current(ta_id: int, body: SaveIn, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    p = snapshot(db, ta, user, (body.title or '').strip() or None)
    if not p:
        raise HTTPException(400, 'Bu sinif/qrupda plan yoxdur')
    audit(db, user, 'create', 'plan_program', p.id, from_ta=ta.id)
    db.commit()
    return _out(p, {})


LEVELS = Literal['Zəif', 'Orta', 'Güclü']


class PatchIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(None, max_length=2000)
    grade: int | None = Field(None, ge=1, le=11)
    level: LEVELS | None = None


@router.patch('/{pid}')
def rename(pid: int, body: PatchIn, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    p = _visible(db, user, pid)
    if p.owner_id != user.id:
        raise HTTPException(403, 'Ümumi proqram dəyişdirilmir – sinfə tətbiq edib öz nüsxənizi saxlayın')
    p.title, p.description, p.level = body.title.strip(), body.description, body.level
    if body.grade:
        p.grade = body.grade
    audit(db, user, 'update', 'plan_program', p.id)
    db.commit()
    return _out(p, {})


@router.delete('/{pid}')
def archive(pid: int, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    p = _visible(db, user, pid)
    if p.owner_id != user.id:
        raise HTTPException(403, 'Ümumi proqram silinmir')
    if db.scalar(select(TeachingAssignment.id).where(TeachingAssignment.program_id == p.id,
                                                     TeachingAssignment.archived_at.is_(None))):
        raise HTTPException(409, 'Proqram hazırda sinif/qrupda istifadə olunur – əvvəlcə başqa proqram tətbiq edin')
    p.archived_at = now()
    audit(db, user, 'archive', 'plan_program', p.id)
    db.commit()
    return {'ok': True}


# ---------------------------------------------------------------- sinif/qrupun proqramları: əsas + əlavə
def _for(db: Session, ta: TeachingAssignment) -> dict:
    cls = db.get(SchoolClass, ta.class_id)
    main = db.get(PlanProgram, ta.program_id) if ta.program_id else None
    extra = [{'id': ap.id, 'level': ap.level, 'note': ap.note, 'program': _out(db.get(PlanProgram, ap.program_id), {})}
             for ap in db.scalars(select(AssignmentProgram).where(AssignmentProgram.assignment_id == ta.id)
                                  .order_by(AssignmentProgram.id))]
    return {'ta_id': ta.id, 'class_name': cls.name, 'subject': ta.subject, 'grade': class_grade(db, cls),
            'grade_roman': ROMAN.get(class_grade(db, cls)), 'main': _out(main, {}) if main else None, 'extra': extra}


@router.get('/for/{ta_id}')
def programs_for(ta_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Sinif/qrupun proqramları: əsas (jurnal və tarixlər ona görə) və əlavə (səviyyə qrupu üçün də)."""
    ensure_builtin(db)
    ensure_current(db, user)
    db.commit()
    return _for(db, own_assignment(db, user, ta_id))


class AttachIn(BaseModel):
    level: LEVELS | None = None
    note: str | None = Field(None, max_length=300)


@router.post('/{pid}/attach/{ta_id}')
def attach(pid: int, ta_id: int, body: AttachIn, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    """Əlavə proqram: jurnala qarışmır, ayrıca dərs siyahısı (sinfin cədvəlinə görə) kimi göstərilir və çap olunur."""
    p = _visible(db, user, pid)
    ta = own_assignment(db, user, ta_id)
    if ta.program_id == p.id and body.level is None:
        raise HTTPException(409, 'Bu proqram artıq sinfin əsas proqramıdır')
    if db.scalar(select(AssignmentProgram.id).where(AssignmentProgram.assignment_id == ta.id, AssignmentProgram.program_id == p.id,
                                                    (AssignmentProgram.level == body.level) if body.level else AssignmentProgram.level.is_(None))):
        raise HTTPException(409, 'Bu proqram artıq əlavə edilib')
    ap = AssignmentProgram(assignment_id=ta.id, program_id=p.id, level=body.level, note=body.note)
    db.add(ap)
    db.flush()
    audit(db, user, 'create', 'assignment_program', ap.id, ta_id=ta.id, program_id=p.id, level=body.level)
    db.commit()
    return _for(db, ta)


def _ap(db: Session, user: User, aid: int) -> tuple[AssignmentProgram, TeachingAssignment]:
    ap = db.get(AssignmentProgram, aid)
    if not ap:
        raise HTTPException(404, 'Tapılmadı')
    return ap, own_assignment(db, user, ap.assignment_id)


@router.get('/attached/{aid}')
def attached_lessons(aid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    ap, ta = _ap(db, user, aid)
    return {**dated(db, db.get(PlanProgram, ap.program_id), ta), 'level': ap.level, 'note': ap.note}


@router.delete('/attached/{aid}')
def detach(aid: int, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    ap, ta = _ap(db, user, aid)
    db.delete(ap)
    audit(db, user, 'delete', 'assignment_program', aid, ta_id=ta.id)
    db.commit()
    return _for(db, ta)
