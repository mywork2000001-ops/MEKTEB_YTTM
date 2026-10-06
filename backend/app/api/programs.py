"""Perspektiv plan proqramları – kitabxana: siyahı, önbaxış, sinif/qrupa tətbiq, cari planı saxlamaq, arxiv.
Ümumi proqramlar (DİM «Sinif testləri» V–XI) hamıya görünür; sinif planlarından saxlananlar – yalnız sahibinə."""
from __future__ import annotations

import datetime as dt
import json
import random
import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, object_session

from ..services import ws_cond
from ..db import get_db
from ..deps import staff
from typing import Literal

from ..models import (AssignmentProgram, BankFile, BankQuestion, BankSource, OnlineTask, PlanLesson, PlanProgram, SchoolClass,
                      TeachingAssignment, User, now)
from ..programs import (DATA, ROMAN, apply, check_sections, dated, ensure_builtin, ensure_current, is_course, is_toplu, lessons_for, purposes,
                        section_names, snapshot, tpl_sections)
from ..services import class_grade, own_assignment
from .common import audit, settings_unlocked
from .tasks import _snapshot

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


def _out(p: PlanProgram, used: dict[int, list[str]], grade: int | None = None, purpose: str | None = None) -> dict:
    tpl = p.data.get('template') if p.kind == 'adaptive' else None
    return {'id': p.id, 'title': p.title, 'subject': p.subject, 'grade': p.grade, 'grade_roman': ROMAN.get(p.grade),
            'kind': p.kind, 'source': p.source, 'description': p.description, 'weekly_hours': p.weekly_hours,
            'lessons': _count(p), 'topics': sum(len(s['topics']) for s in tpl_sections(tpl)) if tpl else None,
            'course': is_course(p) or is_toplu(p), 'toplu': is_toplu(p), 'purposes': purposes(p),
            'tasks': sum(s.get('tasks') or 0 for s in tpl_sections(tpl)) if tpl and is_toplu(p) else None,
            'level': p.level, 'mine': p.owner_id is not None, 'builtin': p.key is not None, 'used_by': used.get(p.id, []),
            'fits': grade is None or p.grade is None or p.grade == grade, 'created_at': p.created_at,
            'workspace': _workspace(p), 'purpose_fits': bool(purpose) and purpose in purposes(p)}


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
    tgrade, tpurpose = None, None
    if ta_id:
        ta = own_assignment(db, user, ta_id)
        tc = db.get(SchoolClass, ta.class_id)
        tgrade, tpurpose = class_grade(db, tc), tc.purpose
    elif class_id:                                       # qoşulmazdan əvvəl (sinif/qrup seçilib, dərs bağlılığı hələ yoxdur)
        c = db.get(SchoolClass, class_id)
        if c and c.school_id == user.school_id:
            tgrade, tpurpose = class_grade(db, c), c.purpose
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
    # qrupun hazırlıq məqsədinə uyğun olanlar öndə, sonra sinfi uyğun olanlar; məktəbdə sinif proqramları kursdan əvvəl,
    # fərdi məkanda – əksinə
    rows.sort(key=lambda p: (bool(tpurpose) and tpurpose not in purposes(p), tgrade is not None and p.grade not in (None, tgrade),
                             is_course(p) != private, p.key is None, p.grade or 0, p.title))
    return [_out(p, used, tgrade, tpurpose) for p in rows]


@router.get('/{pid}')
def program_detail(pid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    p = _visible(db, user, pid)
    out = _out(p, {})
    out['sections'] = section_names(p)
    if is_toplu(p):
        from ..models import BankFile
        tpl = p.data['template']
        have = {f.lesson for f in db.scalars(select(BankFile).where(BankFile.source_key == 'p007', BankFile.active.is_(True),
                                                                    BankFile.question_count > 0))}
        out['chapters'] = [{'section': s['section'], 'part': s.get('part'), 'pages': s['pages'], 'tasks': s['tasks'],
                            'closed': s['closed'], 'p007': s['p007'], 'in_bank': s['p007'] in have} for s in tpl['sections']]
        ex = tpl.get('exam')
        out['exam'] = ex and {**ex, 'in_bank': ex['p007'] in have}
    elif is_course(p):
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


def _sections(p: PlanProgram, sections: list[str] | None) -> list[str] | None:
    try:
        return check_sections(p, sections)
    except ValueError as e:
        raise HTTPException(400, str(e))


def _q_sections(raw: str | None) -> list[str] | None:
    """Sorğu parametri: JSON massivi (bölmə adlarında vergül ola bilər)."""
    if raw is None:
        return None
    import json
    try:
        v = json.loads(raw)
    except ValueError:
        raise HTTPException(400, 'sections – JSON massivi')
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise HTTPException(400, 'sections – JSON massivi')
    return v


@router.get('/{pid}/preview/{ta_id}')
def preview(pid: int, ta_id: int, sections: str | None = None, user: User = Depends(staff), db: Session = Depends(get_db)):
    p = _visible(db, user, pid)
    ta = own_assignment(db, user, ta_id)
    lessons, rep = lessons_for(db, p, ta, _sections(p, _q_sections(sections)))
    return {**rep, 'program': p.title,
            'list': [{'seq': i, 'semester': l['semester'], 'section': l.get('section'), 'topic': l['topic'],
                      'assessment_type': l['assessment_type'], 'standards': l.get('standards') or []} for i, l in enumerate(lessons, 1)]}


class ApplyIn(BaseModel):
    sections: list[str] | None = None          # proqramın seçilmiş bölmələri (None – hamısı)


@router.post('/{pid}/apply/{ta_id}')
def apply_program(pid: int, ta_id: int, body: ApplyIn | None = None, user: User = Depends(settings_unlocked),
                  db: Session = Depends(get_db)):
    p = _visible(db, user, pid)
    ta = own_assignment(db, user, ta_id)
    rep = apply(db, p, ta, user, _sections(p, body.sections if body else None))
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


# ---------------------------------------------------------------- qoşulmadan əvvəl təxmin (qoşulma pəncərəsi)
class EstimateIn(BaseModel):
    class_id: int
    slots: dict[str, list[int]] = Field(default_factory=dict)
    times: list[dict] | None = None              # fərdi qrup: [{weekday, start, end}]
    starts_on: dt.date | None = None
    ends_on: dt.date | None = None
    has_summative: bool = True


@router.post('/{pid}/estimate')
def estimate(pid: int, body: EstimateIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Proqram bu cədvəllə neçə dərsə açılır və nə sığmır – sinfə qoşulmazdan əvvəl (heç nə yazılmır)."""
    from .classes import TimeIn, private_times
    p = _visible(db, user, pid)
    c = db.get(SchoolClass, body.class_id)
    if not c or c.school_id != user.school_id:
        raise HTTPException(404, 'Sinif tapılmadı')
    slots = body.slots
    if body.times:
        try:
            slots, _ = private_times(db, user, c, None, [TimeIn(**t) for t in body.times])
        except HTTPException as e:
            return {'lessons': 0, 'slots': 0, 'warnings': [str(e.detail)]}
    ta = TeachingAssignment(teacher_id=user.id, class_id=c.id, subject='', weekly_hours=1, slots=slots,
                            has_summative=body.has_summative, starts_on=body.starts_on, ends_on=body.ends_on)
    lessons, rep = lessons_for(db, p, ta)
    return {'lessons': rep['lessons'], 'slots': rep['sem1_slots'] + rep['sem2_slots'], 'warnings': rep['warnings']}


# ---------------------------------------------------------------- Word planı birbaşa kitabxanaya
@router.post('/import')
def import_word(file: UploadFile = File(...), title: str | None = Form(None), grade: int | None = Form(None),
                subject: str = Form('Riyaziyyat'), user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    """Rəsmi perspektiv plan (.docx) sabit proqram kimi kitabxanaya düşür; heç bir sinfə tətbiq olunmur."""
    import tempfile
    from pathlib import Path
    from ..importers.plans import parse_plan
    from ..programs import FIELDS
    name = file.filename or 'plan.docx'
    if not name.lower().endswith('.docx'):
        raise HTTPException(400, 'Word (.docx) faylı seçin')
    if grade is not None and not 1 <= grade <= 11:
        raise HTTPException(400, 'Sinif 1–11')
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / 'plan.docx'
        f.write_bytes(file.file.read())
        try:
            parsed = parse_plan(f)
        except Exception as e:                          # zədəli / plan cədvəli olmayan fayl
            raise HTTPException(400, f'Plan oxunmadı: {e}')
    if not parsed.lessons:
        raise HTTPException(400, 'Faylda perspektiv plan cədvəli tapılmadı')
    lessons = []
    for l in parsed.lessons:
        d = {k: getattr(l, k, None) for k in FIELDS}
        d['tasks'] = [t.__dict__ for t in (l.tasks or [])]
        d['standards'] = d['standards'] or []
        lessons.append(d)
    from ..domain.classes import grade_of
    stem = name.rsplit('.', 1)[0]
    p = PlanProgram(school_id=user.school_id, owner_id=user.id, subject=subject.strip() or 'Riyaziyyat',
                    grade=grade or grade_of(stem, None), kind='fixed', title=(title or '').strip() or stem[:200],
                    source=f'Word: {name}'[:300], description=f'{len(lessons)} dərs', data={'lessons': lessons})
    db.add(p)
    db.flush()
    audit(db, user, 'import', 'plan_program', p.id, file=name, lessons=len(lessons))
    db.commit()
    return {**_out(p, {}), 'warnings': parsed.warnings}


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
    extra = [{'id': ap.id, 'level': ap.level, 'note': ap.note, 'sections': ap.sections,
              'program': _out(db.get(PlanProgram, ap.program_id), {})}
             for ap in db.scalars(select(AssignmentProgram).where(AssignmentProgram.assignment_id == ta.id)
                                  .order_by(AssignmentProgram.id))]
    return {'ta_id': ta.id, 'class_name': cls.name, 'subject': ta.subject, 'grade': class_grade(db, cls),
            'grade_roman': ROMAN.get(class_grade(db, cls)), 'main': _out(main, {}) if main else None,
            'main_sections': ta.program_sections if main else None, 'extra': extra}


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
    sections: list[str] | None = None


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
    ap = AssignmentProgram(assignment_id=ta.id, program_id=p.id, level=body.level, note=body.note,
                           sections=_sections(p, body.sections))
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
    return {**dated(db, db.get(PlanProgram, ap.program_id), ta, ap.sections), 'level': ap.level, 'note': ap.note}


@router.delete('/attached/{aid}')
def detach(aid: int, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    ap, ta = _ap(db, user, aid)
    db.delete(ap)
    audit(db, user, 'delete', 'assignment_program', aid, ta_id=ta.id)
    db.commit()
    return _for(db, ta)


# ---------------------------------------------------------------- «Test toplusu» dərsi → P007 sualları (promt §4)
_P007_TAG = re.compile(r'P007:\s*([^;]+?)\s*$')


def _toplu_src() -> dict:
    return json.loads((DATA / 'dim_toplu_9_2025.json').read_text(encoding='utf-8'))


def toplu_lesson(pl: PlanLesson, src: dict) -> dict | None:
    """Plan dərsi «Test toplusu» proqramındandırsa – onun növü: chapter (fəsil dərsi) | exam | diag | mock (Cəbr/Həndəsə)."""
    m = _P007_TAG.search(pl.resources or '')
    if not m:
        return None
    tag = m.group(1)
    for c in src['chapters']:
        if c['p007']['lesson'].split('/', 1)[0] == tag:
            return {'mode': 'chapter', 'chapter': c}
    if src['exam_2025']['p007']['lesson'].split('/', 1)[0] == tag:
        return {'mode': 'exam'}
    if pl.section == 'Diaqnostika' or 'hər fəsildən' in tag:
        return {'mode': 'diag'}
    for part in ('Cəbr', 'Həndəsə'):
        if part in tag:
            return {'mode': 'mock', 'part': part}
    return None


def _p007_url(src: dict, lesson: str) -> str:
    return src['p007']['url'].replace('{lesson}', lesson)


def _p007_qs(db: Session, lesson: str) -> dict[int, BankQuestion] | None:
    """Faylın aktiv sualları qid (= toplu tapşırıq nömrəsi) üzrə; fayl bazada yoxdursa – None. qid rəqəm deyilsə – atılır."""
    f = db.scalar(select(BankFile).join(BankSource, BankSource.key == BankFile.source_key).where(
        BankFile.source_key == 'p007', BankFile.lesson == lesson, BankFile.active.is_(True), BankSource.enabled.is_(True)))
    if f is None:
        return None
    out: dict[int, BankQuestion] = {}
    for q in db.scalars(select(BankQuestion).where(BankQuestion.file_id == f.id, BankQuestion.active.is_(True))
                        .order_by(BankQuestion.n)):
        try:
            n = int(str(q.qid).strip())
        except (TypeError, ValueError):
            continue
        out.setdefault(n, q)
    return out or None


def _pick(qs: list[BankQuestion], n: int, rnd: random.Random) -> list[BankQuestion]:
    """n təsadüfi sual, qapalı : açıq ≈ 2 : 1 (birindən çatmırsa – digərindən)."""
    mcq, opn = [q for q in qs if q.kind == 'mcq'], [q for q in qs if q.kind != 'mcq']
    k = min(len(mcq), max(n - len(opn), round(n * 2 / 3)))
    got = rnd.sample(mcq, k) + rnd.sample(opn, min(len(opn), n - k))
    return got


def _used_bank_ids(db: Session, ta_id: int) -> set[int]:
    """Bu sinif/qrupa əvvəl verilmiş test bazası sualları (sınaqda təkrarlanmasın)."""
    return {q.get('bank_id') for t in db.scalars(select(OnlineTask).where(OnlineTask.assignment_id == ta_id,
                                                                          OnlineTask.archived_at.is_(None)))
            for q in (t.questions or []) if q.get('bank_id')}


@router.get('/toplu/questions')
def toplu_questions(lesson_id: int, scope: Literal['lesson', 'ev', 'chapter'] = 'lesson', n: int = 15,
                    user: User = Depends(staff), db: Session = Depends(get_db)):
    """Plan dərsinin «Test toplusu» tapşırıqları P007 bankından: dərsin S/E/M aralığı, yalnız ev tapşırığı və ya fəsildən
    n təsadüfi sual; sınaq/diaqnostika/2025 imtahanı dərsində – fəsillərdən qarışıq (əvvəl verilənlər təkrarlanmır)."""
    pl = db.get(PlanLesson, lesson_id)
    if not pl:
        raise HTTPException(404, 'Dərs tapılmadı')
    ta = own_assignment(db, user, pl.assignment_id)
    src = _toplu_src()
    info = toplu_lesson(pl, src)
    if info is None:
        raise HTTPException(400, 'Bu dərs «Test toplusu» proqramından deyil')
    n = max(1, min(n, 100))
    rnd = random.Random()
    out = {'mode': info['mode'], 'scope': scope, 'in_bank': True, 'missing': [], 'questions': []}
    picked: list[BankQuestion] = []
    if info['mode'] == 'chapter':
        c = info['chapter']
        file = c['p007']['lesson']
        out.update(file=file, url=_p007_url(src, file), chapter=f'{c["num"]}. {c["title"]}',
                   ranges=pl.tasks or [], has_ev=any(t.get('kind') == 'ev' for t in pl.tasks or []))
        qs = _p007_qs(db, file)
        if qs is None:
            out['in_bank'] = False
            return out
        if scope == 'chapter':
            picked = sorted(_pick(list(qs.values()), n, rnd), key=lambda q: int(q.qid))
            out['title'] = f'{c["title"]} · fəsil testi ({len(picked)} sual)'
        else:
            rng = [t for t in pl.tasks or [] if scope == 'lesson' or t.get('kind') == 'ev']
            if not rng:
                raise HTTPException(400, 'Bu dərsdə ev tapşırığı aralığı yoxdur')
            nums = [i for t in rng for i in range(t['start'], t['end'] + 1)]
            picked = [qs[i] for i in nums if i in qs]
            out['missing'] = [i for i in nums if i not in qs]
            a, b = min(nums), max(nums)
            out['title'] = f'{c["title"]} · tapşırıqlar {a}–{b}' + (' (ev)' if scope == 'ev' else '')
    elif info['mode'] == 'exam':
        ex = src['exam_2025']
        file = ex['p007']['lesson']
        out.update(file=file, url=_p007_url(src, file))
        qs = _p007_qs(db, file)
        if qs is None:
            out['in_bank'] = False
            return out
        picked = [qs[i] for i in sorted(qs)]
        out['missing'] = [i for i in range(1, ex['tasks'] + 1) if i not in qs]
        out['title'] = '2025 buraxılış imtahanı tapşırıqları (IX)'
    else:
        chs = [c for c in src['chapters'] if info['mode'] == 'diag' or c['part'] == info['part']]
        per = 1 if info['mode'] == 'diag' else 2
        used = _used_bank_ids(db, ta.id)
        absent = []
        for c in chs:
            qs = _p007_qs(db, c['p007']['lesson'])
            if qs is None:
                absent.append(f'{c["num"]}. {c["title"]}')
                continue
            fresh = [q for q in qs.values() if q.id not in used]
            got = _pick(fresh, per, rnd)
            if len(got) < per:                   # təzə sual qalmayıb – əvvəl verilənlərdən tamamla
                got += _pick([q for q in qs.values() if q not in got], per - len(got), rnd)
            picked += sorted(got, key=lambda q: int(q.qid))
        out['absent'] = absent
        out['in_bank'] = bool(picked)
        out['url'] = _p007_url(src, chs[0]['p007']['lesson'])
        out['title'] = ('Diaqnostik test (hər fəsildən 1 tapşırıq)' if info['mode'] == 'diag'
                        else f'Sınaq: {info["part"]} (hər fəsildən {per} tapşırıq)')
    snaps = _snapshot(db, [q.id for q in picked]) if picked else []
    out['questions'] = [{**s, 'qid': int(q.qid)} for s, q in zip(snaps, picked)]
    return out
