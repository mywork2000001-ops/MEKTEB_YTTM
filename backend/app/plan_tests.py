"""Perspektiv plandan mövzu testlərinin təyini – TƏK MÜHƏRRİK (docs/plan-testleri-skripti-promtu.md).

Mövzu testinin seçimi/təyini ilə bağlı hər yeni imkan (yeni bank mənbəyi, sinif/nömrə qaydası, variant, səviyyə, öz rəqəmləri,
paralel siniflər) YALNIZ burada: `RESOLVERS` (sual mənbəyi seçiciləri), `POST_STEPS` (yaranmış tapşırığa son addımlar), `Opts`.
Skript (scripts/plan_tests.py), API (/api/plan-tests/*), plan səhifəsi, gündəlik `auto_tests` hamısı bu moduldan istifadə edir.

    plan_items(db, ta, d1, d2)  → mövzu qrupları: dərslər + test yuvası (mövzunun SONUNCU dərsi) + mövzu nömrəsi
    resolve(db, ta, teacher, item, opts, gm) → Choice (status: ok | weak | none | manual | toplu...)
    build_task(db, ta, teacher, item, choice, opts) → OnlineTask (+ TestBatch) – jurnala, qarışıq, cavablar bağlanandan sonra
    assign(db, user, tas, d1, d2, opts, apply=False) → Report (defolt quru rejim – heç nə yazmır)

Statuslar: ok | weak (şübhəli) | none (tapılmadı) | manual (müəllimin seçimi) | has_test | summative | derived | past | missing."""
from __future__ import annotations

import datetime as dt
import random
from dataclasses import dataclass, field
from typing import Callable
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from .bank.match import (_NOT_TOPIC, GradeMatcher, base_topic, derived, lesson_query, topic_numbers, _norm)
from .models import (BankFile, BankQuestion, LessonBankLink, OnlineTask, PlanLesson, PlanProgram, School, SchoolClass,
                     TeachingAssignment, TestBatch, User, now)
from .services import SCHOOL_TZ, class_grade, plan_ctx, today

TZ = ZoneInfo(SCHOOL_TZ)
SUMMATIVE = ('KSQ', 'BSQ', 'diaqnostik')

# server mətnləri (AZ) – frontend bunları t() ilə tərcümə edir (frontend/src/i18n.ts); dəyişəndə orada da yenilə
R_SUMMATIVE = 'KSQ/BSQ/diaqnostik dərsinə mövzu testi verilmir'
R_NOTTOPIC = 'Sınaq və ya təkrar dərsi – mövzu testi yoxdur'
R_DERIVED = 'Törəmə dərs – mövzunun testi əsas dərsə bağlanır'
R_HAS = 'Bu mövzuda test artıq var'
R_PAST = 'Dərs keçib (çatışmayanlar rejimi söndürülüb)'
R_MANUAL = 'Müəllimin seçdiyi fayl'
R_MANUAL_NONE = 'Müəllim «Test yoxdur» seçib'
R_WEAK = 'Şübhəli uyğunluq – yoxlayın'
R_NOFILE = 'Uyğun test faylı tapılmadı'
R_NOQ = 'Faylda sual yoxdur'
R_OFF = 'Bu sinif üçün test bazası mənbəyi söndürülüb'
R_MIXED = 'Qarışıq təkrar – tək fayl yoxdur'
R_TOPLU = 'DİM 9 test toplusu (P007)'
R_TOPLU_NO = 'Test toplusu faylı bankda yoxdur'
R_NOSLOT = 'Dərs cədvəldə yerləşmir'
R_AUTO = 'Avtomatik uyğunluq'
R_PENDING = 'Gözlənilir – bu sinif üçün test sualları hələ hazırlanır'
R_MISSING = 'Keçmiş dərs – çatışan test'


@dataclass
class Opts:
    """Təyin seçimləri. Yeni seçim = bura bir sahə + RESOLVERS/POST_STEPS-də istifadə."""
    n_questions: int = 15
    duration: int = 45                    # dəq.; MIN_TEST_MIN-dən az ola bilməz
    missing: bool = False                 # keçilmiş testsiz dərslərə də (açılma – indi)
    missing_close_days: int = 3           # çatışan test: açılmadan N gün sonra 22:00
    close_days: int = 1                   # adi test: dərsdən N gün sonra 22:00 (defolt ertəsi gün)
    include_weak: bool = False            # şübhəli uyğunluqda da yarat

    def norm(self) -> 'Opts':
        from .api.tasks import MIN_TEST_MIN
        self.n_questions = max(1, min(int(self.n_questions or 15), 100))
        self.duration = max(int(self.duration or MIN_TEST_MIN), MIN_TEST_MIN)
        self.missing_close_days = max(1, int(self.missing_close_days or 3))
        self.close_days = max(1, int(self.close_days or 1))
        return self


@dataclass
class Item:
    """Bir mövzu: ardıcıl dərslər (qrup), test yuvası = sonuncu dərsin sonuncu yuvası."""
    ta: TeachingAssignment
    cls: SchoolClass
    lessons: list[PlanLesson]
    kind: str                              # topic | summative | nottopic | derived | toplu
    date: dt.date | None = None
    period: int | None = None
    no: str | None = None

    @property
    def pl(self) -> PlanLesson:
        return self.lessons[-1]


@dataclass
class Choice:
    status: str                            # ok | weak | none | manual
    reason: str = ''
    source: str | None = None
    file: BankFile | None = None
    count: int = 0
    title: str | None = None
    questions: list[dict] | None = None    # hazırdırsa (toplu); fayldan – build zamanı seçilir
    cover: float | None = None

    @property
    def creatable(self) -> bool:
        return self.status in ('ok', 'manual') and self.count > 0


# ---------------------------------------------------------------- plan_items
class TaCtx:
    """Bir TA üçün bir dəfə hesablanan kontekst (plan, proqram, mövzu nömrələri, GradeMatcher)."""

    def __init__(self, db: Session, ta: TeachingAssignment, gm: GradeMatcher | None = None):
        self.db, self.ta = db, ta
        self.ctx = plan_ctx(db, ta)
        self.prog = db.get(PlanProgram, ta.program_id) if ta.program_id else None
        self.numbers = topic_numbers(self.ctx.lessons, self.prog)
        explicit = ta.bank_source if ta.bank_source and ta.bank_source != 'none' else None
        self.gm = gm or GradeMatcher(db, explicit)
        self.teacher = db.get(User, ta.teacher_id)

    def no_of(self, pl: PlanLesson) -> str | None:
        for l, n in zip(self.ctx.lessons, self.numbers):
            if l.id == pl.id:
                return n
        return None

    def grade_of(self, pl: PlanLesson) -> int | None:
        from .programs import lesson_grade
        return lesson_grade(pl, self.prog, class_grade(self.db, self.ctx.cls))


def _toplu(pl: PlanLesson) -> bool:
    from .api.programs import _toplu_src, toplu_lesson
    try:
        return toplu_lesson(pl, _toplu_src()) is not None
    except (OSError, ValueError, KeyError):
        return False


def _kind(l: PlanLesson) -> str:
    t = (l.topic or '').strip()
    if l.assessment_type in SUMMATIVE:
        return 'summative'
    if derived(t):
        return 'derived'
    if t.startswith(_NOT_TOPIC):
        return 'nottopic'
    if _toplu(l):
        return 'toplu'
    return 'topic'


def plan_items(db: Session, ta: TeachingAssignment, date_from: dt.date | None, date_to: dt.date | None,
               _c: TaCtx | None = None) -> list[Item]:
    """İşçi plana görə mövzu qrupları. Mövzu = ardıcıl eyni əsas adlı dərslər («… Nəzəri xülasə», «… (2/3)», «… Sinif testi və təhlil»);
    test yuvası – qrupun SONUNCU dərsinin sonuncu yuvası. date_from/date_to – test yuvasının tarixi (None – məhdudiyyət yoxdur)."""
    c = _c or TaCtx(db, ta)
    ctx = c.ctx
    last_slot: dict[int, object] = {}
    for s in ctx.slots:
        pl = ctx.lesson_for(s)
        if pl is not None:
            last_slot[pl.id] = s
    items: list[Item] = []
    key_prev = None
    for l in ctx.lessons:
        k = _kind(l)
        if k == 'topic':
            q = lesson_query(l.topic, l.section)
            key = ('t', _norm(base_topic(q[0] if q else l.topic)).strip()) if q else None
            if key is None:
                k, key = 'nottopic', ('n', l.id)
        else:
            key = (k, l.id)
        if items and key == key_prev and k == 'topic':
            items[-1].lessons.append(l)
        else:
            items.append(Item(ta, ctx.cls, [l], k))
        key_prev = key
    out = []
    for it in items:
        s = last_slot.get(it.pl.id)
        if s is not None:
            it.date, it.period = s.date, s.period
        it.no = c.no_of(it.pl)
        if it.date is None:
            out.append(it)                         # yuvası yoxdur (ilə sığmır) – hesabatda «cədvəldə yerləşmir»
        elif (date_from is None or it.date >= date_from) and (date_to is None or it.date <= date_to):
            out.append(it)
    return out


# ---------------------------------------------------------------- resolve (RESOLVERS reyestri)
def _src_label(key: str | None) -> str:
    return 'DİM 9' if key == 'p007' else 'P0010' if key == 'p003' else (key or '').upper()


def _file_choice(db: Session, f: BankFile, status: str, reason: str, opts: Opts, item: Item, cover=None) -> Choice:
    base = base_topic(item.pl.topic) or item.pl.topic
    return Choice(status, reason, f.source_key, f, min(opts.n_questions, f.question_count or 0), cover=cover,
                  title=f'№{item.pl.seq} {base} – {_src_label(f.source_key)} testi'[:200])


def r_manual(c: TaCtx, item: Item, opts: Opts) -> Choice | None:
    """Müəllimin plan sətrində seçdiyi fayl (LessonBankLink; file_id None – «Test yoxdur»); qrupun hər dərsində axtarılır."""
    for l in reversed(item.lessons):
        k = c.db.scalar(select(LessonBankLink).where(LessonBankLink.plan_lesson_id == l.id))
        if k is None:
            continue
        if k.file_id is None:
            return Choice('none', R_MANUAL_NONE)
        f = c.db.get(BankFile, k.file_id)
        if f is None or not f.active:
            return Choice('none', R_NOFILE)
        return _file_choice(c.db, f, 'manual', R_MANUAL, opts, item) if f.question_count else Choice('none', R_NOQ, f.source_key, f)
    return None


def r_toplu(c: TaCtx, item: Item, opts: Opts) -> Choice | None:
    """IX «Test toplusu» dərsi – P007 bankından dərsin S/E/M aralığı (köhnə davranış)."""
    if item.kind != 'toplu':
        return None
    from fastapi import HTTPException
    from .api.programs import toplu_questions
    try:
        r = toplu_questions(lesson_id=item.pl.id, scope='lesson', n=opts.n_questions, user=c.teacher, db=c.db)
    except HTTPException:
        return Choice('none', R_TOPLU_NO, 'p007')
    qs = [{k: v for k, v in q.items() if k != 'qid'} for q in r.get('questions') or []]
    if not qs:
        return Choice('none', R_TOPLU_NO if not r.get('in_bank', True) else R_NOQ, 'p007')
    return Choice('ok', R_TOPLU, 'p007', None, len(qs), r.get('title') or f'№{item.pl.seq} {item.pl.topic} – mövzu testi',
                  questions=qs)


def r_grade_matcher(c: TaCtx, item: Item, opts: Opts) -> Choice | None:
    """Dərsin öz sinfi → sinfin sıralı mənbələri → mövzu nömrəsi + ad uyğunluğu (bank/match.py GradeMatcher)."""
    if c.ta.bank_source == 'none':
        return Choice('none', R_OFF)
    g = c.grade_of(item.pl)
    if not c.gm.sources(g):
        return Choice('none', R_NOFILE)
    q = lesson_query(item.pl.topic, item.pl.section)
    if q is None:
        return Choice('none', R_MIXED)
    r = c.gm.find_ex(g, q[0], q[1], 1, no=item.no)
    if r.status == 'pending':
        return Choice('pending', R_PENDING, r.source, r.files[0][0] if r.files else None, cover=r.cover)
    if not r.files or r.status == 'none':
        return Choice('none', R_NOFILE, r.source, r.files[0][0] if r.files else None, cover=r.cover)
    f = r.files[0][0]
    if not f.question_count:
        return Choice('none', R_NOQ, f.source_key, f)
    return _file_choice(c.db, f, r.status, R_AUTO if r.status == 'ok' else R_WEAK, opts, item, r.cover)


RESOLVERS: list[Callable[[TaCtx, Item, Opts], Choice | None]] = [r_manual, r_toplu, r_grade_matcher]


def resolve(db: Session, ta: TeachingAssignment, item: Item, opts: Opts | None = None, _c: TaCtx | None = None) -> Choice:
    """Sual mənbəyi: RESOLVERS sırası ilə ilk cavab verən. Yeni mənbə/qayda = yeni funksiya + siyahıya bir sətir."""
    opts = (opts or Opts()).norm()
    c = _c or TaCtx(db, ta)
    for fn in RESOLVERS:
        r = fn(c, item, opts)
        if r is not None:
            return r
    return Choice('none', R_NOFILE)


def locate(db: Session, ta: TeachingAssignment, pl: PlanLesson, limit: int = 6, _c: TaCtx | None = None):
    """Bir plan dərsi üçün (dərsin sinfi, GradeMatcher.Found | None, mövzu nömrəsi) – əl ilə təklif (p0010_for_topic) də bu yolla."""
    c = _c or TaCtx(db, ta)
    g = c.grade_of(pl)
    if ta.bank_source == 'none' or not c.gm.sources(g):
        return g, None, None
    no = c.no_of(pl)
    q = lesson_query(pl.topic, pl.section)
    if q is None:
        return g, None, no
    return g, c.gm.find_ex(g, q[0], q[1], limit, no=no), no


# ---------------------------------------------------------------- build_task (POST_STEPS)
POST_STEPS: list[Callable[[Session, OnlineTask, TeachingAssignment, Item, Opts], None]] = []


def _questions(db: Session, choice: Choice, opts: Opts) -> list[dict]:
    if choice.questions is not None:
        return choice.questions
    from .api.programs import _pick
    from .api.tasks import _snapshot
    qs = list(db.scalars(select(BankQuestion).where(BankQuestion.file_id == choice.file.id, BankQuestion.active.is_(True))
                         .order_by(BankQuestion.n)))
    n = max(1, min(opts.n_questions, 100))
    if len(qs) > n:
        keep = {q.id for q in _pick(qs, n, random.Random())}
        qs = [q for q in qs if q.id in keep]
    return [{k: v for k, v in q.items() if k != 'qid'} for q in _snapshot(db, [q.id for q in qs])] if qs else []


def _times(db: Session, item: Item, opts: Opts, past: bool) -> tuple[dt.datetime, dt.datetime]:
    from .api.topic_tests import _lesson_end
    if past:                                           # çatışan test: indi açılır, N gün sonra 22:00 bağlanır
        o = now()
        c = dt.datetime.combine(today() + dt.timedelta(days=opts.missing_close_days), dt.time(22, 0), tzinfo=TZ)
    else:
        o = _lesson_end(db, item.cls, item.date, item.period, item.ta)
        c = dt.datetime.combine(item.date + dt.timedelta(days=opts.close_days), dt.time(22, 0), tzinfo=TZ)
    o, c = o.astimezone(dt.timezone.utc), c.astimezone(dt.timezone.utc)
    if (c - o).total_seconds() < opts.duration * 60:   # açıq qalma aralığı həll müddətindən qısa ola bilməz
        c = o + dt.timedelta(minutes=opts.duration)
    return o, c


def build_task(db: Session, ta: TeachingAssignment, teacher: User, item: Item, choice: Choice, opts: Opts,
               past: bool = False) -> OnlineTask:
    qs = _questions(db, choice, opts)
    pl = item.pl
    title = (choice.title or f'№{pl.seq} {pl.topic} – mövzu testi')[:200]
    o, c = _times(db, item, opts, past)
    batch = TestBatch(kind='movzu', title=title, subject=ta.subject, grade=class_grade(db, item.cls), created_by=teacher.id)
    db.add(batch)
    db.flush()
    t = OnlineTask(assignment_id=ta.id, title=title, description='Avtomatik mövzu testi (perspektiv plan)', opens_at=o, closes_at=c,
                   duration_min=opts.duration, questions=qs, shuffle=True, show_answers='after_close', student_ids=None,
                   created_by=teacher.id, kind='movzu', batch_id=batch.id, plan_lesson_id=pl.id, journal_auto=True)
    db.add(t)
    db.flush()
    for step in POST_STEPS:
        step(db, t, ta, item, opts)
    return t


# ---------------------------------------------------------------- assign / Report
@dataclass
class Report:
    rows: list[dict] = field(default_factory=list)
    applied: bool = False

    def summary(self) -> list[dict]:
        out: dict[int, dict] = {}
        for r in self.rows:
            s = out.setdefault(r['ta_id'], {'ta_id': r['ta_id'], 'class_name': r['class_name'], 'total': 0, 'will_create': 0,
                                           'created': 0, 'has_test': 0, 'weak': 0, 'none': 0, 'summative': 0, 'past': 0,
                                           'missing': 0, 'manual': 0, 'ok': 0, 'derived': 0, 'pending': 0})
            s['total'] += 1
            s[r['status']] = s.get(r['status'], 0) + 1
            s['will_create'] += bool(r['will_create'])
            s['created'] += bool(r['created'])
        return list(out.values())

    def to_dict(self) -> dict:
        return {'applied': self.applied, 'rows': self.rows, 'summary': self.summary(),
                'will_create': sum(1 for r in self.rows if r['will_create']), 'created': sum(1 for r in self.rows if r['created'])}


def _has_test(db: Session, item: Item) -> bool:
    from .api.topic_tests import _has_test
    return any(_has_test(db, l.id) for l in item.lessons)


def assign(db: Session, user: User | None, tas: list[TeachingAssignment], date_from: dt.date | None, date_to: dt.date | None,
           opts: Opts | None = None, apply: bool = False, gm: GradeMatcher | None = None) -> Report:
    """Seçilən dərs bağlılıqları üçün dövr üzrə mövzu testləri. apply=False – heç nə yazmır (hesabat). Təkrar çağırış dublikat yaratmır."""
    from .api.common import audit
    opts = (opts or Opts()).norm()
    rep = Report(applied=apply)
    t0 = today()
    for ta in tas:
        c = TaCtx(db, ta, gm)
        lo = date_from
        for it in plan_items(db, ta, lo, date_to, c):
            row = {'ta_id': ta.id, 'class_name': it.cls.name, 'date': it.date.isoformat() if it.date else None,
                   'seq': it.pl.seq, 'plan_lesson_id': it.pl.id, 'topic_no': it.no, 'topic': base_topic(it.pl.topic) or it.pl.topic,
                   'file': None, 'source': None, 'questions': 0, 'status': 'none', 'reason': '', 'will_create': False,
                   'created': False, 'task_id': None}
            rep.rows.append(row)
            if it.date is None:
                row['reason'] = R_NOSLOT
                continue
            if it.kind in ('summative', 'nottopic', 'derived'):
                row['status'] = 'summative' if it.kind != 'derived' else 'derived'
                row['reason'] = {'summative': R_SUMMATIVE, 'nottopic': R_NOTTOPIC, 'derived': R_DERIVED}[it.kind]
                continue
            if _has_test(db, it):
                row['status'], row['reason'] = 'has_test', R_HAS
                continue
            past = it.date < t0
            if past and not opts.missing:
                row['status'], row['reason'] = 'past', R_PAST
                continue
            ch = resolve(db, ta, it, opts, c)
            row.update(file=ch.file.label if ch.file else None, source=ch.source, questions=ch.count, status=ch.status,
                       reason=ch.reason)
            if ch.status == 'weak' and opts.include_weak and ch.file is not None and ch.count > 0:
                ch.status = 'ok'
            if not ch.creatable:
                continue
            if past:
                row['status'], row['reason'] = 'missing', R_MISSING
            row['will_create'] = True
            if apply:
                t = build_task(db, ta, c.teacher, it, ch, opts, past)
                row.update(created=True, task_id=t.id, questions=len(t.questions))
                audit(db, user or c.teacher, 'create', 'task', t.id, kind='movzu', auto=True, plan_seq=it.pl.seq,
                      questions=len(t.questions), by='plan_tests', status=row['status'])
    if apply:
        n = sum(1 for r in rep.rows if r['created'])
        if n:
            audit(db, user, 'create', 'plan_tests', len(tas), tasks=n, classes=len({r['ta_id'] for r in rep.rows if r['created']}),
                  date_from=str(date_from), date_to=str(date_to), missing=opts.missing)
        db.commit()
    return rep


def scope_system(db: Session, ta_ids: list[int] | None = None, class_name: str | None = None, teacher: str | None = None,
                 everything: bool = False) -> list[TeachingAssignment]:
    """Skript üçün (istifadəçi yoxdur): --all yalnız adi məktəblərin dərsləri (fərdi məkanlar düşmür); --ta N konkret dərs;
    --class / --teacher (giriş adı və ya ad) daraltma."""
    q = select(TeachingAssignment).join(SchoolClass, SchoolClass.id == TeachingAssignment.class_id).where(
        TeachingAssignment.archived_at.is_(None), SchoolClass.archived_at.is_(None))
    if ta_ids:
        q = q.where(TeachingAssignment.id.in_(ta_ids))
    else:
        if not (everything or class_name or teacher):
            return []
        q = q.where(SchoolClass.school_id.in_(select(School.id).where(School.kind == 'school')))
        if class_name:
            q = q.where(SchoolClass.name == class_name)
    if teacher:
        q = q.where(TeachingAssignment.teacher_id.in_(select(User.id).where((User.login == teacher) | (User.full_name == teacher))))
    return list(db.scalars(q.order_by(SchoolClass.name, TeachingAssignment.id)))


# ---------------------------------------------------------------- kimin hansı dərslərini görür
def scope_tas(db: Session, user: User, ta_ids: list[int] | None = None, class_name: str | None = None,
              teacher_id: int | None = None, everything: bool = False) -> list[TeachingAssignment]:
    """Müəllim – yalnız öz (aktiv məkanın) dərsləri. Admin – məktəbin müəllimlərinin dərsləri (teacher_id ilə konkret müəllim);
    fərdi məkanlar (School.kind='private') heç vaxt. ta_ids/class_name – daraltma; heç biri və everything=False – boş."""
    from .models import Role
    q = select(TeachingAssignment).join(SchoolClass, SchoolClass.id == TeachingAssignment.class_id).where(
        TeachingAssignment.archived_at.is_(None), SchoolClass.archived_at.is_(None))
    if user.role == Role.admin:
        sch = db.get(School, user.school_id) if user.school_id else None
        if sch is None or sch.kind != 'school':
            q = q.where(TeachingAssignment.teacher_id == user.id, SchoolClass.school_id == user.school_id)
        else:
            q = q.where(SchoolClass.school_id == sch.id)
            if teacher_id:
                q = q.where(TeachingAssignment.teacher_id == teacher_id)
    else:
        q = q.where(TeachingAssignment.teacher_id == user.id, SchoolClass.school_id == user.school_id)
    if ta_ids:
        q = q.where(TeachingAssignment.id.in_(ta_ids))
    elif class_name:
        q = q.where(SchoolClass.name == class_name)
    elif not everything:
        return []
    return list(db.scalars(q.order_by(SchoolClass.name, TeachingAssignment.id)))
