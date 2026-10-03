"""Servis qatı: müəllimin dərs bağlılığı, şagird siyahısı, işçi plan, rəsmi planın importu."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .domain.plan import Slot, working_plan
from .models import (AcademicYear, GroupMember, Holiday, PlanHold, PlanLesson, SchoolClass, Student,
                     TeachingAssignment, User)


def own_assignment(db: Session, user: User, ta_id: int) -> TeachingAssignment:
    """Jurnal və plan yalnız öz dərs bağlılığınızdır (admin də başqasının jurnalını görmür – məxfilik)."""
    ta = db.get(TeachingAssignment, ta_id)
    if not ta or ta.teacher_id != user.id or ta.archived_at:
        raise HTTPException(404, 'Dərs tapılmadı')
    return ta


def roster(db: Session, ta: TeachingAssignment) -> list[Student]:
    c = db.get(SchoolClass, ta.class_id)
    st = select(Student).where(Student.archived_at.is_(None))
    if c.kind == 'qrup':
        st = st.join(GroupMember, GroupMember.student_id == Student.id).where(GroupMember.group_id == c.id)
    else:
        st = st.where(Student.class_id == c.id)
    return list(db.scalars(st.order_by(Student.full_name)))


def class_grade(db: Session, c: SchoolClass) -> int | None:
    """Sinif rəqəmi: əl ilə yazılan → addan/UTİS-dən → bölünmə qrupunda ana sinifdən → tədris qrupunda üzvlərin
    sinfindən (hamısı eyni rəqəmdədirsə)."""
    from .domain.classes import grade_of
    g = c.grade or grade_of(c.name, c.utis_class)
    if g or c.kind != 'qrup':
        return g
    if c.parent_id:
        p = db.get(SchoolClass, c.parent_id)
        return p and class_grade(db, p)
    parents = set(db.scalars(select(Student.class_id).join(GroupMember, GroupMember.student_id == Student.id)
                             .where(GroupMember.group_id == c.id)))
    grades = {class_grade(db, db.get(SchoolClass, pid)) for pid in parents}
    return grades.pop() if len(grades) == 1 else None


IX_SUBJECTS = {'math': ('riyaziyyat', 'cəbr', 'həndəsə'),
               'foreign': ('ingilis', 'xarici', 'rus dili', 'alman', 'fransız'),
               'language': ('azərbaycan dili', 'ədəbiyyat', 'tədris dili')}
IX_LABELS = {'math': 'IX sinif buraxılış balı (riyaziyyat)', 'foreign': 'IX sinif buraxılış balı (xarici dil)',
             'language': 'IX sinif buraxılış balı (Azərbaycan dili)'}


def ix_kind(subject: str) -> str | None:
    """Fənnə uyğun IX sinif buraxılış imtahanı: riyaziyyat / xarici dil / dil; uyğun gəlmirsə None."""
    sub = (subject or '').lower()
    return next((k for k, keys in IX_SUBJECTS.items() if any(x in sub for x in keys)), None)


def ix_score(s, subject: str, grade: int | None) -> float | None:
    """Şagirdin bu fənnə uyğun IX sinif balı – yalnız X–XI siniflərdə (sinif rəqəmi bilinmirsə də götürülür)."""
    if grade is not None and grade < 10:
        return None
    k = ix_kind(subject)
    return {'math': s.score_math, 'foreign': s.score_foreign, 'language': s.score_language}.get(k) if k else None


@dataclass
class PlanCtx:
    ta: TeachingAssignment
    cls: SchoolClass
    year: AcademicYear
    lessons: list[PlanLesson]
    slots: list[Slot]
    unfit: list[int]                 # ilin sonuna sığmayan dərslərin indeksləri

    def lesson_for(self, s: Slot | None) -> PlanLesson | None:
        return self.lessons[s.index] if s and s.index is not None else None


def plan_ctx(db: Session, ta: TeachingAssignment) -> PlanCtx:
    cls = db.get(SchoolClass, ta.class_id)
    year = db.get(AcademicYear, cls.year_id)
    off = {h.date: h.name for h in db.scalars(select(Holiday).where(Holiday.year_id == year.id))}
    lessons = list(db.scalars(select(PlanLesson).where(PlanLesson.assignment_id == ta.id).order_by(PlanLesson.seq)))
    holds = {(h.date, h.period) for h in db.scalars(select(PlanHold).where(PlanHold.assignment_id == ta.id))}
    slots = {int(k): v for k, v in (ta.slots or {}).items()}
    wp, unfit = working_plan(slots, len(lessons), holds, off, year.start, year.end)
    return PlanCtx(ta, cls, year, lessons, wp, unfit)


def taught_lesson(ctx: PlanCtx, slot, entry) -> PlanLesson | None:
    """Dərsin plan mövzusu: jurnal yazılıbsa – yazılan anda qeyd olunan plan dərsi (sonradan «Mövzunu saxla»
    və ya planın yenidən yüklənməsi keçmiş dərsləri dəyişməsin), yoxdursa – işçi plan üzrə."""
    if entry is not None and entry.plan_lesson_id:
        pl = next((l for l in ctx.lessons if l.id == entry.plan_lesson_id), None)
        if pl:
            return pl
    return ctx.lesson_for(slot) if slot else None


def journal_entries(db: Session, ta_id: int, a: dt.date, b: dt.date) -> dict:
    from .models import JournalEntry
    return {(e.date, e.period): e for e in db.scalars(select(JournalEntry).where(
        JournalEntry.assignment_id == ta_id, JournalEntry.date >= a, JournalEntry.date <= b))}


def lesson_out(pl: PlanLesson | None) -> dict | None:
    if pl is None:
        return None
    return {'id': pl.id, 'seq': pl.seq, 'semester': pl.semester, 'section': pl.section, 'topic': pl.topic,
            'standards': pl.standards, 'resources': pl.resources, 'assessment': pl.assessment,
            'assessment_type': pl.assessment_type, 'exam_no': pl.exam_no, 'official_date': pl.date,
            'tt_pages': pl.tt_pages, 'tasks': pl.tasks, 'integration': pl.integration}


def import_plan(db: Session, ta: TeachingAssignment, path: str | Path) -> dict:
    """Rəsmi planı (.docx) oxuyur və sıra № üzrə yeniləyir; jurnal qeydlərinin bağlantısı qorunur."""
    from .importers.plans import parse_plan
    p = parse_plan(path)
    existing = {pl.seq: pl for pl in db.scalars(select(PlanLesson).where(PlanLesson.assignment_id == ta.id))}
    seen = set()
    for l in p.lessons:
        vals = dict(semester=l.semester, section=l.section, topic=l.topic, standards=l.standards,
                    integration=l.integration, resources=l.resources, assessment=l.assessment,
                    assessment_type=l.assessment_type, exam_no=l.exam_no, date=l.date, tt_pages=l.tt_pages,
                    tasks=[t.__dict__ for t in l.tasks])
        pl = existing.get(l.seq)
        if pl:
            for k, v in vals.items():
                setattr(pl, k, v)
        else:
            db.add(PlanLesson(assignment_id=ta.id, seq=l.seq, **vals))
        seen.add(l.seq)
    removed = [pl for s, pl in existing.items() if s not in seen]
    for pl in removed:
        db.delete(pl)
    db.flush()
    return {'file': p.file, 'lessons': len(p.lessons), 'removed': len(removed), 'warnings': p.warnings,
            'ksq': sum(l.assessment_type == 'KSQ' for l in p.lessons),
            'bsq': sum(l.assessment_type == 'BSQ' for l in p.lessons)}


SCHOOL_TZ = 'Asia/Baku'


def today() -> dt.date:
    """Məktəbin tarixi (Bakı vaxtı) – server UTC-də işləsə də gecə 00:00–04:00 arası «dünən» sayılmasın."""
    from zoneinfo import ZoneInfo
    return dt.datetime.now(ZoneInfo(SCHOOL_TZ)).date()
