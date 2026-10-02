"""Mövzu testi → formativ jurnal.

Qaydalar (docs/plan-test-uygunlugu-promtu.md §3.6–3.7):
- dərs = jurnalda bu mövzunun yazıldığı SONUNCU dərs; jurnal yoxdursa – işçi planda mövzunun düşdüyü sonuncu dərs;
- dərs hələ keçməyibsə – gözləyir (planlaşdırıcı sonra yenidən yoxlayır);
- KSQ/BSQ dərsinə formativ qiymət yazılmır;
- testi yazmayan şagirdə qiymət yazılmır; dərsdə qayıb olması onlayn testə mane deyil;
- müəllimin həmin dərsə əl ilə yazdığı «test» qiyməti üstələnmir;
- təkrar çağırış eyni qiymətləri yeniləyir, cəhdi sıfırlanmış şagirdin qiyməti silinir."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from .domain.rules import summative_grade
from .models import JournalEntry, Mark, OnlineTask, PlanLesson, TaskAttempt, TeachingAssignment, now
from .services import plan_ctx, roster, today


def topic_lesson(db: Session, ta: TeachingAssignment, pl_id: int) -> tuple[dt.date, int, JournalEntry | None] | None:
    """Mövzunun (sonuncu) dərsi: (tarix, saat, jurnal yazısı)."""
    e = db.scalar(select(JournalEntry).where(JournalEntry.assignment_id == ta.id, JournalEntry.plan_lesson_id == pl_id)
                  .order_by(JournalEntry.date.desc(), JournalEntry.period.desc()))
    if e:
        return e.date, e.period, e
    ctx = plan_ctx(db, ta)
    slots = [s for s in ctx.slots if (pl := ctx.lesson_for(s)) is not None and pl.id == pl_id]
    if not slots:
        return None
    s = slots[-1]
    e = db.scalar(select(JournalEntry).where(JournalEntry.assignment_id == ta.id, JournalEntry.date == s.date,
                                             JournalEntry.period == s.period))
    if e is not None and e.plan_lesson_id and e.plan_lesson_id != pl_id:
        return None                    # həmin saatda jurnalda başqa mövzu yazılıb – mövzu hələ keçilməyib
    return s.date, s.period, e


def write_topic_marks(db: Session, task: OnlineTask, by: int | None = None) -> dict:
    """Nəticəni jurnala yazır. Qaytarır: {status, date, period, topic, copied, updated, removed, skipped}.
    status: yazıldı | gözləyir (dərs hələ keçməyib) | mövzu yoxdur | dərs yoxdur | summativ."""
    from .api.common import audit
    from .api.journal import SUMMATIVE
    out = {'status': 'yazıldı', 'date': None, 'period': None, 'topic': None, 'copied': 0, 'updated': 0,
           'removed': 0, 'skipped': []}
    ta = db.get(TeachingAssignment, task.assignment_id)
    pl = db.get(PlanLesson, task.plan_lesson_id) if task.plan_lesson_id else None
    if pl is None or pl.assignment_id != ta.id:
        out['status'] = 'mövzu yoxdur'
        return out
    out['topic'] = pl.topic
    if pl.assessment_type in SUMMATIVE:
        out['status'] = 'summativ'
        return out
    where = topic_lesson(db, ta, pl.id)
    if where is None:
        out['status'] = 'dərs yoxdur'
        return out
    d, period, e = where
    out['date'], out['period'] = d, period
    if d > today():
        out['status'] = 'gözləyir'
        return out
    if e is None:
        e = JournalEntry(assignment_id=ta.id, date=d, period=period, plan_lesson_id=pl.id)
        db.add(e)
        db.flush()
    names = {s.id: s.full_name for s in roster(db, ta)}
    done = {a.student_id: a for a in db.scalars(select(TaskAttempt).where(TaskAttempt.task_id == task.id,
                                                                         TaskAttempt.submitted_at.is_not(None)))
            if a.student_id in names and a.total}
    for sid in [k for k, a in done.items()
                if a.auto_submitted and not any(v not in (None, '') for v in (a.answers or {}).values())]:
        out['skipped'].append({'full_name': names[sid], 'reason': 'başlayıb, heç bir cavab verməyib'})
        del done[sid]                      # boş avtomatik təhvil – «yazmayıb», 2 qoyulmur
    marks = {m.student_id: m for m in db.scalars(select(Mark).where(Mark.entry_id == e.id, Mark.kind == 'test'))}
    for sid, a in done.items():
        m = marks.get(sid)
        if m is not None and m.task_id != task.id:
            out['skipped'].append({'full_name': names[sid], 'reason': 'bu dərsdə əl ilə «test» qiyməti var'})
            continue
        if m is None:
            m = Mark(entry_id=e.id, student_id=sid, kind='test', task_id=task.id)
            db.add(m)
            out['copied'] += 1
        else:
            out['updated'] += 1
        m.test_correct, m.test_total = a.correct, a.total
        m.grade = summative_grade(a.correct * 100 / a.total)
        m.comment = f'Onlayn test: {task.title}'[:300]
    # əvvəl bu testdən yazılıb, indi cəhdi yoxdur (sıfırlanıb) – qiymət silinir
    for m in db.scalars(select(Mark).where(Mark.task_id == task.id)):
        if m.student_id not in done or m.entry_id != e.id:
            db.delete(m)
            out['removed'] += 1
    closes = task.closes_at if task.closes_at.tzinfo else task.closes_at.replace(tzinfo=dt.timezone.utc)
    if closes <= now():                    # test hələ açıqdırsa, bağlananda yenidən yazılacaq (sonra təhvil verənlər)
        task.journal_done_at = now()
    audit(db, None if by is None else _user(db, by), 'update', 'journal', e.id, from_task=task.id,
          copied=out['copied'], updated=out['updated'], removed=out['removed'])
    return out


def _user(db: Session, uid: int):
    from .models import User
    return db.get(User, uid)


def run_due(db: Session) -> int:
    """Planlaşdırıcı: bağlanmış, avtomatik yazılmalı və hələ yazılmamış mövzu testləri. Qaytarır: yazılan test sayı."""
    from .api.tasks import aware, expire_due
    t, n = now(), 0
    for task in db.scalars(select(OnlineTask).where(OnlineTask.kind == 'movzu', OnlineTask.journal_auto.is_(True),
                                                    OnlineTask.journal_done_at.is_(None),
                                                    OnlineTask.archived_at.is_(None))):
        if aware(task.closes_at) > t:
            continue
        expire_due(db, task)
        r = write_topic_marks(db, task)
        if r['status'] == 'yazıldı':
            n += 1
        elif r['status'] != 'gözləyir':
            task.journal_done_at = now()          # yazıla bilməz (mövzu/dərs yoxdur, summativ) – təkrar yoxlanmasın
        db.commit()
    return n
