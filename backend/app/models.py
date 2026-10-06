"""Verilənlər bazası modelləri.
Qaydalar (istifadəçinin qərarları):
- Sinif və şagird MƏKTƏBƏ (UTİS) aiddir – ortaq siyahı; müəllim sinfə «qoşulur», təkrar sinif/şagird yaranmır.
- Jurnal, qiymət, mövzu hər müəllimin öz fənni üzrə ayrıcadır (TeachingAssignment vasitəsilə).
- Silinmə = arxiv (archived_at); həmişəlik silmə yalnız arxivdən.
- Uşaq İD, pinkod, şəxsiyyət vəsiqəsi heç bir cədvəldə yoxdur."""
from __future__ import annotations

import datetime as dt
import enum

from sqlalchemy import (JSON, Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, LargeBinary, String, Text,
                        UniqueConstraint, false, func, text)
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
    # rəsmi sənədlər: {'deputy': 'Direktor müavini (tədris işləri üzrə) adı', 'director': '...'}
    doc_settings: Mapped[dict | None] = mapped_column(JSON)
    # school – adi məktəb; private – müəllimin fərdi (repetitor) məkanı: məktəbə aid deyil, yalnız sahibi görür
    kind: Mapped[str] = mapped_column(String(10), default='school', server_default='school')
    owner_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', use_alter=True, name='fk_school_owner'))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)


class User(Base, Archivable):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[Role] = mapped_column(Enum(Role))
    login: Mapped[str] = mapped_column(String(64), unique=True)          # müəllim: e-poçt/ad; şagird: XC-001
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(200))
    school_id: Mapped[int | None] = mapped_column(ForeignKey('schools.id'))
    active_school_id: Mapped[int | None] = mapped_column(ForeignKey('schools.id'))   # aktiv məkan (fərdi məkan və ya None – əsas məktəb)
    subjects: Mapped[list | None] = mapped_column(JSON)                  # müəllim: ["Riyaziyyat"]
    language: Mapped[str] = mapped_column(String(2), default='az')
    theme: Mapped[str | None] = mapped_column(String(20))
    settings_password_hash: Mapped[str | None] = mapped_column(String(255))   # Tənzimləmələr kilidi (boş = yoxdur)
    ai_settings: Mapped[dict | None] = mapped_column(JSON)               # {provider, model, base_url, key(şifrəli)} – müəllimin öz açarı
    avatar: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)   # çat şəkli (≤ 300 KB, 256 px)
    avatar_type: Mapped[str | None] = mapped_column(String(20))
    avatar_v: Mapped[int | None] = mapped_column(Integer)                # versiya (keş üçün); boş – şəkil yoxdur
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)
    school: Mapped[School | None] = relationship(foreign_keys=[school_id])


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
    grade: Mapped[int | None] = mapped_column(Integer)                   # sinif rəqəmi (IX a -> 9); eyni mövzulu siniflər üçün
    # fərdi hazırlıq qrupunun məqsədi: sinif | buraxilis9 | buraxilis11 | qebul | olimpiada | diger (məktəb sinfində – None)
    purpose: Mapped[str | None] = mapped_column(String(20))
    exam_date: Mapped[dt.date | None] = mapped_column(Date)              # buraxılış/qəbul imtahanı (sayğac)
    bells: Mapped[dict | None] = mapped_column(JSON)                     # sinfin öz zəngi (XI peşə)
    homeroom_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'))   # sinif rəhbəri (yalnız bütöv sinif)
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
    initial_pin: Mapped[str | None] = mapped_column(Text)               # şifrələnmiş ilkin PIN (çap üçün); dəyişəndə silinir
    score_language: Mapped[float | None] = mapped_column(Float)          # IX sinif buraxılış balları
    score_math: Mapped[float | None] = mapped_column(Float)
    score_foreign: Mapped[float | None] = mapped_column(Float)
    guardians: Mapped[list | None] = mapped_column(JSON)                 # [{name, relation, phone}] – yalnız sinif rəhbəri/admin görür
    phone: Mapped[str | None] = mapped_column(String(30))                # şagirdin öz telefonu (+994 50 123 45 67) – rəhbər/admin
    left_reason: Mapped[str | None] = mapped_column(String(300))         # passiv: «başqa məktəbə köçdü» və s.
    left_on: Mapped[dt.date | None] = mapped_column(Date)                # məktəbdən getdiyi tarix
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
    # cari perspektiv plan proqramı (kitabxanadan seçilib; None – köhnə qaydada yüklənmiş plan)
    program_id: Mapped[int | None] = mapped_column(ForeignKey('plan_programs.id', ondelete='SET NULL', use_alter=True))
    # kurs müddəti (fərdi qrup: məs. noyabr–yanvar); None – tədris ilinin əvvəli / sonu
    starts_on: Mapped[dt.date | None] = mapped_column(Date)
    ends_on: Mapped[dt.date | None] = mapped_column(Date)
    # fərdi qrupun real dərs vaxtları: {"<həftə günü>:<sıra>": "17:00–18:30"}; None – məktəb zəngi (slots-dakı sıra = dərs saatı)
    times: Mapped[dict | None] = mapped_column(JSON)
    # əsas proqramdan seçilmiş bölmələr (None – hamısı)
    program_sections: Mapped[list | None] = mapped_column(JSON)
    # hər plan dərsinə avtomatik mövzu testi (X–XI – P0010, «Test toplusu» – P007), dərs günü yaradılır (app/auto_tests.py)
    auto_tests: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    __table_args__ = (UniqueConstraint('teacher_id', 'class_id', 'subject'),)
    teacher: Mapped[User] = relationship()
    cls: Mapped[SchoolClass] = relationship()


class PlanProgram(Base, Archivable):
    """Perspektiv plan proqramı – sinfə bağlı deyil; müəllim sinif/qrup üçün seçib tətbiq edir.
    fixed – hazır dərs siyahısı (əvvəlki Word planlar, sinifdən saxlanmış planlar);
    adaptive – bölmə/mövzu şablonu (məs. DİM «Sinif testləri»), sinfin cədvəlinə görə dərslərə açılır."""
    __tablename__ = 'plan_programs'
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str | None] = mapped_column(String(60), unique=True)          # daxili proqramlar: dim-sinif-testleri-10
    school_id: Mapped[int | None] = mapped_column(ForeignKey('schools.id'))   # None – ümumi (hamıya görünür)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'))       # None – ümumi
    title: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(60))
    grade: Mapped[int | None] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(10))                              # fixed | adaptive
    source: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    weekly_hours: Mapped[int | None] = mapped_column(Integer)
    level: Mapped[str | None] = mapped_column(String(10))                      # None – ümumi; Zəif | Orta | Güclü
    data: Mapped[dict] = mapped_column(JSON)                                    # fixed: {"lessons": [...]}, adaptive: şablon
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)


class AssignmentProgram(Base):
    """Sinif/qrupun ƏLAVƏ proqramları (əsas proqram – TeachingAssignment.program_id, jurnal ona görə gedir).
    Əlavə proqram jurnala qarışmır: öz dərs siyahısı sinfin cədvəlinə görə ayrıca göstərilir və çap olunur;
    level – sinif daxilində səviyyə qrupu üçün (Zəif / Orta / Güclü), None – bütün sinif."""
    __tablename__ = 'assignment_programs'
    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey('teaching_assignments.id', ondelete='CASCADE'))
    program_id: Mapped[int] = mapped_column(ForeignKey('plan_programs.id', ondelete='CASCADE'))
    level: Mapped[str | None] = mapped_column(String(10))
    note: Mapped[str | None] = mapped_column(String(300))
    sections: Mapped[list | None] = mapped_column(JSON)                         # seçilmiş bölmələr (None – hamısı)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint('assignment_id', 'program_id', 'level'),)


# ---------------------------------------------------------------- əlavə test bazası (viktorina.html – avtomatik yenilənir)
class BankSource(Base):
    __tablename__ = 'bank_sources'
    key: Mapped[str] = mapped_column(String(32), primary_key=True)       # p007
    label: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)         # admin söndürə bilər (məs. TAİM)
    active: Mapped[bool] = mapped_column(Boolean, default=True)          # viktorina-da hələ də var


class BankFile(Base):
    __tablename__ = 'bank_files'
    id: Mapped[int] = mapped_column(primary_key=True)
    source_key: Mapped[str] = mapped_column(ForeignKey('bank_sources.key'))
    lesson: Mapped[str] = mapped_column(Text)                            # mənbə daxilində fayl yolu
    label: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(String(64))
    question_count: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    checked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    changed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    kind: Mapped[str] = mapped_column(String(12), default='movzu')       # movzu | sinaq | yekun | diaqnostik (bank/classify.py)
    grades: Mapped[list | None] = mapped_column(JSON)                    # [9] – hansı siniflər üçün
    subject: Mapped[str | None] = mapped_column(String(60), default='Riyaziyyat')
    meta_locked: Mapped[bool] = mapped_column(Boolean, default=False)    # admin əl ilə düzəldib – avtomatik təsnifat toxunmur
    __table_args__ = (UniqueConstraint('source_key', 'lesson'),)


class BankQuestion(Base):
    __tablename__ = 'bank_questions'
    id: Mapped[int] = mapped_column(primary_key=True)
    file_id: Mapped[int] = mapped_column(ForeignKey('bank_files.id'))
    n: Mapped[int] = mapped_column(Integer)                              # fayl daxilində sıra
    qid: Mapped[str | None] = mapped_column(Text)                        # mənbədəki sual nömrəsi
    kind: Mapped[str] = mapped_column(String(10))                        # mcq | open
    text: Mapped[dict] = mapped_column(JSON)                             # {"az": ..., "ru": ..., "en": ...}
    options: Mapped[list | None] = mapped_column(JSON)                   # [{"az": ...}, ...]
    correct: Mapped[int | None] = mapped_column(Integer)                 # mcq: indeks
    answer: Mapped[str | None] = mapped_column(Text)                     # open: «a|b» qəbul edilən cavablar
    explanation: Mapped[dict | None] = mapped_column(JSON)
    image: Mapped[str | None] = mapped_column(Text)                      # URL və ya data: URI (uzun ola bilər)
    content_hash: Mapped[str] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint('file_id', 'n'),)


class BankSync(Base):
    __tablename__ = 'bank_syncs'
    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    trigger: Mapped[str] = mapped_column(String(20))                     # auto | manual | hook
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
    school_id: Mapped[int | None] = mapped_column(Integer)                  # yazının məkanı (fərdi məkan adminə görünmür)


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
    section: Mapped[str | None] = mapped_column(Text)
    topic: Mapped[str] = mapped_column(Text)
    standards: Mapped[list | None] = mapped_column(JSON)
    integration: Mapped[str | None] = mapped_column(Text)
    resources: Mapped[str | None] = mapped_column(Text)
    assessment: Mapped[str | None] = mapped_column(Text)
    assessment_type: Mapped[str] = mapped_column(String(12))           # formativ | KSQ | BSQ | diaqnostik
    exam_no: Mapped[int | None] = mapped_column(Integer)
    date: Mapped[dt.date] = mapped_column(Date)                         # rəsmi tarix
    tt_pages: Mapped[str | None] = mapped_column(Text)
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


class TopicProgress(Base):
    """Mövzu icrası – müəllimin əl ilə qeydi (jurnaldan üstündür). Rəsmi plan dəyişmir; planın yenidən yüklənməsi
    qeydi saxlayır (sıra № üzrə yenilənir). keçildi | təkrar (keçildi, mənimsəmə zəif) | qismən (sayılmır)."""
    __tablename__ = 'topic_progress'
    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey('teaching_assignments.id', ondelete='CASCADE'))
    plan_lesson_id: Mapped[int] = mapped_column(ForeignKey('plan_lessons.id', ondelete='CASCADE'))
    status: Mapped[str] = mapped_column(String(10))
    done_on: Mapped[dt.date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(String(300))
    updated_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    __table_args__ = (UniqueConstraint('assignment_id', 'plan_lesson_id', name='uq_topic_progress'),)


class LessonBankLink(Base):
    """Plan dərsinin P0010 test faylı – müəllimin seçimi (avtomatik uyğunluğun üstündədir).
    file_id = None – müəllim bağlantını götürüb (bu dərsə P0010 göstərilmir)."""
    __tablename__ = 'lesson_bank_links'
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_lesson_id: Mapped[int] = mapped_column(ForeignKey('plan_lessons.id', ondelete='CASCADE'), unique=True)
    file_id: Mapped[int | None] = mapped_column(ForeignKey('bank_files.id', ondelete='SET NULL'))
    set_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class DailyPlan(Base):
    """Gündəlik dərs planı (ARTİ): perspektiv planın bir dərs yuvası üçün süni intellektlə hazırlanır, müəllim redaktə edir."""
    __tablename__ = 'daily_plans'
    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey('teaching_assignments.id', ondelete='CASCADE'))
    date: Mapped[dt.date] = mapped_column(Date)
    period: Mapped[int] = mapped_column(Integer)
    plan_lesson_id: Mapped[int | None] = mapped_column(ForeignKey('plan_lessons.id', ondelete='SET NULL'))
    topic: Mapped[str] = mapped_column(Text)
    content: Mapped[dict] = mapped_column(JSON)
    notes: Mapped[str | None] = mapped_column(Text)                     # müəllimin əlavə istəyi
    provider: Mapped[str | None] = mapped_column(String(30))
    model: Mapped[str | None] = mapped_column(String(120))
    edited: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    __table_args__ = (UniqueConstraint('assignment_id', 'date', 'period', name='uq_daily_plan_slot'),)


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
    # onlayn mövzu testinin nəticəsi üçün avtomatik yaranıb, müəllim hələ saxlamayıb – «yazılmış dərs» sayılmır
    auto: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
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
    task_id: Mapped[int | None] = mapped_column(ForeignKey('online_tasks.id', ondelete='SET NULL'))   # onlayn testdən gəlib
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
    title: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (UniqueConstraint('assignment_id', 'kind', 'semester', 'no'),)


class ExamScore(Base):
    __tablename__ = 'exam_scores'
    exam_id: Mapped[int] = mapped_column(ForeignKey('exams.id', ondelete='CASCADE'), primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='CASCADE'), primary_key=True)
    points: Mapped[float | None] = mapped_column(Float)
    item_marks: Mapped[list | None] = mapped_column(JSON)              # [1, 0, 1, …] – tapşırıq üzrə ✓/✗
    absent: Mapped[bool] = mapped_column(Boolean, default=False)
    taken_on: Mapped[dt.date | None] = mapped_column(Date)             # üzrlü səbəbdən sonradan yazdığı tarix


# ---------------------------------------------------------------- onlayn tapşırıqlar (vaxtlı testlər)
class TestBatch(Base):
    """Bir neçə sinfə eyni anda göndərilən test (mövzu testi / sınaq) – siniflərin müqayisəsi və ümumi reytinq üçün."""
    __tablename__ = 'test_batches'
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(10))                       # movzu | sinaq
    title: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str | None] = mapped_column(String(60))
    grade: Mapped[int | None] = mapped_column(Integer)
    penalty: Mapped[int] = mapped_column(Integer, default=0)            # sınaq: N səhv 1 düzü aparır (0 – cərimə yox)
    created_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)


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
    kind: Mapped[str | None] = mapped_column(String(10))                # movzu (plan mövzusu üzrə) | sinaq | None – adi tapşırıq
    batch_id: Mapped[int | None] = mapped_column(ForeignKey('test_batches.id', ondelete='SET NULL'))
    plan_lesson_id: Mapped[int | None] = mapped_column(ForeignKey('plan_lessons.id', ondelete='SET NULL'))
    journal_auto: Mapped[bool] = mapped_column(Boolean, default=False)  # bağlananda formativ jurnala özü yazılsın
    journal_done_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


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
    manual: Mapped[dict | None] = mapped_column(JSON)                   # müəllimin açıq sual düzəlişi {"sual indeksi": true/false}
    solution_key: Mapped[str | None] = mapped_column(String(200))       # həllin şəkilləri – bir PDF (storage açarı)
    solution_size: Mapped[int | None] = mapped_column(Integer)
    solution_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
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
    cleared_id: Mapped[int] = mapped_column(Integer, default=0, server_default=false())   # «söhbəti sil» – bu id-yə qədər görünmür (yalnız özündə)


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
    edited_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))   # müəllif mətni düzəldib


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


# ---------------------------------------------------------------- şagird kartı: valideynlə əlaqə, fərdi iş planı
class ParentContact(Base):
    __tablename__ = 'parent_contacts'
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='CASCADE'))
    teacher_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    date: Mapped[dt.date] = mapped_column(Date)
    method: Mapped[str] = mapped_column(String(20))                    # zəng | görüş | mesaj | iclas
    topic: Mapped[str] = mapped_column(String(300))
    outcome: Mapped[str | None] = mapped_column(Text)
    follow_up: Mapped[dt.date | None] = mapped_column(Date)


class IndividualPlan(Base):
    __tablename__ = 'individual_plans'
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='CASCADE'))
    teacher_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    goal: Mapped[str] = mapped_column(Text)
    steps: Mapped[list] = mapped_column(JSON, default=list)             # [{"text":..., "done": false}]
    start: Mapped[dt.date] = mapped_column(Date)
    review_date: Mapped[dt.date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(12), default='aktiv')    # aktiv | tamamlandı | dayandırıldı
    note: Mapped[str | None] = mapped_column(Text)



# ---------------------------------------------------------------- materiallar: PDF/fayl tapşırıq, video dərs, link
class Material(Base, Archivable):
    __tablename__ = 'materials'
    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey('teaching_assignments.id', ondelete='CASCADE'))
    kind: Mapped[str] = mapped_column(String(10))                      # task | video | link | note
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(1000))               # video/link (YouTube və s.)
    file_key: Mapped[str | None] = mapped_column(String(120))
    file_name: Mapped[str | None] = mapped_column(String(200))
    file_type: Mapped[str | None] = mapped_column(String(80))
    file_size: Mapped[int | None] = mapped_column(Integer)
    due_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))   # tapşırığın son vaxtı
    needs_submission: Mapped[bool] = mapped_column(Boolean, default=False)
    student_ids: Mapped[list | None] = mapped_column(JSON)              # None = bütün sinif/qrup
    created_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)


class MaterialSubmission(Base):
    __tablename__ = 'material_submissions'
    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey('materials.id', ondelete='CASCADE'))
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='CASCADE'))
    text: Mapped[str | None] = mapped_column(Text)
    file_key: Mapped[str | None] = mapped_column(String(120))
    file_name: Mapped[str | None] = mapped_column(String(200))
    file_type: Mapped[str | None] = mapped_column(String(80))
    file_size: Mapped[int | None] = mapped_column(Integer)
    submitted_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)
    late: Mapped[bool] = mapped_column(Boolean, default=False)
    grade: Mapped[int | None] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (UniqueConstraint('material_id', 'student_id'),)


from .storage import FileBlob  # noqa: E402,F401 – çat fayllarının bazada saxlanması (Alembic üçün qeydiyyat)


class InviteLink(Base):
    """Şagirdin özünü qeydiyyatdan keçirməsi üçün sinif linki (müəllim yaradır; müddət və say limiti)."""
    __tablename__ = 'invite_links'
    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(64), unique=True)
    class_id: Mapped[int] = mapped_column(ForeignKey('classes.id', ondelete='CASCADE'))
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    max_uses: Mapped[int] = mapped_column(Integer, default=40)
    uses: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class LevelOverride(Base):
    """Müəllimin əl ilə təyin etdiyi səviyyə (güclü/orta/zəif) – öz fənni üzrə; avtomatik səviyyəni əvəz edir."""
    __tablename__ = 'level_overrides'
    assignment_id: Mapped[int] = mapped_column(ForeignKey('teaching_assignments.id', ondelete='CASCADE'), primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='CASCADE'), primary_key=True)
    level: Mapped[str] = mapped_column(String(10))                     # Güclü | Orta | Zəif
    note: Mapped[str | None] = mapped_column(String(300))
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    source: Mapped[str] = mapped_column(String(10), default='manual')  # manual – müəllim | auto – bölgü (app/levels.py)
    locked: Mapped[bool] = mapped_column(Boolean, default=True)        # kilidli – avtomatik bölgü və təkliflər toxunmur
    score: Mapped[float | None] = mapped_column(Float)                 # bölgü balı (0–100)
    components: Mapped[dict | None] = mapped_column(JSON)              # {"buraxilis": 72, "sinaq": 64, ...}


class LevelHistory(Base):
    """Səviyyə dəyişikliklərinin tarixçəsi (kim, nə vaxt, haradan → hara)."""
    __tablename__ = 'level_history'
    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey('teaching_assignments.id', ondelete='CASCADE'))
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='CASCADE'))
    old: Mapped[str | None] = mapped_column(String(10))
    new: Mapped[str | None] = mapped_column(String(10))
    source: Mapped[str] = mapped_column(String(10))                    # manual | auto
    score: Mapped[float | None] = mapped_column(Float)
    by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)


class ClassEvent(Base):
    """Sinif rəhbərinin jurnalı: valideyn iclası, sinif saatı, tədbir, ekskursiya (kim iştirak etmədi)."""
    __tablename__ = 'class_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey('classes.id', ondelete='CASCADE'))
    teacher_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    date: Mapped[dt.date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(20))                      # valideyn iclası | sinif saatı | tədbir | ekskursiya | digər
    title: Mapped[str] = mapped_column(String(300))
    note: Mapped[str | None] = mapped_column(Text)
    absent_ids: Mapped[list | None] = mapped_column(JSON)              # iştirak etməyən şagirdlər
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)


class ClassLesson(Base):
    """Sinfin həftəlik dərs cədvəli (bütün fənlər, 1–8-ci saat) – sinif rəhbəri doldurur; sistemdəki müəllimlərin
    dərsləri onların bağlılığından avtomatik gəlir (burada saxlanmır)."""
    __tablename__ = 'class_lessons'
    class_id: Mapped[int] = mapped_column(ForeignKey('classes.id', ondelete='CASCADE'), primary_key=True)
    weekday: Mapped[int] = mapped_column(Integer, primary_key=True)          # 0 = B.e. … 4 = C.
    period: Mapped[int] = mapped_column(Integer, primary_key=True)           # 1–8
    subject: Mapped[str] = mapped_column(String(80))
    teacher: Mapped[str | None] = mapped_column(String(120))


class HomeroomAttendance(Base):
    """Sinif rəhbərinin davamiyyət qeydi (dərs saatı üzrə). Fənn müəlliminin jurnalı olan dərsdə jurnal əsasdır."""
    __tablename__ = 'homeroom_attendance'
    class_id: Mapped[int] = mapped_column(ForeignKey('classes.id', ondelete='CASCADE'), primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    period: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='CASCADE'), primary_key=True)
    status: Mapped[str] = mapped_column(String(10))                    # var | yox | üzrlü | gecikdi
    reason: Mapped[str | None] = mapped_column(String(120))            # üzrlü səbəb: arayış, ailə, tədbir …
    marked_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


# ---------------------------------------------------------------- əlavə məşğələ (əyani və onlayn)
class ExtraCourse(Base, Archivable):
    """Əlavə məşğələ kursu – dərs cədvəlindən və gündəlik plandan ayrı, öz perspektiv planı (məşğələlər) ilə.
    Jurnala qiymət yazmır, işçi planı sürüşdürmür; şagird və valideyn planı və öz iştirakını görür."""
    __tablename__ = 'extra_courses'
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    school_id: Mapped[int] = mapped_column(ForeignKey('schools.id'))
    title: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(60))
    format: Mapped[str] = mapped_column(String(10))                    # əyani | onlayn | qarışıq
    audience: Mapped[dict] = mapped_column(JSON)                       # {"ta_ids": [...], "levels": [...] | null, "student_ids": [...] | null}
    schedule: Mapped[list] = mapped_column(JSON)                       # [{"weekday": 5, "start": "10:00", "end": "11:00", "room": "...", "link": "..."}]
    starts_on: Mapped[dt.date] = mapped_column(Date)
    ends_on: Mapped[dt.date] = mapped_column(Date)
    goal: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)


class ExtraSession(Base):
    __tablename__ = 'extra_sessions'
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey('extra_courses.id', ondelete='CASCADE'))
    date: Mapped[dt.date] = mapped_column(Date)
    start: Mapped[str] = mapped_column(String(5))                      # 10:00 (Bakı vaxtı)
    end: Mapped[str] = mapped_column(String(5))
    format: Mapped[str] = mapped_column(String(10))                    # əyani | onlayn
    room: Mapped[str | None] = mapped_column(String(60))
    link: Mapped[str | None] = mapped_column(String(500))              # yalnız https://
    topics: Mapped[list | None] = mapped_column(JSON)                  # [{"plan_lesson_id": 12 | null, "text": "..."}]
    goals: Mapped[str | None] = mapped_column(Text)
    resources: Mapped[str | None] = mapped_column(Text)                # material / keçidlər
    material_ids: Mapped[list | None] = mapped_column(JSON)            # «Materiallar» bölməsindən (şagird yalnız ona açıq olanları görür)
    homework: Mapped[str | None] = mapped_column(Text)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey('test_batches.id', ondelete='SET NULL'))   # məşğələ testi
    status: Mapped[str] = mapped_column(String(10), default='planned')   # planned | held | cancelled
    note: Mapped[str | None] = mapped_column(String(300))              # ləğv / köçürmə səbəbi
    recording_url: Mapped[str | None] = mapped_column(String(500))


class ExtraAttendance(Base):
    __tablename__ = 'extra_attendance'
    session_id: Mapped[int] = mapped_column(ForeignKey('extra_sessions.id', ondelete='CASCADE'), primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='CASCADE'), primary_key=True)
    status: Mapped[str | None] = mapped_column(String(10))             # var | yox | üzrlü | gecikdi (müəllim təsdiqi)
    joined_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))   # şagird «Qoşul» basıb (onlayn)


class AiReview(Base):
    """Süni intellekt köməkçisinin pedaqoji rəyi (Test nəticələri): müəllim, əhatə (şagird/sinif/qrup/ümumi), son rəy."""
    __tablename__ = 'ai_reviews'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    school_id: Mapped[int | None] = mapped_column(ForeignKey('schools.id', ondelete='CASCADE'))
    scope: Mapped[str] = mapped_column(String(10))                     # student | class | group | overall
    key: Mapped[str] = mapped_column(String(80))                       # «student:12», «class:5:Zəif», «overall»
    payload: Mapped[dict] = mapped_column(JSON)                        # {xulase, guclu, zeif, sebebler, tovsiyeler, valideyne, diqqet}
    model: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------- şagird sorğusu (müəllim haqqında, anonim)
class Survey(Base, Archivable):
    """Müəllimin öz işi haqqında anonim şagird sorğusu (docs/muellim-sorgusu-promtu.md). Məkana (school_id) bağlıdır.
    repeat=weekly – şagird hər tədris həftəsində bir dəfə cavab verə bilər (nəticələr həftələr üzrə);
    in_app – sorğu şagirdin tətbiqində (portal) də görünür (müəllimin dərs dediyi siniflərin şagirdlərinə)."""
    __tablename__ = 'surveys'
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    school_id: Mapped[int | None] = mapped_column(ForeignKey('schools.id', ondelete='CASCADE'))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    template_key: Mapped[str | None] = mapped_column(String(40))
    sections: Mapped[list] = mapped_column(JSON)                       # [{key, title}]
    status: Mapped[str] = mapped_column(String(10), default='draft')   # draft | open | closed
    opens_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    closes_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    min_group: Mapped[int] = mapped_column(Integer, default=5)         # k-anonimlik həddi
    repeat: Mapped[str] = mapped_column(String(10), default='once')    # once | weekly
    in_app: Mapped[bool] = mapped_column(Boolean, default=True)
    # qısa həftəlik sorğu: hər həftə hər meyardan 1 sual (növbə ilə) + ümumi bal – şagird üçün 1–2 dəqiqə
    pulse: Mapped[bool] = mapped_column(Boolean, default=True)
    root_id: Mapped[int | None] = mapped_column(Integer)               # təkrar sorğu (dalğa) – ilk sorğunun id-si
    wave: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)


class SurveyQuestion(Base):
    __tablename__ = 'survey_questions'
    id: Mapped[int] = mapped_column(primary_key=True)
    survey_id: Mapped[int] = mapped_column(ForeignKey('surveys.id', ondelete='CASCADE'), index=True)
    key: Mapped[str | None] = mapped_column(String(20))                # şablon açarı (A1, overall, nps) – dalğaları tutuşdurmaq üçün
    section: Mapped[str] = mapped_column(String(4))
    order: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(10))                      # likert5 | scale10 | single | multi | text
    text: Mapped[str] = mapped_column(String(500))
    options: Mapped[dict | None] = mapped_column(JSON)                 # scale10: {min, max}; single/multi: {choices: []}
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    reverse: Mapped[bool] = mapped_column(Boolean, default=False)


class SurveyLink(Base):
    """Açıq link (/s/{token}): ümumi və ya sinif/qrup üçün ayrıca (WhatsApp-da göndərilir, QR çap olunur)."""
    __tablename__ = 'survey_links'
    id: Mapped[int] = mapped_column(primary_key=True)
    survey_id: Mapped[int] = mapped_column(ForeignKey('surveys.id', ondelete='CASCADE'), index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True)
    class_id: Mapped[int | None] = mapped_column(ForeignKey('classes.id', ondelete='SET NULL'))
    label: Mapped[str] = mapped_column(String(120))
    # auto – sorğunun qaydası; full – tam anket; short – qısa (~8 sual), hər dəfə dəyişir (həftəlikdə hər həftə, birdəfəlikdə hər şagirdə başqa dəst)
    mode: Mapped[str] = mapped_column(String(10), default='auto')
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)


class SurveyResponse(Base):
    """Anonim cavab: şagird, IP, cihaz – heç biri saxlanmır; tarix yalnız gün dəqiqliyi ilə."""
    __tablename__ = 'survey_responses'
    id: Mapped[int] = mapped_column(primary_key=True)
    survey_id: Mapped[int] = mapped_column(ForeignKey('surveys.id', ondelete='CASCADE'), index=True)
    link_id: Mapped[int | None] = mapped_column(ForeignKey('survey_links.id', ondelete='SET NULL'))
    # sinif/qrup: sinif linki və tətbiqdə avtomatik, ümumi linkdə şagird özü seçir – sinif üzrə strategiya üçün (≥ min_group)
    class_id: Mapped[int | None] = mapped_column(ForeignKey('classes.id', ondelete='SET NULL'), index=True)
    period: Mapped[str] = mapped_column(String(10))                    # «2026-W40» (həftəlik) və ya «once»
    submitted_on: Mapped[dt.date] = mapped_column(Date)
    answers: Mapped[dict] = mapped_column(JSON)                        # {"<question_id>": dəyər}
    hidden: Mapped[list | None] = mapped_column(JSON)                  # hesabatdan gizlədilən açıq cavablar: [question_id]


class SurveyDedup(Base):
    """Təkrar göndərməyə qarşı: yalnız heş (cavabla əlaqəsi yoxdur)."""
    __tablename__ = 'survey_dedup'
    survey_id: Mapped[int] = mapped_column(ForeignKey('surveys.id', ondelete='CASCADE'), primary_key=True)
    hash: Mapped[str] = mapped_column(String(64), primary_key=True)
