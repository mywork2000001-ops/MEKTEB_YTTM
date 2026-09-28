"""Şagird siyahısının importu (admin): UTİS faylı (+ istəyə görə DİM buraxılış balları).
Uşaq İD, şəxsiyyət vəsiqəsi, pinkod oxunmur/saxlanmır. PIN-lər yalnız bu cavabda bir dəfə qaytarılır."""
import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..importers.utis import read_utis
from ..models import SchoolClass, User
from ..seed import add_students
from .common import admin_only_unlocked, audit, current_year, need_school

router = APIRouter(prefix='/api/import', tags=['import'])


@router.post('/roster')
def import_roster(utis: UploadFile = File(...), dim: UploadFile | None = File(None),
                  user: User = Depends(admin_only_unlocked), db: Session = Depends(get_db)):
    sid = need_school(user)
    year = current_year(db, sid)
    d = io.BytesIO(dim.file.read()) if dim is not None and dim.filename else None
    try:
        roster = read_utis(io.BytesIO(utis.file.read()), d)
    except Exception as e:                                       # noqa: BLE001 – fayl formatı xətası istifadəçiyə
        raise HTTPException(400, f'UTİS faylı oxunmadı: {e}')
    classes = db.scalars(select(SchoolClass).where(SchoolClass.school_id == sid, SchoolClass.year_id == year.id,
                                                   SchoolClass.archived_at.is_(None),
                                                   SchoolClass.utis_class.is_not(None)))
    rows, matched = [], []
    for sc in classes:
        if sc.utis_class in roster.classes:
            matched.append(sc.name)
            rows += add_students(db, sc, roster.classes[sc.utis_class], user.id)
    audit(db, user, 'import', 'roster', None, added=len(rows), classes=matched)
    db.commit()
    return {'matched_classes': matched, 'utis_classes': sorted(roster.classes),
            'added': [{'class_name': c, 'full_name': n, 'portal_code': k, 'pin': p} for c, n, k, p in rows],
            'without_scores': len(roster.without_scores), 'warnings': roster.warnings}
