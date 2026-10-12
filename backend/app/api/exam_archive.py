"""KSQ/BSQ arxivi (istifadəçi tələbi, 12.10.2026): müəllimin bütün KSQ/BSQ-ləri siniflər və tarix üzrə ZIP-də –
Google Drive qovluğunda «data» kimi saxlamaq üçün; sonra kart şəkilləri serverdən silinə bilər (sistem yüklənməsin).

ZIP quruluşu:  {Sinif · Fənn}/{YYYY-MM-DD KSQ-1}/
    variantlar.json  – hər şagirdin sualları (mətn, variantlar, cavab, bal)
    acar.csv         – variant kodu × slot → düzgün cavab
    neticeler.csv    – şagird, kod, bal, faiz, qiymət, skan vəziyyəti, oxunmuş cavablar
    kartlar/KOD.jpg  – cavab kartının adsız kəsiyi (varsa)"""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import staff
from ..domain.rules import grade_from_points
from ..models import Exam, ExamScan, ExamScore, ExamVariant, SchoolClass, Student, TeachingAssignment, User
from .common import audit

router = APIRouter(prefix='/api/exam-archive', tags=['exam-archive'])


def _safe(s: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', ' ', s or '').strip()[:80] or '—'


def _csv(rows: list[list]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=';')
    w.writerows(rows)
    return ('﻿' + buf.getvalue()).encode('utf-8')                 # Excel Azərbaycan hərflərini düz açsın


def _my_exams(db: Session, user: User, ta_id: int | None) -> list[tuple[Exam, TeachingAssignment, SchoolClass]]:
    q = select(Exam, TeachingAssignment, SchoolClass).join(TeachingAssignment, TeachingAssignment.id == Exam.assignment_id) \
        .join(SchoolClass, SchoolClass.id == TeachingAssignment.class_id).where(TeachingAssignment.teacher_id == user.id)
    if ta_id:
        q = q.where(TeachingAssignment.id == ta_id)
    return list(db.execute(q.order_by(SchoolClass.name, Exam.date)).all())


@router.get('/zip')
def archive_zip(ta_id: int | None = None, user: User = Depends(staff), db: Session = Depends(get_db)):
    from ..domain.ksq_card import key_value
    from ..storage import storage_for_key
    rows = _my_exams(db, user, ta_id)
    if not rows:
        raise HTTPException(404, 'KSQ/BSQ tapılmadı')
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for e, ta, cls in rows:
            base = f'{_safe(cls.name)} · {_safe(ta.subject)}/{e.date.isoformat()} {e.kind}-{e.no}'
            vs = sorted(db.scalars(select(ExamVariant).where(ExamVariant.exam_id == e.id)), key=lambda v: v.code)
            names = {s.id: s.full_name for s in db.scalars(select(Student).where(Student.id.in_([v.student_id for v in vs] or [0])))}
            scores = {s.student_id: s for s in db.scalars(select(ExamScore).where(ExamScore.exam_id == e.id))}
            scans = {s.student_id: s for s in db.scalars(select(ExamScan).where(ExamScan.exam_id == e.id))}
            meta = {'sinif': cls.name, 'fenn': ta.subject, 'imtahan': f'{e.kind}-{e.no}', 'yarimil': e.semester,
                    'tarix': e.date.isoformat(), 'max_bal': e.max_points, 'tapsiriqlar': e.items}
            z.writestr(f'{base}/variantlar.json', json.dumps(
                {**meta, 'variantlar': [{'kod': v.code, 'sagird': names.get(v.student_id), 'suallar': v.questions} for v in vs]},
                ensure_ascii=False, indent=1, default=str))
            n = max((len(v.questions) for v in vs), default=0)
            z.writestr(f'{base}/acar.csv', _csv([['kod', 'şagird', *range(1, n + 1)]] + [
                [v.code, names.get(v.student_id), *[key_value(q) for q in sorted(v.questions, key=lambda q: q['slot'])]] for v in vs]))
            res = [['şagird', 'kod', 'bal', 'faiz', 'qiymət', 'skan', 'oxunmuş cavablar']]
            sids = [v.student_id for v in vs] or list(scores)
            for sid in sids:
                sc, sn = scores.get(sid), scans.get(sid)
                pts = sc.points if sc and not sc.absent else None
                res.append([names.get(sid) or sid, next((v.code for v in vs if v.student_id == sid), ''),
                            '' if pts is None else str(pts).replace('.', ','),
                            '' if pts is None else str(round(pts * 100 / e.max_points, 1)).replace('.', ','),
                            grade_from_points(pts, e.max_points) if pts is not None else ('yox idi' if sc and sc.absent else ''),
                            sn.status if sn else '', ' '.join(f'{r["slot"]}:{r.get("value") or "-"}' for r in (sn.reading or [])) if sn else ''])
                if sn and sn.crop_key:
                    try:
                        z.writestr(f'{base}/kartlar/{_safe(sn.code)}.jpg', b''.join(storage_for_key(sn.crop_key).stream(sn.crop_key, db)))
                    except Exception:                       # noqa: BLE001 – şəkil oxunmasa arxiv yenə yaranır
                        pass
            z.writestr(f'{base}/neticeler.csv', _csv(res))
    audit(db, user, 'export', 'exam_archive', ta_id, exams=len(rows))
    db.commit()
    return Response(out.getvalue(), media_type='application/zip',
                    headers={'Content-Disposition': 'attachment; filename="KSQ-BSQ-arxiv.zip"'})


@router.post('/purge-images')
def purge_images(ta_id: int | None = None, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Arxiv endirildikdən sonra: kart şəkilləri serverdən silinir (oxunuş, bal və jurnal qalır)."""
    from ..storage import DbStorage
    n = 0
    for e, _, _ in _my_exams(db, user, ta_id):
        for sc in db.scalars(select(ExamScan).where(ExamScan.exam_id == e.id, ExamScan.crop_key.is_not(None))):
            if sc.crop_key.startswith('db:'):
                DbStorage.remove(db, sc.crop_key)
            sc.crop_key = None
            n += 1
    audit(db, user, 'delete', 'exam_scan_images', ta_id, removed=n)
    db.commit()
    return {'ok': True, 'removed': n}
