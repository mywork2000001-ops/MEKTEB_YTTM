"""Hər plan dərsinə avtomatik mövzu testi (sinif/qrupda «auto_tests» açıqdırsa).

Bütün məntiq tək mühərrikdədir – app/plan_tests.py (docs/plan-testleri-skripti-promtu.md): bu gün mövzusu bitən dərslər üçün
`assign(..., d, d, apply=True)`. Test: açılır dərsin sonunda, defoltda müddətsiz (son tarix və taymer yoxdur; close_days/duration
verilsə – dərsdən N gün sonra 22:00 / taymerlə), sualların sırası qarışıq, cavablar müddətsizdə təhvildən dərhal sonra, müddətlidə
bağlanandan sonra, nəticə formativ jurnala. Mənbə: müəllimin seçimi → «Test toplusu» (P007) → sinfə görə bank
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
    made += run_review(db, d)
    return made


def run_review(db: Session, day: dt.date | None = None) -> int:
    """«Təkrar testləri» açarı açıq siniflərdə interval təkrar (14 / 42 gün, sinif ortası < 60%) – plan_tests.review_assign."""
    from .plan_tests import review_assign, review_on
    d = day or today()
    made = 0
    for ta in db.scalars(select(TeachingAssignment).where(TeachingAssignment.archived_at.is_(None))).all():
        if not review_on(ta):
            continue
        try:
            made += sum(1 for r in review_assign(db, [ta], d, apply=True).rows if r['created'])
        except Exception:
            log.exception('auto_tests review: ta=%s', ta.id)
            db.rollback()
    return made
