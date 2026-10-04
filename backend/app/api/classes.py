"""Siniflər – məktəbin ortaq siyahısı.
- Eyni adlı sinif ikinci dəfə yaradılmır (409) – müəllim mövcud sinfə «qoşulur» (TeachingAssignment).
- Müəllim bütün siniflərin adını görür (qoşulmaq üçün), şagirdləri isə yalnız öz siniflərində.
- Silmə: arxiv (adı yazaraq təsdiq) -> geri qaytarma və ya həmişəlik silmə (yalnız arxivdən).
- Qrup (kind='qrup'): ana sinifli – sinif daxilində BÖLÜNMƏ qrupu (üzvlər yalnız ana sinifdən);
  ana sinifsiz – sərbəst TƏDRİS qrupu (olimpiada, hazırlıq: üzvlər məktəbin istənilən sinfindən)."""
from __future__ import annotations

import datetime as dt
import re

from fastapi import APIRouter, Depends, HTTPException
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import staff
from ..domain.classes import grade_of
from ..models import GroupMember, Role, SchoolClass, Student, TeachingAssignment, User
from ..services import class_grade
from .common import (ConfirmIn, audit, can_see_class, check_confirm, current_year, get_or_404, my_class_ids,
                     need_school, settings_unlocked)

router = APIRouter(prefix='/api/classes', tags=['classes'])
KINDS = ('TOM', 'adi', 'qrup')


def norm_name(s: str) -> str:
    return ' '.join(s.split())


def class_code(name: str) -> str:
    """«X e» -> XE, «XI peşə sinfi» -> XIP, «X b (riyaziyyat qrupu)» -> XBQ."""
    parts = re.sub(r'[()]', ' ', name).split()
    roman = parts[0].upper() if parts and re.fullmatch(r'[IVX]+', parts[0], re.I) else ''
    letters = ''.join(p[0] for p in parts[1:] if p and p[0].isalpha())
    tr = str.maketrans('ƏÖÜĞÇŞIİəöüğçşıi', 'EOUGCSIIEOUGCSII')
    return (roman + letters.upper().translate(tr))[:6] or 'S'


def _unique_code(db: Session, school_id: int, year_id: int, base: str) -> str:
    code, n = base, 2
    while db.scalar(select(SchoolClass).where(SchoolClass.school_id == school_id, SchoolClass.year_id == year_id,
                                              SchoolClass.code == code)):
        code, n = f'{base}{n}', n + 1
    return code


def group_type(c: SchoolClass) -> str | None:
    """bölünmə – sinif daxilində; tədris – müxtəlif siniflərdən; None – bütöv sinif."""
    return None if c.kind != 'qrup' else 'bölünmə' if c.parent_id else 'tədris'


def class_out(db: Session, c: SchoolClass, user: User, mine: set[int] | None):
    teachers = db.execute(select(User.id, User.full_name, TeachingAssignment.subject)
                          .join(TeachingAssignment, TeachingAssignment.teacher_id == User.id)
                          .where(TeachingAssignment.class_id == c.id, TeachingAssignment.archived_at.is_(None))).all()
    my_ta = db.scalar(select(TeachingAssignment).where(TeachingAssignment.class_id == c.id,
                                                       TeachingAssignment.teacher_id == user.id,
                                                       TeachingAssignment.archived_at.is_(None)))
    visible = mine is None or c.id in mine
    n = db.scalar(select(func.count()).select_from(Student).where(Student.class_id == c.id,
                                                                  Student.archived_at.is_(None)))
    if c.kind == 'qrup':
        n = db.scalar(select(func.count()).select_from(GroupMember).where(GroupMember.group_id == c.id))
    return {'id': c.id, 'name': c.name, 'code': c.code, 'kind': c.kind, 'parent_id': c.parent_id,
            'group_type': group_type(c),
            'utis_class': c.utis_class, 'grade': class_grade(db, c), 'grade_set': c.grade, 'purpose': c.purpose, 'exam_date': c.exam_date, 'bells': c.bells, 'split_with': c.split_with,
            'archived': c.archived_at is not None, 'students': n, 'can_open': visible,
            'homeroom': (lambda u: u and {'id': u.id, 'name': u.full_name})(db.get(User, c.homeroom_id) if c.homeroom_id else None),
            'teachers': [{'id': i, 'name': nm, 'subject': sb} for i, nm, sb in teachers],
            'mine': my_ta and {'ta_id': my_ta.id, 'subject': my_ta.subject, 'weekly_hours': my_ta.weekly_hours, 'slots': my_ta.slots,
                               'has_summative': my_ta.has_summative, 'program_id': my_ta.program_id,
                               'starts_on': my_ta.starts_on, 'ends_on': my_ta.ends_on, 'times': times_out(my_ta)}}


@router.get('')
def list_classes(archived: bool = False, user: User = Depends(staff), db: Session = Depends(get_db)):
    sid = need_school(user)
    year = current_year(db, sid)
    st = select(SchoolClass).where(SchoolClass.school_id == sid, SchoolClass.year_id == year.id,
                                   SchoolClass.archived_at.is_not(None) if archived else SchoolClass.archived_at.is_(None))
    mine = my_class_ids(db, user)
    rows = db.scalars(st.order_by(SchoolClass.name))
    return [class_out(db, c, user, mine) for c in rows]


# fərdi hazırlıq qrupunun məqsədi (docs/repetitor-proqramlar-promtu.md §7)
PURPOSE = Literal['sinif', 'buraxilis9', 'buraxilis11', 'qebul', 'olimpiada', 'diger']


def _private_school(db: Session, sid: int) -> bool:
    from ..models import School
    s = db.get(School, sid)
    return bool(s and s.kind == 'private')


class ClassIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    kind: str = 'TOM'
    parent_id: int | None = None
    split_with: str | None = Field(None, max_length=120)
    utis_class: str | None = Field(None, max_length=20)
    grade: int | None = Field(None, ge=1, le=12)               # boş – addan (IX a -> 9)
    exam_date: dt.date | None = None
    bells: dict[str, str] | None = None
    private: bool = False          # fərdi (repetitor) sinif – məktəbə aid deyil, müəllimin fərdi məkanında yaranır
    purpose: PURPOSE | None = None  # fərdi hazırlıq qrupunun məqsədi (proqram təklifi buna görə)

    @field_validator('kind')
    @classmethod
    def _kind(cls, v):
        if v not in KINDS:
            raise ValueError('növ: TOM, adi və ya qrup')
        return v


@router.post('')
def create_class(body: ClassIn, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    if body.private:
        from sqlalchemy.orm.attributes import set_committed_value
        from ..workspaces import ensure_private
        ws = ensure_private(db, user)
        user.active_school_id = ws.id                   # yaradandan sonra fərdi məkana keçilir
        set_committed_value(user, 'school_id', ws.id)
    sid = need_school(user)
    year = current_year(db, sid)
    name = norm_name(body.name)
    dup = db.scalar(select(SchoolClass).where(SchoolClass.school_id == sid, SchoolClass.year_id == year.id,
                                              func.lower(SchoolClass.name) == name.lower()))
    if dup:
        raise HTTPException(409, {'message': f'«{dup.name}» sinfi artıq var – ona qoşulun',
                                  'class_id': dup.id, 'archived': dup.archived_at is not None})
    if body.purpose and not _private_school(db, sid):
        raise HTTPException(400, 'Hazırlıq məqsədi yalnız fərdi (repetitor) məkanın qruplarında')
    if body.parent_id and body.kind != 'qrup':
        raise HTTPException(400, 'Ana sinif yalnız bölünmə qrupu üçün seçilir')
    if body.parent_id:
        p = get_or_404(db, SchoolClass, body.parent_id, 'Ana sinif')
        if p.school_id != sid or p.year_id != year.id:
            raise HTTPException(404, 'Ana sinif tapılmadı')
        if p.kind == 'qrup':
            raise HTTPException(400, 'Ana sinif bütöv sinif olmalıdır (qrup yox)')
    c = SchoolClass(school_id=sid, year_id=year.id, name=name, code=_unique_code(db, sid, year.id, class_code(name)),
                    kind=body.kind, parent_id=body.parent_id, split_with=body.split_with, utis_class=body.utis_class, exam_date=body.exam_date,
                    bells=body.bells, created_by=user.id, grade=body.grade or grade_of(name, body.utis_class), purpose=body.purpose)
    db.add(c)
    db.flush()
    audit(db, user, 'create', 'class', c.id, name=c.name)
    db.commit()
    return class_out(db, c, user, my_class_ids(db, user))


class ClassPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=60)
    code: str | None = Field(None, min_length=1, max_length=8, pattern=r'^[A-Za-z0-9]+$')   # sinif ID-si (XB)
    kind: str | None = None                                    # yalnız TOM <-> adi
    split_with: str | None = Field(None, max_length=120)
    utis_class: str | None = Field(None, max_length=20)
    grade: int | None = Field(None, ge=1, le=12)
    exam_date: dt.date | None = None
    bells: dict[str, str] | None = None
    purpose: PURPOSE | None = None


def _editable(db: Session, user: User, c: SchoolClass):
    """Ortaq məlumatı (ad, imtahan tarixi, zəng) sinfin müəllimi və ya admin dəyişə bilər."""
    if c.school_id != user.school_id or (user.role != Role.admin and not can_see_class(db, user, c)
                                          and not _private_school(db, c.school_id)):      # fərdi məkanda – sahibi
        raise HTTPException(403, 'Bu sinif sizin siniflərinizdən deyil')


@router.patch('/{cid}')
def update_class(cid: int, body: ClassPatch, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    c = get_or_404(db, SchoolClass, cid, 'Sinif')
    _editable(db, user, c)
    data = body.model_dump(exclude_unset=True)
    if data.get('purpose') and not _private_school(db, c.school_id):
        raise HTTPException(400, 'Hazırlıq məqsədi yalnız fərdi (repetitor) məkanın qruplarında')
    if 'kind' in data and (data['kind'] not in ('TOM', 'adi') or c.kind == 'qrup'):
        raise HTTPException(400, 'Növ yalnız TOM ↔ adi dəyişir; sinif qrupa (və ya əksinə) çevrilmir')
    if data.get('bells') is not None:                         # boş xanalar atılır; hamısı boşdursa – məktəbin zəngi
        data['bells'] = {k: v.strip() for k, v in data['bells'].items()
                         if k.isdigit() and 0 <= int(k) <= 9 and v.strip()} or None
    if 'code' in data:                                        # sinif ID-si: məktəb + tədris ilində unikal
        data['code'] = data['code'].upper()
        if db.scalar(select(SchoolClass.id).where(SchoolClass.school_id == c.school_id, SchoolClass.year_id == c.year_id,
                                                  func.upper(SchoolClass.code) == data['code'], SchoolClass.id != c.id)):
            raise HTTPException(409, f'«{data["code"]}» ID-si başqa sinifdədir')
    if 'name' in data:
        data['name'] = norm_name(data['name'])
        dup = db.scalar(select(SchoolClass).where(SchoolClass.school_id == c.school_id, SchoolClass.year_id == c.year_id,
                                                  func.lower(SchoolClass.name) == data['name'].lower(),
                                                  SchoolClass.id != c.id))
        if dup:
            raise HTTPException(409, f'«{dup.name}» adlı sinif artıq var')
    for k, v in data.items():
        setattr(c, k, v)
    audit(db, user, 'update', 'class', c.id, **{k: str(v) for k, v in data.items()})
    db.commit()
    return class_out(db, c, user, my_class_ids(db, user))


# ---------------------------------------------------------------- qoşulma (müəllim – sinif – fənn)
class TimeIn(BaseModel):
    """Fərdi qrupun dərsi: həftə günü (0 – B.e. … 6 – B.) və real vaxt."""
    weekday: int = Field(ge=0, le=6)
    start: str = Field(pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
    end: str = Field(pattern=r'^([01]\d|2[0-3]):[0-5]\d$')


def _mins(t: str) -> int:
    h, m = t.split(':')
    return int(h) * 60 + int(m)


def private_times(db: Session, user: User, c: SchoolClass, ta: TeachingAssignment | None, times: list[TimeIn]) -> tuple[dict, dict]:
    """Fərdi qrupun vaxtlarını yoxlayır və {gün: [sıra]} + {"gün:sıra": "HH:MM–HH:MM"} qaytarır. Mövcud vaxtlar öz
    sırasını saxlayır (jurnal yazıları (tarix, sıra) ilə bağlıdır), yeni vaxta ən kiçik boş sıra verilir."""
    from ..domain.calendar import WEEKDAYS
    rows = sorted(times, key=lambda x: (x.weekday, x.start))
    for x in rows:
        dur = _mins(x.end) - _mins(x.start)
        if dur <= 0:
            raise HTTPException(400, f'{WEEKDAYS[x.weekday]} {x.start}–{x.end}: bitmə başlamadan sonra olmalıdır')
        if not 20 <= dur <= 240:
            raise HTTPException(400, f'{WEEKDAYS[x.weekday]} {x.start}–{x.end}: dərsin müddəti 20 dəqiqə – 4 saat olmalıdır')
    for a, b in zip(rows, rows[1:]):
        if a.weekday == b.weekday and _mins(b.start) < _mins(a.end):
            raise HTTPException(400, f'{WEEKDAYS[a.weekday]}: {a.start}–{a.end} və {b.start}–{b.end} üst-üstə düşür')
    others = db.scalars(select(TeachingAssignment).join(SchoolClass).where(
        TeachingAssignment.teacher_id == user.id, TeachingAssignment.archived_at.is_(None), SchoolClass.school_id == c.school_id,
        SchoolClass.archived_at.is_(None), TeachingAssignment.class_id != c.id, TeachingAssignment.times.is_not(None)))
    for o in others:
        oc = db.get(SchoolClass, o.class_id)
        for k, v in (o.times or {}).items():
            wd = int(k.split(':')[0])
            s2, e2 = v.split('–')
            for x in rows:
                if x.weekday == wd and _mins(x.start) < _mins(e2) and _mins(s2) < _mins(x.end):
                    raise HTTPException(409, f'{WEEKDAYS[wd]} {x.start}–{x.end} – «{oc.name}» qrupunun dərsi ({v}) ilə üst-üstə düşür')
    old_by_day: dict[int, dict[str, int]] = {}
    for k, v in ((ta.times or {}) if ta else {}).items():
        wd, p = map(int, k.split(':'))
        old_by_day.setdefault(wd, {})[v] = p
    slots: dict[str, list[int]] = {}
    tmap: dict[str, str] = {}
    for wd in sorted({x.weekday for x in rows}):
        day = [x for x in rows if x.weekday == wd]
        if len(day) > 10:
            raise HTTPException(400, f'{WEEKDAYS[wd]}: gündə ən çox 10 dərs')
        prev = old_by_day.get(wd, {})
        used: set[int] = set()
        assigned: list[tuple[TimeIn, int]] = []
        for x in day:                                       # vaxtı dəyişməyən dərs köhnə sırasını saxlayır
            t = f'{x.start}–{x.end}'
            if t in prev and prev[t] not in used:
                used.add(prev[t]); assigned.append((x, prev[t]))
        free = (p for p in range(10) if p not in used)
        for x in day:
            if not any(x is a for a, _ in assigned):
                p = next(free); used.add(p); assigned.append((x, p))
        slots[str(wd)] = sorted(p for _, p in assigned)
        for x, p in assigned:
            tmap[f'{wd}:{p}'] = f'{x.start}–{x.end}'
    return slots, tmap


def times_out(ta: TeachingAssignment) -> list[dict] | None:
    if not ta.times:
        return None
    out = []
    for k, v in ta.times.items():
        wd, p = map(int, k.split(':'))
        s, e = v.split('–')
        out.append({'weekday': wd, 'period': p, 'start': s, 'end': e})
    return sorted(out, key=lambda x: (x['weekday'], x['start']))


class JoinIn(BaseModel):
    subject: str = Field(min_length=2, max_length=60)
    weekly_hours: int = Field(ge=1, le=12)
    slots: dict[str, list[int]] = Field(default_factory=dict)     # {"0": [3, 5]} – həftə günü -> dərs saatları
    has_summative: bool = True
    program_id: int | None = None          # əsas perspektiv plan proqramı (kitabxanadan) – qoşulanda əvvəldən seçilir
    grade: int | None = Field(None, ge=1, le=12)   # sinif rəqəmi müəyyən deyilsə (qarışıq qrup) – proqram uyğunluğu üçün
    starts_on: dt.date | None = None       # kurs müddəti (fərdi qrup); boş – tədris ilinin əvvəli / sonu
    ends_on: dt.date | None = None
    times: list[TimeIn] | None = None      # fərdi qrup: real dərs vaxtları (slots və weekly_hours bundan hesablanır)

    @field_validator('slots')
    @classmethod
    def _slots(cls, v):
        for k, ps in v.items():
            if k not in {'0', '1', '2', '3', '4', '5', '6'} or any(not 0 <= p <= 9 for p in ps):
                raise ValueError('cədvəl: gün 0–6, dərs saatı 0–9')
        return {k: sorted(set(ps)) for k, ps in v.items() if ps}


@router.post('/{cid}/join')
def join_class(cid: int, body: JoinIn, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    c = get_or_404(db, SchoolClass, cid, 'Sinif')
    if c.school_id != need_school(user) or c.archived_at:
        raise HTTPException(404, 'Sinif tapılmadı')
    from ..models import School
    private = db.get(School, c.school_id).kind == 'private'
    ta_prev = db.scalar(select(TeachingAssignment).where(TeachingAssignment.teacher_id == user.id, TeachingAssignment.class_id == cid,
                                                         TeachingAssignment.subject == body.subject))
    tmap = None
    if body.times is not None:
        if not private:
            raise HTTPException(400, 'Real dərs vaxtları yalnız fərdi (repetitor) məkanın qruplarında; məktəbdə dərs saatı seçilir')
        if not body.times:
            raise HTTPException(400, 'Ən azı bir dərs vaxtı əlavə edin')
        body.slots, tmap = private_times(db, user, c, ta_prev, body.times)
        body.weekly_hours = len(tmap)
    if any(k in ('5', '6') for k in body.slots):
        if not private:
            raise HTTPException(400, 'Şənbə və bazar dərsləri yalnız fərdi (repetitor) məkanın siniflərində olur')
    if body.starts_on or body.ends_on:
        from ..models import AcademicYear
        y = db.get(AcademicYear, c.year_id)
        a, b = body.starts_on or y.start, body.ends_on or y.end
        if not (y.start <= a <= b <= y.end):
            raise HTTPException(400, f'Kurs müddəti tədris ilinin daxilində olmalıdır ({y.start:%d.%m.%Y} – {y.end:%d.%m.%Y}) '
                                     'və başlama bitmədən əvvəl olmalıdır')
    if body.program_id and not body.slots:
        raise HTTPException(400, 'Proqramı tətbiq etmək üçün dərs saatlarını işarələyin')
    if sum(len(v) for v in body.slots.values()) not in (0, body.weekly_hours):
        raise HTTPException(400, f'Cədvəldə {body.weekly_hours} saat olmalıdır')
    ta = db.scalar(select(TeachingAssignment).where(TeachingAssignment.teacher_id == user.id,
                                                    TeachingAssignment.class_id == cid,
                                                    TeachingAssignment.subject == body.subject))
    vals = body.model_dump(exclude={'program_id', 'grade', 'times'})
    vals['times'] = tmap
    if body.grade and not c.grade:
        c.grade = body.grade
    if ta and not ta.archived_at:
        for k, v in vals.items():
            setattr(ta, k, v)
        action = 'update'
    elif ta:
        ta.archived_at = None
        for k, v in vals.items():
            setattr(ta, k, v)
        action = 'restore'
    else:
        ta = TeachingAssignment(teacher_id=user.id, class_id=cid, **vals)
        db.add(ta)
        action = 'create'
    db.flush()
    audit(db, user, action, 'teaching', ta.id, class_id=cid, subject=body.subject)
    if body.program_id and body.program_id != ta.program_id and ta.slots:
        from ..models import PlanProgram
        from ..programs import apply
        p = db.get(PlanProgram, body.program_id)
        if not p or p.archived_at or not (p.owner_id is None or p.owner_id == user.id):
            raise HTTPException(404, 'Proqram tapılmadı')
        rep = apply(db, p, ta, user)                     # əvvəlki plan (varsa) kitabxanada saxlanılır
        audit(db, user, 'update', 'plan_program', ta.id, program_id=p.id, lessons=rep['lessons'])
    db.commit()
    return class_out(db, c, user, my_class_ids(db, user))


@router.post('/{cid}/leave')
def leave_class(cid: int, subject: str, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    ta = db.scalar(select(TeachingAssignment).where(TeachingAssignment.teacher_id == user.id,
                                                    TeachingAssignment.class_id == cid,
                                                    TeachingAssignment.subject == subject,
                                                    TeachingAssignment.archived_at.is_(None)))
    if not ta:
        raise HTTPException(404, 'Bu sinifdə belə dərsiniz yoxdur')
    ta.archived_at = dt.datetime.now(dt.timezone.utc)          # jurnal qeydləri saxlanır
    audit(db, user, 'archive', 'teaching', ta.id, class_id=cid)
    db.commit()
    return {'ok': True}


# ---------------------------------------------------------------- qrup üzvləri
@router.get('/{cid}/members')
def members(cid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    c = get_or_404(db, SchoolClass, cid, 'Sinif')
    if not can_see_class(db, user, c):
        raise HTTPException(403, 'Bu sinif sizin siniflərinizdən deyil')
    return list(db.scalars(select(GroupMember.student_id).where(GroupMember.group_id == cid)))


@router.get('/{cid}/members/detail')
def members_detail(cid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Qrup üzvləri sinifləri ilə (tədris qrupunda üzvlər müxtəlif siniflərdəndir)."""
    c = get_or_404(db, SchoolClass, cid, 'Sinif')
    if not can_see_class(db, user, c):
        raise HTTPException(403, 'Bu sinif sizin siniflərinizdən deyil')
    rows = db.execute(select(Student, SchoolClass.name).join(GroupMember, GroupMember.student_id == Student.id)
                      .join(SchoolClass, SchoolClass.id == Student.class_id)
                      .where(GroupMember.group_id == cid, Student.archived_at.is_(None))
                      .order_by(SchoolClass.name, Student.full_name))
    return [{'id': s.id, 'full_name': s.full_name, 'class_id': s.class_id, 'class_name': n} for s, n in rows]


@router.get('/{cid}/candidates')
def candidates(cid: int, class_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Tədris qrupuna üzv seçmək üçün istənilən sinfin siyahısı – yalnız ad və sinif (qrupu redaktə edən müəllimə)."""
    c = get_or_404(db, SchoolClass, cid, 'Sinif')
    if c.kind != 'qrup' or c.parent_id:
        raise HTTPException(400, 'Yalnız tədris qrupu üçün')
    _editable(db, user, c)
    src = get_or_404(db, SchoolClass, class_id, 'Sinif')
    if src.school_id != c.school_id or src.year_id != c.year_id or src.kind == 'qrup' or src.archived_at:
        raise HTTPException(404, 'Sinif tapılmadı')
    rows = db.scalars(select(Student).where(Student.class_id == src.id, Student.archived_at.is_(None))
                      .order_by(Student.full_name))
    return [{'id': s.id, 'full_name': s.full_name, 'class_id': src.id, 'class_name': src.name} for s in rows]


class MembersIn(BaseModel):
    student_ids: list[int]


@router.put('/{cid}/members')
def set_members(cid: int, body: MembersIn, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    c = get_or_404(db, SchoolClass, cid, 'Sinif')
    if c.kind != 'qrup':
        raise HTTPException(400, 'Üzvlər yalnız qrup üçün təyin olunur')
    _editable(db, user, c)
    st = select(Student.id).where(Student.id.in_(body.student_ids), Student.archived_at.is_(None))
    if c.parent_id:                                       # bölünmə: yalnız ana sinifdən
        st = st.where(Student.class_id == c.parent_id)
    else:                                                 # tədris qrupu: məktəbin cari ilinin istənilən sinfindən
        st = st.join(SchoolClass, SchoolClass.id == Student.class_id).where(
            SchoolClass.school_id == c.school_id, SchoolClass.year_id == c.year_id, SchoolClass.kind != 'qrup')
    ok = set(db.scalars(st))
    bad = set(body.student_ids) - ok
    if bad:
        where = 'ana sinifdə' if c.parent_id else 'məktəbin siniflərində'
        raise HTTPException(400, f'Bu şagirdlər {where} deyil: {sorted(bad)}')
    db.query(GroupMember).filter(GroupMember.group_id == cid).delete()
    db.add_all(GroupMember(group_id=cid, student_id=s) for s in ok)
    audit(db, user, 'update', 'group_members', cid, count=len(ok))
    db.commit()
    return sorted(ok)


# ---------------------------------------------------------------- arxiv
@router.post('/{cid}/archive')
def archive_class(cid: int, body: ConfirmIn, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    c = get_or_404(db, SchoolClass, cid, 'Sinif')
    _editable(db, user, c)
    check_confirm(c.name, body.confirm)
    others = db.scalar(select(func.count()).select_from(TeachingAssignment).where(
        TeachingAssignment.class_id == cid, TeachingAssignment.teacher_id != user.id,
        TeachingAssignment.archived_at.is_(None)))
    if others and user.role != Role.admin:
        raise HTTPException(409, 'Bu sinifdə başqa müəllimlər də dərs deyir – yalnız öz dərsinizdən çıxa bilərsiniz')
    c.archived_at = dt.datetime.now(dt.timezone.utc)
    audit(db, user, 'archive', 'class', c.id, name=c.name)
    db.commit()
    return {'ok': True}


@router.post('/{cid}/restore')
def restore_class(cid: int, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    c = get_or_404(db, SchoolClass, cid, 'Sinif')
    _editable(db, user, c)
    c.archived_at = None
    audit(db, user, 'restore', 'class', c.id)
    db.commit()
    return {'ok': True}


@router.delete('/{cid}')
def delete_class(cid: int, body: ConfirmIn, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    c = get_or_404(db, SchoolClass, cid, 'Sinif')
    _editable(db, user, c)
    if not c.archived_at:
        raise HTTPException(409, 'Əvvəlcə arxivə göndərin')
    check_confirm(c.name, body.confirm)
    if db.scalar(select(func.count()).select_from(Student).where(Student.class_id == cid)):
        raise HTTPException(409, 'Sinifdə şagirdlər var – əvvəlcə onları başqa sinfə keçirin və ya silin')
    db.query(GroupMember).filter(GroupMember.group_id == cid).delete()
    db.query(TeachingAssignment).filter(TeachingAssignment.class_id == cid).delete()
    audit(db, user, 'delete', 'class', c.id, name=c.name)
    db.delete(c)
    db.commit()
    return {'ok': True}
