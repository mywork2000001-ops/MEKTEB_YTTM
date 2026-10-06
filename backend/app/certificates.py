"""Sertifikatlar və şagird motivasiyası (docs/sertifikat-ve-motivasiya-promtu.md).

Sertifikat yalnız serverdəki faktiki nəticədən verilir (şagird ad/bal dəyişə bilməz), hər birinin açıq yoxlanılan kodu var:
- movzu  – mövzu testi ≥ hədd (default 90 %), təhvil veriləndə dərhal;
- sinaq  – sınaq bağlanandan sonra: ≥ hədd (80 %) və ya sinifdə ilk N yer (3);
- seriya – sınaq seriyasında ≥ 4 sınaq göndərilib və şagird ≥ hədd (80 %) qədərində iştirak edib;
- manual – müəllim əl ilə.
Nişanlar, XP, səviyyə, seriya (streak), həftəlik hədəf və bölmə proqresi saxlanılmır – nəticələrdən hesablanır."""
from __future__ import annotations

import datetime as dt
import secrets
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import (Certificate, ExamSeries, OnlineTask, PlanLesson, SchoolClass, Student, TaskAttempt,
                     TeachingAssignment, User, now)
from .services import SCHOOL_TZ

DEFAULT_RULES = {'enabled': True, 'movzu': 90, 'sinaq_pct': 80, 'sinaq_top': 3, 'seriya': 80}
ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'          # 0/O, 1/I qarışmasın
TZ = ZoneInfo(SCHOOL_TZ)


def rules(ta: TeachingAssignment | None) -> dict:
    return {**DEFAULT_RULES, **((ta.cert_rules or {}) if ta else {})}


def new_code(db: Session) -> str:
    while True:
        c = f'MK-{dt.date.today():%y}-' + ''.join(secrets.choice(ALPHABET) for _ in range(8))
        if not db.scalar(select(Certificate.id).where(Certificate.code == c)):
            return c


def _aware(t: dt.datetime | None) -> dt.datetime | None:
    return t.replace(tzinfo=dt.timezone.utc) if t is not None and t.tzinfo is None else t


def _pct(a: TaskAttempt) -> float | None:
    return round(100 * a.correct / a.total, 1) if a.submitted_at and a.total else None


def _context(db: Session, ta: TeachingAssignment, s: Student) -> dict:
    from .api.lessonplans import header_school
    teacher = db.get(User, ta.teacher_id)
    cls = db.get(SchoolClass, ta.class_id)
    return {'subject': ta.subject, 'class_name': cls.name if cls else None, 'teacher': teacher.full_name if teacher else None,
            'school': header_school(teacher) if teacher else None, 'student_code': s.portal_code}


def give(db: Session, s: Student, ta: TeachingAssignment | None, kind: str, source: str, title: str, details: dict,
         by: int | None = None) -> Certificate | None:
    """Sertifikat verir; eyni (şagird, növ, mənbə) artıq varsa – None (təkrar verilmir)."""
    if db.scalar(select(Certificate.id).where(Certificate.student_id == s.id, Certificate.kind == kind,
                                              Certificate.source == source)):
        return None
    c = Certificate(code=new_code(db), student_id=s.id, assignment_id=ta.id if ta else None, kind=kind, source=source,
                    title=title[:300], details={**(_context(db, ta, s) if ta else {'student_code': s.portal_code}), **details},
                    issued_by=by)
    try:
        with db.begin_nested():
            db.add(c)
    except IntegrityError:                                   # paralel işdə eyni sertifikat – təkrar olmasın
        return None
    return c


def for_attempt(db: Session, t: OnlineTask, a: TaskAttempt) -> Certificate | None:
    """Mövzu testi təhvil veriləndə – dərhal (yalnız ilk cəhd: hər şagirdin bir cəhdi var)."""
    if t.kind != 'movzu' or not a.submitted_at:
        return None
    ta = db.get(TeachingAssignment, t.assignment_id)
    r = rules(ta)
    p = _pct(a)
    if not r['enabled'] or p is None or p < r['movzu']:
        return None
    pl = db.get(PlanLesson, t.plan_lesson_id) if t.plan_lesson_id else None
    topic = pl.topic if pl else t.title
    return give(db, db.get(Student, a.student_id), ta, 'movzu', f'task:{t.id}', f'Mövzu ustası: {topic}',
                {'pct': p, 'correct': a.correct, 'total': a.total, 'test': t.title})


def _sinaq_closed(db: Session, t: OnlineTask) -> int:
    ta = db.get(TeachingAssignment, t.assignment_id)
    r = rules(ta)
    if not r['enabled']:
        return 0
    atts = [a for a in db.scalars(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.submitted_at.is_not(None)))
            if a.total]
    n = 0
    for a in atts:
        p = _pct(a)
        place = 1 + sum(1 for b in atts if _pct(b) > p)
        if p >= r['sinaq_pct'] or place <= r['sinaq_top']:
            c = give(db, db.get(Student, a.student_id), ta, 'sinaq', f'task:{t.id}', f'Sınaq imtahanı: {t.title}',
                     {'pct': p, 'correct': a.correct, 'total': a.total, 'place': place, 'of': len(atts), 'test': t.title})
            n += bool(c)
    return n


def _series(db: Session, s: ExamSeries) -> int:
    batches = [x['batch_id'] for x in s.done or []]
    if len(batches) < 4:
        return 0
    n = 0
    for tg in s.targets:
        ta = db.get(TeachingAssignment, tg['ta_id'])
        if not ta or not rules(ta)['enabled']:
            continue
        tasks = list(db.scalars(select(OnlineTask).where(OnlineTask.assignment_id == ta.id, OnlineTask.batch_id.in_(batches))))
        if len(tasks) < 4:
            continue
        done: dict[int, int] = {}
        for a in db.scalars(select(TaskAttempt).where(TaskAttempt.task_id.in_([t.id for t in tasks]),
                                                      TaskAttempt.submitted_at.is_not(None))):
            done[a.student_id] = done.get(a.student_id, 0) + 1
        for sid, k in done.items():
            if 100 * k / len(tasks) >= rules(ta)['seriya']:
                c = give(db, db.get(Student, sid), ta, 'seriya', f'series:{s.id}', f'Sınaq seriyası iştirakçısı: {s.title}',
                         {'taken': k, 'of': len(tasks)})
                n += bool(c)
    return n


def issue_due(db: Session, at: dt.datetime | None = None) -> int:
    """Fon işi: son 3 gündə təhvil verilmiş mövzu testləri, bağlanmış sınaqlar, seriyalar."""
    at = at or now()
    since = at - dt.timedelta(days=3)
    n = 0
    for a, t in db.execute(select(TaskAttempt, OnlineTask).join(OnlineTask, OnlineTask.id == TaskAttempt.task_id).where(
            OnlineTask.kind == 'movzu', TaskAttempt.submitted_at >= since)):
        n += bool(for_attempt(db, t, a))
    for t in db.scalars(select(OnlineTask).where(OnlineTask.kind == 'sinaq', OnlineTask.closes_at <= at,
                                                 OnlineTask.closes_at >= since, OnlineTask.archived_at.is_(None))):
        n += _sinaq_closed(db, t)
    for s in db.scalars(select(ExamSeries)):
        n += _series(db, s)
    db.commit()
    return n


# ---------------------------------------------------------------- motivasiya (hesablanır)
LEVELS = [(0, 'Başlanğıc'), (300, 'Bilici'), (1000, 'Usta'), (2500, 'Ekspert'), (5000, 'Akademik')]
BADGES = [
    ('first', '🎯', 'İlk addım', 'İlk testi təhvil ver'),
    ('perfect', '💯', 'Mükəmməl', 'Bir testdə 100 %'),
    ('five80', '🔥', 'Alov seriyası', '5 test ardıcıl ≥ 80 %'),
    ('sinaq3', '🏁', 'Sınaq döyüşçüsü', '3 sınaq yaz'),
    ('photo', '📷', 'Həll ustası', 'Həllin şəkillərini göndər'),
    ('early', '⚡', 'Tələsməyən sürətli', 'Testi vaxtın yarısından tez və ≥ 80 % ilə bitir'),
    ('growth', '📈', 'İrəliləyiş', 'Son 5 testin ortası ilk 5-dən ≥ 15 % yüksək'),
    ('cert', '🏆', 'Sertifikatlı', 'İlk sertifikatını qazan'),
]


def achievements(db: Session, s: Student) -> dict:
    from .api.portal import _my_tasks
    at = now()
    tasks = {t.id: t for t in _my_tasks(db, s)}
    atts = {a.task_id: a for a in db.scalars(select(TaskAttempt).where(TaskAttempt.student_id == s.id,
                                                                       TaskAttempt.task_id.in_(list(tasks) or [0])))}
    done = sorted((a for a in atts.values() if a.submitted_at and a.total), key=lambda a: _aware(a.submitted_at))
    pcts = [_pct(a) for a in done]
    xp = sum(a.correct * 10 for a in done) + sum(20 for p in pcts if p >= 80) + sum(5 for a in done if not a.auto_submitted)
    lvl = max(i for i, (need, _) in enumerate(LEVELS) if xp >= need)
    nxt = LEVELS[lvl + 1][0] if lvl + 1 < len(LEVELS) else None
    # seriya: bağlanmış (və ya yazılmış) tapşırıqlar ardıcıllığında vaxtında yazılanlar
    closed = sorted((t for t in tasks.values() if _aware(t.closes_at) <= at or (atts.get(t.id) and atts[t.id].submitted_at)),
                    key=lambda t: _aware(t.closes_at))
    run = best = 0
    for t in closed:
        a = atts.get(t.id)
        if a and a.submitted_at:
            run += 1
            best = max(best, run)
        else:
            run = 0
    streak5 = any(all(p >= 80 for p in pcts[i:i + 5]) for i in range(max(0, len(pcts) - 4)))
    early = any(not a.auto_submitted and _pct(a) >= 80 and tasks[a.task_id].duration_min and
                (_aware(a.submitted_at) - _aware(a.started_at)).total_seconds() <= tasks[a.task_id].duration_min * 30 for a in done)
    certs = db.scalars(select(Certificate).where(Certificate.student_id == s.id, Certificate.revoked_at.is_(None))).all()
    earned = {'first': bool(done), 'perfect': any(p >= 100 for p in pcts), 'five80': streak5,
              'sinaq3': sum(1 for a in done if tasks[a.task_id].kind == 'sinaq') >= 3,
              'photo': any(a.solution_key for a in atts.values()), 'early': early,
              'growth': len(pcts) >= 10 and sum(pcts[-5:]) / 5 - sum(pcts[:5]) / 5 >= 15, 'cert': bool(certs)}
    # həftəlik hədəf: bu həftə açılan tapşırıqlar
    today = at.astimezone(TZ).date()
    w0 = dt.datetime.combine(today - dt.timedelta(days=today.weekday()), dt.time(0), tzinfo=TZ)
    week = [t for t in tasks.values() if w0 <= _aware(t.opens_at) < w0 + dt.timedelta(days=7)]
    # bölmələr üzrə proqres (mövzu testləri plan bölməsinə görə)
    sec: dict[str, list[float]] = {}
    for a in done:
        t = tasks[a.task_id]
        pl = db.get(PlanLesson, t.plan_lesson_id) if t.kind == 'movzu' and t.plan_lesson_id else None
        if pl:
            sec.setdefault(pl.section or 'Bölməsiz', []).append(_pct(a))
    return {
        'xp': xp, 'level': lvl + 1, 'level_name': LEVELS[lvl][1], 'level_from': LEVELS[lvl][0], 'level_to': nxt,
        'streak': run, 'best_streak': best, 'tests': len(done), 'avg_pct': round(sum(pcts) / len(pcts), 1) if pcts else None,
        'badges': [{'key': k, 'icon': i, 'title': ti, 'how': h, 'earned': earned[k]} for k, i, ti, h in BADGES],
        'week': {'total': len(week), 'done': sum(1 for t in week if atts.get(t.id) and atts[t.id].submitted_at)},
        'sections': [{'section': k, 'pct': round(sum(v) / len(v), 1), 'tests': len(v)} for k, v in sec.items()],
        'certificates': len(certs), 'new_certificates': sum(1 for c in certs if c.seen_at is None),
    }
