"""Hər plan dərsinə avtomatik mövzu testi (sinif/qrupda «auto_tests» açıqdırsa).

Bütün məntiq tək mühərrikdədir – app/plan_tests.py (docs/plan-testleri-skripti-promtu.md): bu gün mövzusu bitən dərslər üçün
`assign(..., d, d, apply=True)`. Test: açılır dərsin sonunda, bağlanır ertəsi gün 22:00, 45 dəqiqə, sualların sırası qarışıq,
cavablar bağlanandan sonra, nəticə formativ jurnala. Mənbə: müəllimin seçimi → «Test toplusu» (P007) → sinfə görə bank
(GradeMatcher). Bir mövzuya bir test; KSQ/BSQ, şübhəli uyğunluq və artıq testi olan mövzuya yaradılmır."""
from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import TeachingAssignment
from .services import today

log = logging.getLogger('auto_tests')


def run(db: Session, day: dt.date | None = None) -> int:
    from .plan_tests import Opts, assign
    d = day or today()
    made = 0
    for ta in db.scalars(select(TeachingAssignment).where(TeachingAssignment.auto_tests.is_(True),
                                                          TeachingAssignment.archived_at.is_(None))).all():
        try:
            made += sum(1 for r in assign(db, None, [ta], d, d, Opts(), apply=True).rows if r['created'])
        except Exception:                                  # bir sinifdəki xəta digərlərini saxlamasın
            log.exception('auto_tests: ta=%s', ta.id)
            db.rollback()
    return made
