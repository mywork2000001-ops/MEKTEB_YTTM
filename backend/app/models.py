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


# ---------------------------------------------------------------- perspektiv plan (rəsmi – dəyişmir) və geriləmə
class PlanLesson(Base):
    __tablename__ = 'plan_lessons'
    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey('teaching_assignments.id', ondelete='CASCADE'))
    seq: Mapped[int] = mapped_column(Integer)
    semester: Mapped[int] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(300))
    topic: Mapped[str] = mapped_column(Text)
    standards: Mapped[list | None] = mapped_column(JSON)
    integration: Mapped[str | None] = mapped_column(Text)
    resources: Mapped[str | None] = mapped_column(Text)
    assessment: Mapped[str | None] = mapped_column(Text)
    assessment_type: Mapped[str] = mapped_column(String(12))           # formativ | KSQ | BSQ | diaqnostik
    exam_no: Mapped[int | None] = mapped_column(Integer)
    date: Mapped[dt.date] = mapped_column(Date)                         # rəsmi tarix
    tt_pages: Mapped[str | None] = mapped_column(String(300))
    tasks: Mapped[list | None] = mapped_column(JSON)                    # [{kind, label, start, end}]
    __table_args__ = (UniqueConstraint('assignment_id', 'seq'),)


class PlanHold(Base):
    """«Mövzunu saxla»: bu yuvada mövzu növbəti dərsə keçir, işçi plan bir dərs sürüşür."""
    __tablename__ = 'plan_holds'
    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey('teaching_assignments.id', ondelete='CASCADE'))
    date: Mapped[dt.date] = mapped_column(Date)
    period: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(String(300))
    created_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    __table_args__ = (UniqueConstraint('assignment_id', 'date', 'period'),)


# ---------------------------------------------------------------- jurnal
class JournalEntry(Base):
    """Bir dərs saatı (bölünən qrup öz bağlılığı ilə ayrıca yazılır)."""
    __tablename__ = 'journal_entries'
    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey('teaching_assignments.id', ondelete='CASCADE'))
    date: Mapped[dt.date] = mapped_column(Date)
    period: Mapped[int] = mapped_column(Integer)
    plan_lesson_id: Mapped[int | None] = mapped_column(ForeignKey('plan_lessons.id', ondelete='SET NULL'))
    topic: Mapped[str | None] = mapped_column(Text)                    # əl ilə dəyişdirilibsə
    homework: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    __table_args__ = (UniqueConstraint('assignment_id', 'date', 'period'),)


class Attendance(Base):
    __tablename__ = 'attendance'
    entry_id: Mapped[int] = mapped_column(ForeignKey('journal_entries.id', ondelete='CASCADE'), primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='CASCADE'), primary_key=True)
    status: Mapped[str] = mapped_column(String(10))                    # var | yox | üzrlü | gecikdi


class Mark(Base):
    """Formativ qiymət. Test: düzgün cavab sayı / sual sayı -> faiz -> qiymət (avtomatik)."""
    __tablename__ = 'marks'
    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey('journal_entries.id', ondelete='CASCADE'))
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='CASCADE'))
    kind: Mapped[str] = mapped_column(String(10))                      # şifahi | yazılı | test
    grade: Mapped[int] = mapped_column(Integer)
    test_correct: Mapped[int | None] = mapped_column(Integer)
    test_total: Mapped[int | None] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(String(300))
    __table_args__ = (UniqueConstraint('entry_id', 'student_id', 'kind'),)


class HomeworkCheck(Base):
    __tablename__ = 'homework_checks'
    entry_id: Mapped[int] = mapped_column(ForeignKey('journal_entries.id', ondelete='CASCADE'), primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='CASCADE'), primary_key=True)
    status: Mapped[str] = mapped_column(String(10))                    # etdi | qismən | etmədi | köçürüb


# ---------------------------------------------------------------- KSQ / BSQ
class Exam(Base):
    __tablename__ = 'exams'
    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey('teaching_assignments.id', ondelete='CASCADE'))
    kind: Mapped[str] = mapped_column(String(3))                       # KSQ | BSQ
    no: Mapped[int] = mapped_column(Integer)
    semester: Mapped[int] = mapped_column(Integer)
    date: Mapped[dt.date] = mapped_column(Date)
    max_points: Mapped[float] = mapped_column(Float)
    items: Mapped[list | None] = mapped_column(JSON)                   # [{"n":1,"points":1,"standard":"1.2.3"}]
    title: Mapped[str | None] = mapped_column(String(300))
    __table_args__ = (UniqueConstraint('assignment_id', 'kind', 'semester', 'no'),)


class ExamScore(Base):
    __tablename__ = 'exam_scores'
    exam_id: Mapped[int] = mapped_column(ForeignKey('exams.id', ondelete='CASCADE'), primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='CASCADE'), primary_key=True)
    points: Mapped[float | None] = mapped_column(Float)
    item_marks: Mapped[list | None] = mapped_column(JSON)              # [1, 0, 1, …] – tapşırıq üzrə ✓/✗
    absent: Mapped[bool] = mapped_column(Boolean, default=False)


# ---------------------------------------------------------------- onlayn tapşırıqlar (vaxtlı testlər)
class OnlineTask(Base, Archivable):
    """Suallar yaradılanda SURƏT kimi saxlanılır – test bazası sonra dəyişsə də tapşırıq dəyişmir."""
    __tablename__ = 'online_tasks'
    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey('teaching_assignments.id', ondelete='CASCADE'))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    opens_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    closes_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    duration_min: Mapped[int] = mapped_column(Integer)                  # həll müddəti
    questions: Mapped[list] = mapped_column(JSON)                       # [{bank_id, kind, text, options, correct, answer, image, explanation}]
    shuffle: Mapped[bool] = mapped_column(Boolean, default=True)
    show_answers: Mapped[str] = mapped_column(String(12), default='after_close')   # after_close | after_submit | never
    student_ids: Mapped[list | None] = mapped_column(JSON)              # None = bütün sinif/qrup
    created_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)


class TaskAttempt(Base):
    __tablename__ = 'task_attempts'
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey('online_tasks.id', ondelete='CASCADE'))
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='CASCADE'))
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)
    deadline: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    order: Mapped[list] = mapped_column(JSON)                           # sualların şagirdə göstərilən sırası
    answers: Mapped[dict] = mapped_column(JSON, default=dict)           # {"sual indeksi": cavab}
    submitted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    auto_submitted: Mapped[bool] = mapped_column(Boolean, default=False)
    correct: Mapped[int | None] = mapped_column(Integer)
    total: Mapped[int | None] = mapped_column(Integer)
    grade: Mapped[int | None] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint('task_id', 'student_id'),)


# ---------------------------------------------------------------- daxili çat (tam məxfilik)
class ChatRoom(Base):
    __tablename__ = 'chat_rooms'
    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey('schools.id'))
    kind: Mapped[str] = mapped_column(String(10))                      # class | dm | staff
    class_id: Mapped[int | None] = mapped_column(ForeignKey('classes.id', ondelete='CASCADE'))
    dm_key: Mapped[str | None] = mapped_column(String(40), unique=True)   # «dm:5:9» – iki istifadəçi
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)


class ChatMember(Base):
    __tablename__ = 'chat_members'
    room_id: Mapped[int] = mapped_column(ForeignKey('chat_rooms.id', ondelete='CASCADE'), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    last_read_id: Mapped[int] = mapped_column(Integer, default=0)


class ChatMessage(Base):
    __tablename__ = 'chat_messages'
    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey('chat_rooms.id', ondelete='CASCADE'))
    sender_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    text: Mapped[str | None] = mapped_column(Text)
    file_name: Mapped[str | None] = mapped_column(String(200))          # istifadəçinin fayl adı
    file_key: Mapped[str | None] = mapped_column(String(80))            # diskdə təsadüfi ad
    file_type: Mapped[str | None] = mapped_column(String(60))           # image/* | application/pdf | audio/*
    file_size: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)
    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class ChatReport(Base):
    """«!» – şagird mesajı müəllimə bildirir; müəllim YALNIZ bildirilən mesajı görür."""
    __tablename__ = 'chat_reports'
    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey('chat_messages.id', ondelete='CASCADE'))
    reporter_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    class_id: Mapped[int | None] = mapped_column(ForeignKey('classes.id'))
    reason: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint('message_id', 'reporter_id'),)
