"""Daimi «📷 Skan» düyməsi (docs/yazili-sinaq-ve-skan-duymesi-promtu.md §C): hər səhifədən kart yüklənir, imtahanı və şagirdi
QR özü göstərir (sinif/imtahan seçmək lazım deyil). Mövcud skan axını (exam_scans.ingest_card) təkrar istifadə olunur.
QR yoxdur/oxunmur → müəllim şagirdi və imtahanı siyahıdan seçir (son 7 günün imtahanları yuxarıda)."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import staff
from ..exam_logic import exam_label
from ..models import Exam, ExamScan, ExamVariant, SchoolClass, Student, TeachingAssignment, User
from ..services import ws_cond
from .common import audit
from .exam_scans import FILES_MAX, UPLOAD_MAX, _read_now, ingest_card

router = APIRouter(prefix='/api/scans', tags=['scans-any'])


def _label(e: Exam) -> str:
    return (e.title or '').strip() if e.kind in ('TEST', 'SINAQ', 'YI') and (e.title or '').strip() else exam_label(e)


def _mine(db: Session, user: User, e: Exam | None) -> bool:
    if e is None:
        return False
    ta = db.get(TeachingAssignment, e.assignment_id)
    return bool(ta and ta.teacher_id == user.id and not ta.archived_at)


def _my_exams(db: Session, user: User):
    """Müəllimin (aktiv məkanın) çap olunmuş variantı olan imtahanları."""
    return db.execute(
        select(Exam, TeachingAssignment, SchoolClass).join(TeachingAssignment, TeachingAssignment.id == Exam.assignment_id)
        .join(SchoolClass, SchoolClass.id == TeachingAssignment.class_id)
        .where(TeachingAssignment.teacher_id == user.id, TeachingAssignment.archived_at.is_(None), ws_cond(user),
               Exam.id.in_(select(ExamVariant.exam_id)))
        .order_by(Exam.date.desc(), Exam.id.desc())).all()


@router.get('/any/summary')
def summary(user: User = Depends(staff), db: Session = Depends(get_db)):
    """Düymədəki nişan: çap olunub, hələ heç bir kartı qiymətləndirilməyən imtahanların sayı."""
    printed = set(db.scalars(select(ExamVariant.exam_id).where(ExamVariant.printed_at.is_not(None)).distinct()))
    graded = set(db.scalars(select(ExamScan.exam_id).where(ExamScan.source == 'paper', ExamScan.status == 'graded').distinct()))
    mine = {e.id: (e, c) for e, _, c in _my_exams(db, user)}
    waiting = [x for i, x in mine.items() if i in printed and i not in graded]
    return {'waiting': len(waiting), 'exams': [{'exam_id': e.id, 'label': _label(e), 'class_name': c.name} for e, c in waiting[:20]]}


@router.get('/any/options')
def options(user: User = Depends(staff), db: Session = Depends(get_db)):
    """Əl ilə seçim: imtahanlar (son 7 gün yuxarıda) və hər birinin variantı olan şagirdlər."""
    since = dt.date.today() - dt.timedelta(days=7)
    rows = _my_exams(db, user)[:80]
    out = []
    for e, ta, c in rows:
        studs = db.execute(select(Student.id, Student.full_name).join(ExamVariant, ExamVariant.student_id == Student.id)
                           .where(ExamVariant.exam_id == e.id).order_by(Student.full_name)).all()
        out.append({'ta_id': ta.id, 'exam_id': e.id, 'label': _label(e), 'class_name': c.name, 'date': e.date,
                    'recent': e.date >= since, 'students': [{'id': i, 'full_name': n} for i, n in studs]})
    out.sort(key=lambda x: not x['recent'])
    return out


def _result(db: Session, found: list, problems: list, dupes: list, unmatched: int, exams: dict) -> dict:
    names = {s.id: s.full_name for s in db.scalars(select(Student).where(Student.id.in_(
        {x['student_id'] for x in [*found, *dupes, *[p for p in problems if p.get('student_id')]]} or {0})))}
    def tag(x):
        e = exams.get(x.pop('_exam'))
        return {**x, 'full_name': names.get(x['student_id']), 'exam_id': e.id, 'ta_id': e.assignment_id, 'exam': _label(e),
                'list': f'/api/exam-scans/{e.assignment_id}/{e.id}'}
    return {'found': [tag(x) for x in found], 'already': [tag(x) for x in dupes], 'unmatched': unmatched,
            'problems': [{**p, 'full_name': names.get(p.get('student_id'))} for p in problems]}


@router.post('/any')
async def scan_any(bg: BackgroundTasks, files: list[UploadFile] = File(...), replace: bool = False, force: bool = False,
                   user: User = Depends(staff), db: Session = Depends(get_db)):
    """Kart şəkilləri / PDF: QR → imtahan + şagird → müəllimin öz imtahanıdırmı (deyilsə 403) → mövcud skan axını."""
    from ..domain.ksq_scan import find_cards, images_from_upload
    if len(files) > FILES_MAX:
        raise HTTPException(400, f'Bir dəfəyə ən çox {FILES_MAX} fayl')
    found, problems, dupes, exams, vcache = [], [], [], {}, {}
    forbidden = unmatched = 0
    for f in files:
        data = await f.read(UPLOAD_MAX + 1)
        if len(data) > UPLOAD_MAX:
            problems.append({'file': f.filename, 'error': 'Fayl çox böyükdür (25 MB-dan çox)'})
            continue
        try:
            imgs = images_from_upload(data, f.content_type)
        except Exception:                                          # noqa: BLE001
            problems.append({'file': f.filename, 'error': 'Şəkil oxunmadı'})
            continue
        cards = [c for im in imgs for c in find_cards(im)]
        if not cards:
            unmatched += 1
            problems.append({'file': f.filename, 'kind': 'no_qr', 'error': 'QR kod tapılmadı – kartı düz, işıqlı yerdə, tam çəkin'})
        for c in cards:
            e = exams.get(c['exam_id']) or db.get(Exam, c['exam_id'])
            if not _mine(db, user, e):
                forbidden += 1
                problems.append({'file': f.filename, 'kind': 'forbidden', 'error': 'Bu kart sizin imtahanınıza aid deyil'})
                continue
            exams[e.id] = e
            if e.id not in vcache:
                vcache[e.id] = {v.student_id: v for v in db.scalars(select(ExamVariant).where(ExamVariant.exam_id == e.id))}
            n0, d0 = len(found), len(dupes)
            ingest_card(db, e, vcache[e.id], c, f.filename, found, problems, dupes, replace, force)
            for x in found[n0:] + dupes[d0:]:
                x['_exam'] = e.id
    if forbidden and not found and not dupes:
        raise HTTPException(403, 'Bu kart sizin imtahanınıza aid deyil')
    audit(db, user, 'create', 'exam_scans', None, any_cards=len(found), problems=len(problems), already=len(dupes))
    db.commit()
    if found:
        from .. import scheduler
        scheduler.hint_scans()
        for eid in {x['_exam'] for x in found}:
            bg.add_task(_read_now, db.get_bind(), eid, [x['scan_id'] for x in found if x['_exam'] == eid])
    return _result(db, found, problems, dupes, unmatched, exams)


@router.post('/any/manual')
async def scan_manual(bg: BackgroundTasks, exam_id: int = Form(...), student_id: int = Form(...), file: UploadFile = File(...),
                      replace: bool = Form(False), user: User = Depends(staff), db: Session = Depends(get_db)):
    """QR oxunmayanda: müəllim imtahanı və şagirdi özü seçir; kart yenə də şəkildəki QR künclərinə görə kəsilir."""
    from ..domain.ksq_scan import crop_any_qr, images_from_upload
    e = db.get(Exam, exam_id)
    if not _mine(db, user, e):
        raise HTTPException(403, 'Bu imtahan sizin deyil')
    v = db.get(ExamVariant, (e.id, student_id))
    if v is None:
        raise HTTPException(404, 'Bu şagirdin bu imtahan üçün variantı yoxdur')
    data = await file.read(UPLOAD_MAX + 1)
    if len(data) > UPLOAD_MAX:
        raise HTTPException(400, 'Fayl çox böyükdür (25 MB-dan çox)')
    try:
        crop = next((c for im in images_from_upload(data, file.content_type) if (c := crop_any_qr(im))), None)
    except Exception:                                              # noqa: BLE001
        raise HTTPException(400, 'Şəkil oxunmadı')
    if crop is None:
        raise HTTPException(422, 'Kartın QR-ı görünmür – bütün kartı çərçivəyə salıb yenidən çəkin')
    found, problems, dupes = [], [], []
    ingest_card(db, e, {student_id: v}, {'exam_id': e.id, 'student_id': student_id, 'code': v.code, 'crop': crop}, file.filename,
                found, problems, dupes, replace, False)
    for x in found + dupes:
        x['_exam'] = e.id
    audit(db, user, 'create', 'exam_scans', e.id, manual=len(found))
    db.commit()
    if found:
        from .. import scheduler
        scheduler.hint_scans()
        bg.add_task(_read_now, db.get_bind(), e.id, [x['scan_id'] for x in found])
    return _result(db, found, problems, dupes, 0, {e.id: e})
