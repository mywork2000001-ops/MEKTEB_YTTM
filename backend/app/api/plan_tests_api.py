"""«Testləri təyin et»: perspektiv plandan mövzu testləri (bir sinif, seçilənlər və ya hamısı) – önbaxış və təsdiq.
Bütün məntiq app/plan_tests.py mühərrikindədir (docs/plan-testleri-skripti-promtu.md §2.3)."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import plan_tests as E
from ..db import get_db
from ..deps import staff
from ..models import User
from ..services import today
from .common import audit  # noqa: F401 – audit mühərrikin içində yazılır

router = APIRouter(prefix='/api/plan-tests', tags=['plan-tests'])


class OptsIn(BaseModel):
    n_questions: int = Field(15, ge=1, le=100)
    duration: int = Field(45, ge=1, le=300)
    missing: bool = False
    missing_close_days: int = Field(3, ge=1, le=30)
    include_weak: bool = False


class PlanTestsIn(BaseModel):
    ta_ids: list[int] | None = Field(None, max_length=200)      # seçilən siniflər; boş + all – hamısı
    all: bool = False                                           # müəllim: bütün dərslərim; admin: məktəbin bütün dərsləri
    date_from: dt.date | None = None                            # defolt: bu gün (çatışanlar rejimində – ilin əvvəli)
    date_to: dt.date | None = None                              # defolt: from + 7 gün
    opts: OptsIn = Field(default_factory=OptsIn)


def _run(body: PlanTestsIn, user: User, db: Session, apply: bool) -> dict:
    tas = E.scope_tas(db, user, ta_ids=body.ta_ids, everything=body.all)
    if body.ta_ids and len(tas) != len(set(body.ta_ids)):
        raise HTTPException(404, 'Dərs tapılmadı')
    if not tas:
        raise HTTPException(400, 'Sinif seçin')
    d1 = body.date_from or (None if body.opts.missing else today())
    d2 = body.date_to or ((d1 or today()) + dt.timedelta(days=7))
    if d1 and d2 < d1:
        raise HTTPException(400, 'Bitmə tarixi başlanğıcdan əvvəldir')
    rep = E.assign(db, user, tas, d1, d2, E.Opts(**body.opts.model_dump()), apply=apply)
    return rep.to_dict()


@router.post('/preview')
def preview(body: PlanTestsIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Hesabat – heç nə yazmır."""
    return _run(body, user, db, False)


@router.post('/assign')
def assign(body: PlanTestsIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Testləri yaradır (audit jurnalına: ümumi yazı + hər tapşırıq); təkrar çağırış dublikat yaratmır."""
    return _run(body, user, db, True)
