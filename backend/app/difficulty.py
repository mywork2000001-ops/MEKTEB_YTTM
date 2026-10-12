"""Bank suallarının faktiki çətinliyi (docs/yuz-balliq-sistem-promtu.md): təhvil verilmiş bütün cəhdlərdən düz cavab payı
→ asan / orta / çətin (≥10 cavab). Gecə yenilənir; yeni testlərin balı buna görə paylanır (verilmiş testlər dəyişmir)."""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from .domain.scoring import from_stats
from .models import BankQuestion, OnlineTask, TaskAttempt


def update_difficulty(db: Session) -> int:
    """Statistikanı yenidən hesablayır; dəyişən sualların sayını qaytarır. Heç cavab verməyən (boş) cəhd sayılmır."""
    from .api.tasks import is_ok
    n: dict[int, int] = defaultdict(int)
    ok: dict[int, int] = defaultdict(int)
    for t, a in db.execute(select(OnlineTask, TaskAttempt).join(TaskAttempt, TaskAttempt.task_id == OnlineTask.id)
                           .where(TaskAttempt.submitted_at.is_not(None))):
        if not any(v not in (None, '') for v in (a.answers or {}).values()):
            continue
        for i, q in enumerate(t.questions or []):
            bid = q.get('bank_id') if isinstance(q, dict) else None
            if bid:
                n[bid] += 1
                ok[bid] += is_ok(t, a, i)
    changed = 0
    for q in db.scalars(select(BankQuestion).where(BankQuestion.id.in_(list(n) or [-1]))):
        new = (n[q.id], ok[q.id], from_stats(n[q.id], ok[q.id]))
        if (q.stat_n, q.stat_ok, q.diff_auto) != new:
            q.stat_n, q.stat_ok, q.diff_auto = new
            changed += 1
    db.commit()
    return changed
