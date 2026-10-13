"""KSQ/BSQ cavab kartlarının skanı (docs/ksq-bsq-kagiz-promtu.md §4, mərhələ 3).

Müəllim kart şəkillərini / skan PDF-i yükləyir → QR ilə şagird tapılır → cavab zonası kəsilir (status pending) → oxunuş gəlir
(mərhələ 4: Claude API; ehtiyat yol: GET /pending + POST /import – bu sessiyadakı Claude Code) → serverdə qiymətləndirmə və
jurnala (ExamScore) avtomatik yazılır. «Yenilə» – bütün kartlar yenidən hesablanır; müəllim tək xananı düzəldə bilər."""
from __future__ import annotations

import base64
import io

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import staff
from ..models import Exam, ExamScan, ExamScore, ExamVariant, User, now
from ..services import own_assignment, roster
from .common import audit, get_or_404

router = APIRouter(prefix='/api/exam-scans', tags=['exam-scans'])
UPLOAD_MAX = 25 * 1024 * 1024
FILES_MAX = 40


def _exam(db: Session, user: User, ta_id: int, exam_id: int) -> tuple:
    ta = own_assignment(db, user, ta_id)
    e = get_or_404(db, Exam, exam_id, 'İmtahan')
    if e.assignment_id != ta.id:
        raise HTTPException(404, 'İmtahan tapılmadı')
    return ta, e


def _own_scan(db: Session, user: User, scan_id: int) -> tuple[ExamScan, Exam]:
    sc = get_or_404(db, ExamScan, scan_id, 'Skan')
    e = db.get(Exam, sc.exam_id)
    own_assignment(db, user, e.assignment_id)
    return sc, e


def apply(db: Session, e: Exam, sc: ExamScan) -> None:
    """Oxunuşa görə bal → skan və jurnal (ExamScore). Variant yoxdursa – xəta statusu."""
    from ..domain.ksq_scan import grade
    v = db.get(ExamVariant, (e.id, sc.student_id))
    if v is None or v.code != sc.code:
        sc.status, sc.error = 'error', 'Bu kodla variant yoxdur (variantlar yenidən yaradılıb?)'
        return
    if sc.reading is None:
        sc.status = 'pending'
        return
    g = grade(v.questions, sc.reading, {it['n'] for it in (e.items or []) if it.get('annulled')} | set(sc.lost or []))
    sc.marks, sc.points, sc.flagged, sc.status, sc.error = g['marks'], g['points'], g['flagged'], 'graded', None
    score = db.get(ExamScore, (e.id, sc.student_id)) or ExamScore(exam_id=e.id, student_id=sc.student_id)
    score.points, score.item_marks, score.absent = g['points'], g['marks'], False
    db.add(score)


def _out(sc: ExamScan, name: str | None) -> dict:
    return {'id': sc.id, 'student_id': sc.student_id, 'full_name': name, 'code': sc.code, 'status': sc.status, 'points': sc.points,
            'flagged': sc.flagged or [], 'reading': sc.reading, 'marks': sc.marks, 'read_by': sc.read_by, 'error': sc.error,
            'updated_at': sc.updated_at, 'rescans': len(sc.history or []), 'lost': sc.lost or [],
            'n': len(sc.marks or []) or None}


# ---------------------------------------------------------------- ehtiyat yol: oxunmamış kartlar və idxal (Claude Code)
@router.get('/pending')
def pending(images: bool = False, limit: int = 30, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Müəllimin oxunmamış kartları: gözlənilən quruluş (slot, növ) və istəyə görə cavab zonasının şəkli (base64 JPEG)."""
    from ..storage import storage_for_key
    out = []
    for sc in db.scalars(select(ExamScan).where(ExamScan.status == 'pending').order_by(ExamScan.id).limit(max(1, min(limit, 100)))):
        e = db.get(Exam, sc.exam_id)
        try:
            own_assignment(db, user, e.assignment_id)
        except HTTPException:
            continue
        v = db.get(ExamVariant, (e.id, sc.student_id))
        x = {'scan_id': sc.id, 'exam': f'{e.kind}-{e.no}', 'code': sc.code,
             'slots': [{'slot': q['slot'], 'kind': q['kind']} for q in sorted(v.questions, key=lambda q: q['slot'])] if v else []}
        if images and sc.crop_key:
            x['image_jpeg_b64'] = base64.b64encode(b''.join(storage_for_key(sc.crop_key).stream(sc.crop_key, db))).decode()
        out.append(x)
    return out


class Cell(BaseModel):
    slot: int = Field(ge=1, le=60)
    value: str | None = Field(None, max_length=12)
    confidence: float | None = Field(None, ge=0, le=1)


class ImportIn(BaseModel):
    scan_id: int
    answers: list[Cell] = Field(max_length=60)


@router.post('/import')
def import_readings(body: list[ImportIn], user: User = Depends(staff), db: Session = Depends(get_db)):
    """Kart oxunuşlarını qəbul edir ({scan_id, answers:[{slot, value, confidence}]}) və dərhal qiymətləndirir."""
    n = 0
    for it in body[:200]:
        sc, e = _own_scan(db, user, it.scan_id)
        sc.reading, sc.read_by = [c.model_dump() for c in it.answers], 'import'
        apply(db, e, sc)
        n += 1
    audit(db, user, 'update', 'exam_scans', None, imported=n)
    db.commit()
    return {'ok': True, 'graded': n}


@router.get('/image/{scan_id}')
def image(scan_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    from ..storage import storage_for_key
    sc, _ = _own_scan(db, user, scan_id)
    if not sc.crop_key:
        raise HTTPException(404, 'Şəkil yoxdur')
    return StreamingResponse(storage_for_key(sc.crop_key).stream(sc.crop_key, db), media_type='image/jpeg',
                             headers={'Cache-Control': 'private, max-age=300'})


class FixIn(BaseModel):
    slot: int = Field(ge=1, le=60)
    value: str | None = Field(None, max_length=12)


@router.put('/{scan_id}/slot')
def fix_slot(scan_id: int, body: FixIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Müəllim bir xananı düzəldir (etibar = 1) → yenidən hesablanır."""
    sc, e = _own_scan(db, user, scan_id)
    rd = [r for r in (sc.reading or []) if r.get('slot') != body.slot]
    rd.append({'slot': body.slot, 'value': body.value, 'confidence': 1.0, 'by': 'teacher'})
    sc.reading = sorted(rd, key=lambda r: r['slot'])
    apply(db, e, sc)
    audit(db, user, 'update', 'exam_scan', sc.id, slot=body.slot, value=body.value)
    db.commit()
    return _out(sc, None)


class LostIn(BaseModel):
    slots: list[int] = Field(default_factory=list, max_length=60)


@router.put('/{scan_id}/lost')
def set_lost(scan_id: int, body: LostIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Müəllim: bu şagirdin vərəqində görünməyən (çapda kəsilmiş) suallar – sayılmır, qalanlar 100-ə miqyaslanır."""
    sc, e = _own_scan(db, user, scan_id)
    v = db.get(ExamVariant, (e.id, sc.student_id))
    have = {q['slot'] for q in (v.questions if v else [])}
    sc.lost = sorted({s for s in body.slots if s in have}) or None
    apply(db, e, sc)
    audit(db, user, 'update', 'exam_scan', sc.id, lost=sc.lost)
    db.commit()
    return _out(sc, None)


# ---------------------------------------------------------------- yükləmə, siyahı, yenilə
@router.post('/{ta_id}/{exam_id}/upload')
async def upload(ta_id: int, exam_id: int, bg: BackgroundTasks, files: list[UploadFile] = File(...), replace: bool = False,
                 user: User = Depends(staff), db: Session = Depends(get_db)):
    """Kart şəkilləri və ya skan PDF: QR → şagird; cavab zonası saxlanır. Eyni şagirdin kartı təkrar gəlsə – köhnə oxunuş arxivə."""
    from ..domain.ksq_scan import find_cards, images_from_upload
    from ..domain.ksq_card import split_code, variant_rev
    from ..storage import get_storage, storage_for_key
    ta, e = _exam(db, user, ta_id, exam_id)
    if len(files) > FILES_MAX:
        raise HTTPException(400, f'Bir dəfəyə ən çox {FILES_MAX} fayl')
    variants = {v.student_id: v for v in db.scalars(select(ExamVariant).where(ExamVariant.exam_id == e.id))}
    if not variants:
        raise HTTPException(409, 'Bu imtahan üçün kağız variant yoxdur')
    found, problems, dupes = [], [], []
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
            problems.append({'file': f.filename, 'error': 'QR kod tapılmadı – kartı düz, işıqlı yerdə, tam çəkin'})
        for c in cards:
            v = variants.get(c['student_id'])
            if c.get('partial'):                                    # köhnə oxunuşa toxunulmur
                problems.append({'file': f.filename, 'kind': 'partial', 'student_id': c['student_id'],
                                 'error': 'Kart kadra tam düşməyib – bütün kartı çərçivəyə salıb yenidən çəkin'})
                continue
            base, rev = split_code(c['code'])
            if v is not None and base == v.code and rev and rev != variant_rev(v.questions):
                problems.append({'file': f.filename, 'error': f'{base}: kart köhnə çapdır – variant çapdan sonra dəyişib, vərəqi yenidən çap edin'})
                continue
            c['code'] = base
            if c['exam_id'] != e.id or v is None or v.code != c['code']:
                problems.append({'file': f.filename, 'error': f'Kart başqa imtahanın və ya köhnə variantındır ({c["code"]})'})
                continue
            sc = db.scalar(select(ExamScan).where(ExamScan.exam_id == e.id, ExamScan.student_id == c['student_id']))
            # bir blank – bir dəfə: artıq qəbul edilib (xətasız) – təkrar göndərilmir; yenidən skan – yalnız replace=true ilə
            if sc is not None and sc.crop_key and sc.status != 'error' and not replace:
                if c['student_id'] not in {d['student_id'] for d in dupes}:
                    dupes.append({'student_id': c['student_id'], 'scan_id': sc.id, 'status': sc.status, 'points': sc.points})
                continue
            if sc is None:
                sc = ExamScan(exam_id=e.id, student_id=c['student_id'], code=c['code'], history=[])
                db.add(sc)
            elif sc.reading or sc.crop_key:
                sc.history = [*(sc.history or []), {'at': now().isoformat(), 'reading': sc.reading, 'points': sc.points,
                                                    'read_by': sc.read_by}][-5:]
                if sc.crop_key and sc.crop_key.startswith('db:'):
                    storage_for_key(sc.crop_key).remove(db, sc.crop_key)
            key, _ = get_storage().save(io.BytesIO(c['crop']), f'ksq-{e.id}-{c["student_id"]}.jpg', 'image/jpeg', UPLOAD_MAX, db)
            sc.crop_key, sc.code, sc.reading, sc.read_by, sc.status, sc.marks, sc.flagged, sc.error = \
                key, c['code'], None, None, 'pending', None, None, None
            db.flush()
            found.append({'student_id': c['student_id'], 'code': c['code'], 'scan_id': sc.id})
    audit(db, user, 'create', 'exam_scans', e.id, cards=len(found), problems=len(problems), already=len(dupes))
    db.commit()
    if found:
        bg.add_task(_read_now, db.get_bind(), e.id)                     # Claude açarı varsa – dərhal oxunur (fon işi də hər 2 dəq yoxlayır)
    names = {s.id: s.full_name for s in roster(db, ta)}
    return {'found': [{**x, 'full_name': names.get(x['student_id'])} for x in found],
            'problems': [{**p, 'full_name': names.get(p['student_id'])} if p.get('student_id') else p for p in problems],
            'already': [{**x, 'full_name': names.get(x['student_id'])} for x in dupes]}


def _read_now(bind, exam_id: int) -> None:
    """Fon: sorğunun bazası ilə (testdə də eyni) oxunmamış kartları oxuyur; xəta – loqa, kart gözləməyə qalır."""
    import logging
    from ..domain.ksq_reader import read_pending
    try:
        with Session(bind=bind, expire_on_commit=False) as db:
            read_pending(db, exam_id, limit=60)
    except Exception:                                          # noqa: BLE001
        logging.getLogger(__name__).exception('kart oxunuşu')


@router.post('/{ta_id}/{exam_id}/reread')
def reread(ta_id: int, exam_id: int, bg: BackgroundTasks, user: User = Depends(staff), db: Session = Depends(get_db)):
    """«Yenidən oxu»: bütün kartlar Claude-a təzədən göndərilir (müəllimin əl düzəlişləri də silinir)."""
    _, e = _exam(db, user, ta_id, exam_id)
    n = 0
    for sc in db.scalars(select(ExamScan).where(ExamScan.exam_id == e.id, ExamScan.crop_key.is_not(None))):
        sc.history = [*(sc.history or []), {'at': now().isoformat(), 'reading': sc.reading, 'points': sc.points,
                                            'read_by': sc.read_by}][-5:]
        sc.reading, sc.read_by, sc.status, sc.error = None, None, 'pending', None
        n += 1
    audit(db, user, 'update', 'exam_scans', e.id, reread=n)
    db.commit()
    bg.add_task(_read_now, db.get_bind(), e.id)
    return {'ok': True, 'pending': n}


@router.get('/{ta_id}/{exam_id}')
def list_scans(ta_id: int, exam_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    from ..domain.ksq_reader import api_key_for
    ta, e = _exam(db, user, ta_id, exam_id)
    names = {s.id: s.full_name for s in roster(db, ta)}
    scans = list(db.scalars(select(ExamScan).where(ExamScan.exam_id == e.id)))
    have = {sc.student_id for sc in scans}
    variants = list(db.scalars(select(ExamVariant.student_id).where(ExamVariant.exam_id == e.id)))
    return {'scans': sorted((_out(sc, names.get(sc.student_id)) for sc in scans), key=lambda x: x['full_name'] or ''),
            'missing': sorted((names.get(sid) or '—') for sid in variants if sid not in have),
            'counts': {'variants': len(variants), 'scanned': len(scans), 'graded': sum(sc.status == 'graded' for sc in scans),
                       'pending': sum(sc.status == 'pending' for sc in scans), 'flagged': sum(bool(sc.flagged) for sc in scans)},
            'claude': bool(api_key_for(db, ta.teacher_id))}


@router.post('/{ta_id}/{exam_id}/regrade')
def regrade(ta_id: int, exam_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """«Yenilə»: bütün kartlar mövcud açarla yenidən hesablanır (açar / variant düzəldilibsə)."""
    _, e = _exam(db, user, ta_id, exam_id)
    n = 0
    for sc in db.scalars(select(ExamScan).where(ExamScan.exam_id == e.id)):
        apply(db, e, sc)
        n += sc.status == 'graded'
    audit(db, user, 'update', 'exam_scans', e.id, regraded=n)
    db.commit()
    return {'ok': True, 'graded': n}

