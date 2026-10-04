"""Perspektiv plan proqramları – kitabxana: siyahı, önbaxış, sinif/qrupa tətbiq, cari planı saxlamaq, arxiv.
Ümumi proqramlar (DİM «Sinif testləri» V–XI) hamıya görünür; sinif planlarından saxlananlar – yalnız sahibinə."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, object_session

from ..services import ws_cond
from ..db import get_db
from ..deps import staff
from typing import Literal

from ..models import AssignmentProgram, PlanProgram, SchoolClass, TeachingAssignment, User, now
from ..programs import ROMAN, apply, dated, ensure_builtin, ensure_current, is_course, lessons_for, purposes, snapshot, tpl_sections
from ..services import class_grade, own_assignment
from .common import audit, settings_unlocked

router = APIRouter(prefix='/api/programs', tags=['programs'])


def _visible(db: Session, user: User, pid: int) -> PlanProgram:
    p = db.get(PlanProgram, pid)
    if not p or p.archived_at or not (p.owner_id is None or p.owner_id == user.id):
        raise HTTPException(404, 'Proqram tapılmadı')
    return p


def _is_private(db: Session, user: User) -> bool:
    from ..models import School
    sc = db.get(School, user.school_id) if user.school_id else None
    return bool(sc and sc.kind == 'private')


def _count(p: PlanProgram) -> int | None:
    if p.kind == 'fixed':
        return len(p.data.get('lessons', []))
    return None


def _workspace(p: PlanProgram) -> str | None:
    """Proqramın mənbə məkanı: 'school' | 'private'; ümumi (kitab) proqramı – None."""
    if p.school_id is None:
        return None
    from ..models import School
    s = object_session(p).get(School, p.school_id)
    return s.kind if s else None


def _out(p: PlanProgram, used: dict[int, list[str]], grade: int | None = None) -> dict:
    tpl = p.data.get('template') if p.kind == 'adaptive' else None
    return {'id': p.id, 'title': p.title, 'subject': p.subject, 'grade': p.grade, 'grade_roman': ROMAN.get(p.grade),
            'kind': p.kind, 'source': p.source, 'description': p.description, 'weekly_hours': p.weekly_hours,
            'lessons': _count(p), 'topics': sum(len(s['topics']) for s in tpl_sections(tpl)) if tpl else None,
            'course': is_course(p), 'purposes': purposes(p),
            'level': p.level, 'mine': p.owner_id is not None, 'builtin': p.key is not None, 'used_by': used.get(p.id, []),
            'fits': grade is None or p.grade is None or p.grade == grade, 'created_at': p.created_at,
            'workspace': _workspace(p)}


@router.get('')
def list_programs(grade: int | None = None, subject: str | None = None, level: str | None = None, ta_id: int | None = None,
                  class_id: int | None = None, grade_hint: int | None = None, user: User = Depends(staff),
                  db: Session = Depends(get_db)):
    """Kitabxana. ta_id verilsə – həmin sinif/qrupun səviyyəsinə (sinif rəqəmi) uyğun olanlar «fits» ilə işarələnir;
    grade_hint – sinif rəqəmi müəyyən olunmayan qrup üçün qoşulma formasında seçilən rəqəm."""
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
    elif class_id:                                       # qoşulmazdan əvvəl (sinif/qrup seçilib, dərs bağlılığı hələ yoxdur)
        c = db.get(SchoolClass, class_id)
        if c and c.school_id == user.school_id:
            tgrade = class_grade(db, c)
    if tgrade is None and grade_hint:
        tgrade = grade_hint
    used: dict[int, list[str]] = {}
    for ta, c in db.execute(select(TeachingAssignment, SchoolClass).join(SchoolClass).where(
            TeachingAssignment.teacher_id == user.id, ws_cond(user), TeachingAssignment.archived_at.is_(None),
            TeachingAssignment.program_id.is_not(None))):
        used.setdefault(ta.program_id, []).append(c.name)
    rows = list(db.scalars(st))
    for ap, c in db.execute(select(AssignmentProgram, SchoolClass).join(TeachingAssignment, TeachingAssignment.id == AssignmentProgram.assignment_id)
                            .join(SchoolClass, SchoolClass.id == TeachingAssignment.class_id).where(TeachingAssignment.teacher_id == user.id, ws_cond(user))):
        used.setdefault(ap.program_id, []).append(f'{c.name} (əlavə{" – " + ap.level if ap.level else ""})')
    private = _is_private(db, user)
    # uyğun sinif öndə; məktəbdə sinif proqramları kursdan əvvəl, fərdi məkanda – əksinə
    rows.sort(key=lambda p: (tgrade is not None and p.grade not in (None, tgrade), is_course(p) != private, p.key is None,
                             p.grade or 0, p.title))
    return [_out(p, used, tgrade) for p in rows]


@router.get('/{pid}')
def program_detail(pid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    p = _visible(db, user, pid)
    out = _out(p, {})
    if is_course(p):
        tpl = p.data['template']
        out['outline'] = [{'semester': None, 'sections': [{'section': s['section'], 'part': s.get('part'), 'topics': s['topics']}
                                                          for s in tpl['sections']]}]
        out['options'] = {k: tpl.get(k) for k in ('mock_after_section', 'mock_every', 'final_mock')}
    elif p.kind == 'adaptive':
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


# ---------------------------------------------------------------- müəllimin kurs (repetitor) proqramı
PURPOSES = Literal['sinif', 'buraxilis9', 'buraxilis11', 'qebul', 'olimpiada', 'diger']


class CourseIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    subject: str = Field('Riyaziyyat', min_length=2, max_length=60)
    grade: int | None = Field(None, ge=1, le=11)
    level: LEVELS | None = None
    purposes: list[PURPOSES] = Field(default_factory=list)
    description: str | None = Field(None, max_length=2000)
    outline: str = Field(min_length=1, max_length=50000)    # «# Bölmə» sətri – bölmə; digər sətirlər – mövzu
    mock_after_section: bool = False
    mock_every: int = Field(0, ge=0, le=40)                  # hər N mövzu dərsindən sonra aralıq sınaq; 0 – yox
    final_mock: bool = True


def parse_outline(text: str) -> list[dict]:
    import re
    sections: list[dict] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith('#'):
            sections.append({'section': line.lstrip('#').strip() or 'Bölmə', 'topics': []})
            continue
        topic = re.sub(r'^(?:[-–•*]|\d+[.)])\s*', '', line).strip()
        if not topic:
            continue
        if not sections:
            sections.append({'section': 'Ümumi', 'topics': []})
        sections[-1]['topics'].append(topic[:300])
    sections = [s for s in sections if s['topics']]
    if not sections:
        raise HTTPException(400, 'Ən azı bir mövzu yazın (bölmə başlığı «# » ilə başlayır)')
    return sections


def _course_data(body: CourseIn) -> dict:
    return {'template': {'format': 'course', 'sections': parse_outline(body.outline), 'mock_after_section': body.mock_after_section,
                         'mock_every': body.mock_every, 'final_mock': body.final_mock}, 'purposes': body.purposes}


@router.post('/course')
def create_course(body: CourseIn, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    data = _course_data(body)
    n = sum(len(s['topics']) for s in data['template']['sections'])
    p = PlanProgram(school_id=user.school_id, owner_id=user.id, subject=body.subject.strip(), grade=body.grade, kind='adaptive',
                    title=body.title.strip(), source='Müəllimin kurs proqramı', level=body.level,
                    description=body.description or f'{len(data["template"]["sections"])} bölmə, {n} mövzu', data=data)
    db.add(p)
    db.flush()
    audit(db, user, 'create', 'plan_program', p.id, course=True, topics=n)
    db.commit()
    return _out(p, {})


@router.put('/{pid}/course')
def update_course(pid: int, body: CourseIn, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    p = _visible(db, user, pid)
    if p.owner_id != user.id or not is_course(p):
        raise HTTPException(403, 'Yalnız öz kurs proqramınızı redaktə edə bilərsiniz')
    p.data = _course_data(body)
    p.title, p.subject, p.grade, p.level = body.title.strip(), body.subject.strip(), body.grade, body.level
    if body.description is not None:
        p.description = body.description
    audit(db, user, 'update', 'plan_program', p.id, course=True)
    db.commit()
    return _out(p, {})


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
