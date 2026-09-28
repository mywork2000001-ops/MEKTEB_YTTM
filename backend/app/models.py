"""Verilənlər bazası modelləri.
Qaydalar (istifadəçinin qərarları):
- Sinif və şagird MƏKTƏBƏ (UTİS) aiddir – ortaq siyahı; müəllim sinfə «qoşulur», təkrar sinif/şagird yaranmır.
- Jurnal, qiymət, mövzu hər müəllimin öz fənni üzrə ayrıcadır (TeachingAssignment vasitəsilə).
- Silinmə = arxiv (archived_at); həmişəlik silmə yalnız arxivdən.
- Uşaq İD, pinkod, şəxsiyyət vəsiqəsi heç bir cədvəldə yoxdur."""
from __future__ import annotations

import datetime as dt
import enum

from sqlalchemy import (JSON, Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text,
                        UniqueConstraint, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Role(str, enum.Enum):
    admin = 'admin'
    teacher = 'teacher'
    student = 'student'


class Archivable:
    archived_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), default=None)


# ---------------------------------------------------------------- məktəb və istifadəçilər
class School(Base, Archivable):
    __tablename__ = 'schools'
    id: Mapped[int] = mapped_column(primary_key=True)
    utis: Mapped[str | None] = mapped_column(String(32), unique=True)   # admin daxil edir (hələ boş ola bilər)
    name: Mapped[str] = mapped_column(String(300))
    short_name: Mapped[str | None] = mapped_column(String(120))
    region: Mapped[str | None] = mapped_column(String(120))
    bells: Mapped[dict | None] = mapped_column(JSON)                      # {"1": "08:50–09:35", ...}
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)


class User(Base, Archivable):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[Role] = mapped_column(Enum(Role))
    login: Mapped[str] = mapped_column(String(64), unique=True)          # müəllim: e-poçt/ad; şagird: XC-001
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(200))
    school_id: Mapped[int | None] = mapped_column(ForeignKey('schools.id'))
    subjects: Mapped[list | None] = mapped_column(JSON)                  # müəllim: ["Riyaziyyat"]
    language: Mapped[str] = mapped_column(String(2), default='az')
    theme: Mapped[str | None] = mapped_column(String(20))
    settings_password_hash: Mapped[str | None] = mapped_column(String(255))   # Tənzimləmələr kilidi (boş = yoxdur)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)
    school: Mapped[School | None] = relationship()


# ---------------------------------------------------------------- tədris ili
class AcademicYear(Base):
    __tablename__ = 'academic_years'
    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey('schools.id'))
    name: Mapped[str] = mapped_column(String(20))                        # 2026–2027
    start: Mapped[dt.date] = mapped_column(Date)
    sem1_end: Mapped[dt.date] = mapped_column(Date)
    sem2_start: Mapped[dt.date] = mapped_column(Date)
    end: Mapped[dt.date] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint('school_id', 'name'),)


class Holiday(Base):
    __tablename__ = 'holidays'
    id: Mapped[int] = mapped_column(primary_key=True)
    year_id: Mapped[int] = mapped_column(ForeignKey('academic_years.id', ondelete='CASCADE'))
    date: Mapped[dt.date] = mapped_column(Date)
    name: Mapped[str] = mapped_column(String(120))
    __table_args__ = (UniqueConstraint('year_id', 'date'),)


# ---------------------------------------------------------------- ortaq sinif və şagird siyahısı
class SchoolClass(Base, Archivable):
    __tablename__ = 'classes'
    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey('schools.id'))
    year_id: Mapped[int] = mapped_column(ForeignKey('academic_years.id'))
    name: Mapped[str] = mapped_column(String(60))                        # «X e», «X b (riyaziyyat qrupu)»
    code: Mapped[str] = mapped_column(String(10))                        # portal kodu prefiksi: XE
    kind: Mapped[str] = mapped_column(String(10), default='TOM')         # TOM | adi | qrup
    parent_id: Mapped[int | None] = mapped_column(ForeignKey('classes.id'))   # bölünən qrup -> sinif
    split_with: Mapped[str | None] = mapped_column(String(120))          # bölünmə: paralel fənn (Biologiya – Şərqiyə m.)
    utis_class: Mapped[str | None] = mapped_column(String(20))           # UTİS: «10 e»
    exam_date: Mapped[dt.date | None] = mapped_column(Date)              # buraxılış/qəbul imtahanı (sayğac)
    bells: Mapped[dict | None] = mapped_column(JSON)                     # sinfin öz zəngi (XI peşə)
    created_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    __table_args__ = (UniqueConstraint('school_id', 'year_id', 'name'),)
    students: Mapped[list[Student]] = relationship(back_populates='cls', foreign_keys='Student.class_id')


class Student(Base, Archivable):
    __tablename__ = 'students'
    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey('schools.id'))
    class_id: Mapped[int] = mapped_column(ForeignKey('classes.id'))
    full_name: Mapped[str] = mapped_column(String(200))
    birth_date: Mapped[dt.date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(10))
    portal_code: Mapped[str] = mapped_column(String(16), unique=True)    # XE-001 (bütün müəllimlər üçün eyni)
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'))  # portal hesabı (PIN)
    score_language: Mapped[float | None] = mapped_column(Float)          # IX sinif buraxılış balları
    score_math: Mapped[float | None] = mapped_column(Float)
    score_foreign: Mapped[float | None] = mapped_column(Float)
    created_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    __table_args__ = (UniqueConstraint('school_id', 'full_name', 'birth_date', name='uq_student_person'),)
    cls: Mapped[SchoolClass] = relationship(back_populates='students', foreign_keys=[class_id])


class GroupMember(Base):
    """Bölünən qrup (X b riyaziyyat qrupu) və müəllimin öz yaratdığı tədris qrupları üçün üzvlük."""
    __tablename__ = 'group_members'
    group_id: Mapped[int] = mapped_column(ForeignKey('classes.id', ondelete='CASCADE'), primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='CASCADE'), primary_key=True)


class TeachingAssignment(Base, Archivable):
    """Müəllim sinfə «qoşulur»: fənn, həftəlik saat, cədvəl. Jurnal və plan bu bağlılığa aiddir."""
    __tablename__ = 'teaching_assignments'
    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    class_id: Mapped[int] = mapped_column(ForeignKey('classes.id'))
    subject: Mapped[str] = mapped_column(String(60))
    weekly_hours: Mapped[int] = mapped_column(Integer)
    slots: Mapped[dict] = mapped_column(JSON)                            # {"0": [3, 5], "1": [3, 6, 7]}
    has_summative: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint('teacher_id', 'class_id', 'subject'),)
    teacher: Mapped[User] = relationship()
    cls: Mapped[SchoolClass] = relationship()


# ---------------------------------------------------------------- əlavə test bazası (viktorina.html – avtomatik yenilənir)
class BankSource(Base):
    __tablename__ = 'bank_sources'
    key: Mapped[str] = mapped_column(String(32), primary_key=True)       # p007
    label: Mapped[str] = mapped_column(String(200))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)         # admin söndürə bilər (məs. TAİM)
    active: Mapped[bool] = mapped_column(Boolean, default=True)          # viktorina-da hələ də var


class BankFile(Base):
    __tablename__ = 'bank_files'
    id: Mapped[int] = mapped_column(primary_key=True)
    source_key: Mapped[str] = mapped_column(ForeignKey('bank_sources.key'))
    lesson: Mapped[str] = mapped_column(String(300))                     # mənbə daxilində fayl yolu
    label: Mapped[str] = mapped_column(String(400))
    url: Mapped[str] = mapped_column(String(600))
    sha256: Mapped[str | None] = mapped_column(String(64))
    question_count: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    checked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    changed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint('source_key', 'lesson'),)


class BankQuestion(Base):
    __tablename__ = 'bank_questions'
    id: Mapped[int] = mapped_column(primary_key=True)
    file_id: Mapped[int] = mapped_column(ForeignKey('bank_files.id'))
    n: Mapped[int] = mapped_column(Integer)                              # fayl daxilində sıra
    qid: Mapped[str | None] = mapped_column(String(40))                  # mənbədəki sual nömrəsi
    kind: Mapped[str] = mapped_column(String(10))                        # mcq | open
    text: Mapped[dict] = mapped_column(JSON)                             # {"az": ..., "ru": ..., "en": ...}
    options: Mapped[list | None] = mapped_column(JSON)                   # [{"az": ...}, ...]
    correct: Mapped[int | None] = mapped_column(Integer)                 # mcq: indeks
    answer: Mapped[str | None] = mapped_column(Text)                     # open: «a|b» qəbul edilən cavablar
    explanation: Mapped[dict | None] = mapped_column(JSON)
    image: Mapped[str | None] = mapped_column(String(600))
    content_hash: Mapped[str] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint('file_id', 'n'),)


class BankSync(Base):
    __tablename__ = 'bank_syncs'
    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    trigger: Mapped[str] = mapped_column(String(20))                     # auto | manual
    status: Mapped[str] = mapped_column(String(20), default='running')   # running | unchanged | updated | error
    files_checked: Mapped[int] = mapped_column(Integer, default=0)
    files_changed: Mapped[int] = mapped_column(Integer, default=0)
    added: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    deactivated: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(Text)


# ---------------------------------------------------------------- audit jurnalı
class AuditLog(Base):
    __tablename__ = 'audit_log'
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now, server_default=func.now())
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str] = mapped_column(String(40))                      # create | update | archive | restore | delete | login
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(40))
    details: Mapped[dict | None] = mapped_column(JSON)


class AppState(Base):
    """Kiçik açar–dəyər yaddaşı (məs. viktorina.html-in son hash-i)."""
    __tablename__ = 'app_state'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)
