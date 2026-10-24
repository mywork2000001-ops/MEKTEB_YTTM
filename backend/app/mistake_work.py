"""«Səhvlər üzərində iş» (metodik audit M3): formativ mövzu testindən sonra şagirdin yalnız səhv/boş suallarından
şəxsi qısa test. Miqrasiyasız: OnlineTask(kind='sehv'); mənbə cəhd – sualların 'mw_attempt' açarında.
Jurnala, reytinqə, buraxılmış/iştirak hesabatlarına, sertifikata düşmür (hamısı kind='movzu'/'sinaq' ilə süzür) və müəllimin
test siyahısında görünmür. Hər cəhd üçün bir dəfə. Orijinal cəhdin balı/jurnal qiyməti dəyişmir.
Analoq sual əvəzinə eyni sual təkrarlanır (sadə variant; bank analoqu sonra əlavə oluna bilər)."""
from __future__ import annotations

import copy

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import OnlineTask, TaskAttempt, now
from .timing import NO_DEADLINE

KIND = 'sehv'


def wrong_indexes(t: OnlineTask, a: TaskAttempt) -> list[int]:
    from .api.tasks import is_ok
    return [i for i in a.order if not is_ok(t, a, i)]


def existing(db: Session, t: OnlineTask, a: TaskAttempt) -> OnlineTask | None:
    for x in db.scalars(select(OnlineTask).where(OnlineTask.assignment_id == t.assignment_id, OnlineTask.kind == KIND)):
        if x.student_ids == [a.student_id] and x.questions and x.questions[0].get('mw_attempt') == a.id:
            return x
    return None


def eligibility(db: Session, t: OnlineTask, a: TaskAttempt | None, can_review: bool) -> str | None:
    """None – icazə var; yoxsa səbəb kodu: kind | not_done | no_review | none_wrong."""
    from .levels import _diagnostic_tasks
    if t.kind != 'movzu':                                    # KSQ/BSQ/sınaq/adi/səhv-işi – yox
        return 'kind'
    if not a or not a.submitted_at:
        return 'not_done'
    if not can_review:
        return 'no_review'
    if _diagnostic_tasks(db, [t]):
        return 'kind'
    if not wrong_indexes(t, a):
        return 'none_wrong'
    return None


def create(db: Session, t: OnlineTask, a: TaskAttempt, at=None) -> OnlineTask:
    """Çağıran icazəni (eligibility) və təkrarı (existing) əvvəl yoxlayır."""
    qs = []
    for i in wrong_indexes(t, a):
        q = copy.deepcopy(t.questions[i])
        q['mw_attempt'] = a.id
        qs.append(q)
    task = OnlineTask(assignment_id=t.assignment_id, title=f'Səhvlər üzərində iş: {t.title}'[:200], description=None,
                      opens_at=at or now(), closes_at=NO_DEADLINE, duration_min=0, questions=qs, shuffle=False,
                      show_answers='after_submit', student_ids=[a.student_id], kind=KIND, journal_auto=False)
    db.add(task)
    db.flush()
    return task


def result_of(db: Session, t: OnlineTask, student_id: int) -> dict | None:
    """Orijinal testin şagirdi üçün: {'task_id', 'correct', 'total', 'done'} və ya None (başlanmayıb)."""
    a = db.scalar(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.student_id == student_id))
    if not a:
        return None
    x = existing(db, t, a)
    if not x:
        return None
    b = db.scalar(select(TaskAttempt).where(TaskAttempt.task_id == x.id, TaskAttempt.student_id == student_id))
    done = bool(b and b.submitted_at)
    return {'task_id': x.id, 'correct': b.correct if done else None, 'total': len(x.questions), 'done': done}
