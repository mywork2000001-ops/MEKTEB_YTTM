"""KSQ/BSQ cavab kartlarının skanı (docs/ksq-bsq-kagiz-promtu.md §4, mərhələ 3).

Müəllim kart şəkillərini / skan PDF-i yükləyir → QR ilə şagird tapılır → cavab zonası kəsilir (status pending) → oxunuş gəlir
(mərhələ 4: Claude API; ehtiyat yol: GET /pending + POST /import – bu sessiyadakı Claude Code) → serverdə qiymətləndirmə və
jurnala (ExamScore) avtomatik yazılır. «Yenilə» – bütün kartlar yenidən hesablanır; müəllim tək xananı düzəldə bilər."""
from __future__ import annotations

import base64
import datetime as dt
import io

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import staff
from ..models import Exam, ExamScan, ExamScore, ExamVariant, User, now
from ..exam_logic import exam_roster, recompute_score, scan_of
from ..services import own_assignment
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
    if sc.lost is None and v.unprinted:                     # köhnə çap: kağıza düşməyən + boş cavab – avtomatik ⊘ (bir dəfə)
        empty = {int(r['slot']) for r in sc.reading if r.get('slot') is not None and not r.get('value')}
        sc.lost = sorted(set(v.unprinted) & empty)
    void = {it['n'] for it in (e.items or []) if it.get('annulled')} | set(sc.lost or [])
    g = grade(v.questions, sc.reading, void)
    from ..appeals import accepted_slots, apply_accepted               # qəbul olunmuş apelyasiyalar yenilənmədə itmir
    acc = accepted_slots(db, e.id, sc.student_id, sc.source, v.questions,
                         {int(r['slot']): r.get('value') for r in sc.reading if r.get('slot') is not None})
    if acc:
        g = apply_accepted(g, v.questions, acc, void)
    sc.marks, sc.points, sc.flagged, sc.status, sc.error = g['marks'], g['points'], g['flagged'], 'graded', None
    db.flush()
    recompute_score(db, e, sc.student_id)                   # jurnal balı: seçimə görə (onlayn / yazılı / ən yüksək / əl ilə)


def _ai_error(db: Session, ta, scans: list[ExamScan]) -> str | None:
    from ..domain.ksq_reader import AI_LIMIT, pool_error
    err = next((sc.error for sc in scans if sc.status == 'pending' and (sc.error or '').startswith('ai:')), None)
    return err if err in (None, AI_LIMIT) else pool_error(db, ta.teacher_id)


RECENT_S = 90


def _aware(t: dt.datetime) -> dt.datetime:
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def _out(sc: ExamScan, name: str | None) -> dict:
    return {'id': sc.id, 'student_id': sc.student_id, 'full_name': name, 'code': sc.code, 'status': sc.status, 'points': sc.points,
            'flagged': sc.flagged or [], 'reading': sc.reading, 'marks': sc.marks, 'read_by': sc.read_by, 'source': sc.source, 'error': sc.error,
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
    sc.lost = sorted({s for s in body.slots if s in have})   # boş siyahı da müəllimin qərarıdır – avtomatik ⊘ geri qayıtmır
    apply(db, e, sc)
    audit(db, user, 'update', 'exam_scan', sc.id, lost=sc.lost)
    db.commit()
    return _out(sc, None)


PRINT_FIX_AT = dt.datetime(2026, 10, 13, 11, 0, tzinfo=dt.timezone.utc)   # bu andan əvvəl çap olunan vərəqlərdə suallar kəsilə bilərdi


class LostAutoIn(BaseModel):
    cut: dict[int, list[int]] = Field(default_factory=dict)       # şagird → köhnə çapda kəsilmiş (təxmini) suallar


@router.post('/{ta_id}/{exam_id}/lost-auto')
def lost_auto(ta_id: int, exam_id: int, body: LostAutoIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Kağıza düşməyən suallar (docs/ksq-dusmeyen-suallar-promtu.md): köhnə çapda kəsilmiş (brauzer təxmini) ∩ kartda boş cavab →
    «⊘» (sayılmır). Kəsilmiş sayılan, amma cavabı olan sual – görünürmüş, «⊘» götürülür. Müəllimin başqa «⊘»-larına toxunulmur."""
    ta, e = _exam(db, user, ta_id, exam_id)
    # təxmin saxlanır – təzə skanlarda avtomatik tətbiq olunur (apply); yalnız köhnə çap olunmuş variantlar
    for v in db.scalars(select(ExamVariant).where(ExamVariant.exam_id == e.id)):
        old_print = v.printed_at is not None and _aware(v.printed_at) < PRINT_FIX_AT
        v.unprinted = sorted(set(body.cut.get(v.student_id, []))) if old_print else None
    out = []
    for sc in db.scalars(select(ExamScan).where(ExamScan.exam_id == e.id, ExamScan.source == 'paper', ExamScan.reading.is_not(None))):
        cut = set(body.cut.get(sc.student_id, []))
        filled = {int(r['slot']) for r in sc.reading or [] if r.get('value')}
        empty = {int(r['slot']) for r in sc.reading or [] if not r.get('value')}
        old = set(sc.lost or [])
        new = (old - (cut & filled)) | (cut & empty)
        if new != old:
            before = sc.points
            sc.lost = sorted(new)
            apply(db, e, sc)
            out.append({'student_id': sc.student_id, 'lost': sc.lost or [], 'before': before, 'after': sc.points})
    audit(db, user, 'update', 'exam_scans', e.id, lost_auto=len(out))
    db.commit()
    names = {s.id: s.full_name for s in exam_roster(db, ta, e)}
    return {'changed': [{**x, 'full_name': names.get(x['student_id'])} for x in out]}


def _thorough_bg(bind, ids: list[int]) -> None:
    import logging
    from ..domain.ksq_reader import read_thorough
    try:
        with Session(bind=bind, expire_on_commit=False) as db:
            read_thorough(db, ids)
    except Exception:                                          # noqa: BLE001
        logging.getLogger(__name__).exception('diqqətli oxunuş')


@router.post('/{scan_id}/thorough')
def thorough_one(scan_id: int, bg: BackgroundTasks, user: User = Depends(staff), db: Session = Depends(get_db)):
    """«🔍 Diqqətli oxu» – bir şagirdin kartı (səliqəsiz yazı): böyüdülmüş sütunlar, iki model, səsvermə. Fonda (~1 dəq)."""
    sc, e = _own_scan(db, user, scan_id)
    audit(db, user, 'update', 'exam_scan', sc.id, thorough=True)
    db.commit()
    bg.add_task(_thorough_bg, db.get_bind(), [sc.id])
    return {'started': 1}


@router.post('/{ta_id}/{exam_id}/thorough')
def thorough_all(ta_id: int, exam_id: int, bg: BackgroundTasks, only_flagged: bool = False, user: User = Depends(staff),
                 db: Session = Depends(get_db)):
    """«🔍 Sinfi diqqətli oxu» – bütün kartlar (only_flagged – yalnız sarı xanası olanlar). Fonda, kart-kart."""
    _, e = _exam(db, user, ta_id, exam_id)
    ids = [sc.id for sc in db.scalars(select(ExamScan).where(ExamScan.exam_id == e.id, ExamScan.crop_key.is_not(None)))
           if not only_flagged or sc.flagged]
    audit(db, user, 'update', 'exam_scans', e.id, thorough=len(ids))
    db.commit()
    if ids:
        bg.add_task(_thorough_bg, db.get_bind(), ids)
    return {'started': len(ids)}


def ingest_card(db: Session, e: Exam, variants: dict, c: dict, fname: str | None, found: list, problems: list, dupes: list,
                replace: bool = False, force: bool = False) -> None:
    """Bir kartı (find_cards nəticəsi) imtahana qəbul edir: yoxlamalar → ExamScan (pending) + kəsik şəkil. Həm imtahanın öz
    yükləməsi (upload), həm də ümumi «📷 Skan» (api/scans_any.py) istifadə edir."""
    from ..domain.ksq_card import split_code, variant_rev
    from ..storage import get_storage, storage_for_key
    v = variants.get(c['student_id'])
    if c.get('partial'):                                    # köhnə oxunuşa toxunulmur
        problems.append({'file': fname, 'kind': 'partial', 'student_id': c['student_id'],
                         'error': 'Kart kadra tam düşməyib – bütün kartı çərçivəyə salıb yenidən çəkin'})
        return
    base, rev = split_code(c['code'])
    if v is not None and base == v.code and rev and rev != variant_rev(v.questions):
        problems.append({'file': fname, 'error': f'{base}: kart köhnə çapdır – variant çapdan sonra dəyişib, vərəqi yenidən çap edin'})
        return
    c['code'] = base
    if c['exam_id'] != e.id or v is None or v.code != c['code']:
        problems.append({'file': fname, 'error': f'Kart başqa imtahanın və ya köhnə variantındır ({c["code"]})'})
        return
    sc = scan_of(db, e.id, c['student_id'], 'paper')       # kağız nəticə onlayn nəticədən ayrıdır
    # bir blank – bir dəfə: artıq qəbul edilib (xətasız) – təkrar göndərilmir; yenidən skan – yalnız replace=true ilə
    # təkrar oxunuşdan qorunma (kvota): «yenidən skan» açıq olsa belə, son 90 s-də qəbul edilmiş kart təkrar sayılır
    recent = sc is not None and sc.updated_at is not None and now() - _aware(sc.updated_at) < dt.timedelta(seconds=RECENT_S)
    if sc is not None and sc.crop_key and sc.status != 'error' and (not replace or (recent and not force)):
        if c['student_id'] not in {d['student_id'] for d in dupes}:
            dupes.append({'student_id': c['student_id'], 'scan_id': sc.id, 'status': sc.status, 'points': sc.points})
        return
    if sc is None:
        sc = ExamScan(exam_id=e.id, student_id=c['student_id'], code=c['code'], history=[], source='paper')
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


# ---------------------------------------------------------------- yükləmə, siyahı, yenilə
@router.post('/{ta_id}/{exam_id}/upload')
async def upload(ta_id: int, exam_id: int, bg: BackgroundTasks, files: list[UploadFile] = File(...), replace: bool = False,
                 force: bool = False,             # «↻ Bu kartı yenidən çək» – 90 s qoruması olmadan
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
            ingest_card(db, e, variants, c, f.filename, found, problems, dupes, replace, force)
    audit(db, user, 'create', 'exam_scans', e.id, cards=len(found), problems=len(problems), already=len(dupes))
    db.commit()
    if found:
        from .. import scheduler
        scheduler.hint_scans()
        bg.add_task(_read_now, db.get_bind(), e.id, [x['scan_id'] for x in found])   # yeni kartlar növbəsiz, dərhal (kamera balı gözləyir)
    names = {s.id: s.full_name for s in exam_roster(db, ta, e)}
    return {'found': [{**x, 'full_name': names.get(x['student_id'])} for x in found],
            'problems': [{**p, 'full_name': names.get(p['student_id'])} if p.get('student_id') else p for p in problems],
            'already': [{**x, 'full_name': names.get(x['student_id'])} for x in dupes]}


def _read_now(bind, exam_id: int, ids: list[int] | None = None) -> None:
    """Fon: sorğunun bazası ilə (testdə də eyni) oxunmamış kartları oxuyur; xəta – loqa, kart gözləməyə qalır."""
    import logging
    from ..domain.ksq_reader import read_pending
    try:
        with Session(bind=bind, expire_on_commit=False) as db:
            read_pending(db, exam_id, limit=60, ids=ids)
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
    from ..domain.ksq_reader import key_pool
    ta, e = _exam(db, user, ta_id, exam_id)
    names = {s.id: s.full_name for s in exam_roster(db, ta, e)}
    scans = list(db.scalars(select(ExamScan).where(ExamScan.exam_id == e.id)))      # kağız və onlayn sətirlər (source)
    have = {sc.student_id for sc in scans}
    variants = list(db.scalars(select(ExamVariant.student_id).where(ExamVariant.exam_id == e.id)))
    from ..domain.ksq_card import key_value
    vs = {v.student_id: v for v in db.scalars(select(ExamVariant).where(ExamVariant.exam_id == e.id))}
    # düz cavablar və sual növü – müəllim xananın yanında görür və redaktə edir
    keys = {sid: {q['slot']: key_value(q) for q in v.questions} for sid, v in vs.items()}
    kinds = {sid: {q['slot']: q['kind'] for q in v.questions} for sid, v in vs.items()}
    return {'scans': sorted(({**_out(sc, names.get(sc.student_id)), 'keys': keys.get(sc.student_id) or {},
                              'kinds': kinds.get(sc.student_id) or {}} for sc in scans),
                            key=lambda x: x['full_name'] or ''),
            'missing': sorted((names.get(sid) or '—') for sid in variants if sid not in have),
            'counts': {'variants': len(variants), 'scanned': len(scans), 'graded': sum(sc.status == 'graded' for sc in scans),
                       'pending': sum(sc.status == 'pending' for sc in scans), 'flagged': sum(bool(sc.flagged) for sc in scans)},
            'claude': bool(pool := key_pool(db, ta.teacher_id)),
            # ayrıca kart açarı yoxdur – gündəlik plan açarı işləyir (Tənzimləmələr → Süni intellekt → Kart oxuyucusu)
            'scan_fallback': bool(pool) and all('ümumi' in (c.get('label') or '') for c in pool),
            # süni intellekt xətası (ai:credit / ai:key / ai:rate / ai:limit) – interfeysdə BİR dəfə, kart sətrində yox
            # bütün açarlar limitdədirsə – ən tez bərpa olunanın kodu; açar bərpa olubsa – kartlar özü oxunacaq, banner yox
            'ai_error': _ai_error(db, ta, scans),
            # vərəqlər çap düzəlişindən (13.10.2026) əvvəl çap olunub – suallar kəsilmiş ola bilər
            # köhnə çap təxmini serverdə saxlanıbmı – yoxdursa, brauzer bir dəfə hesablayıb göndərir
            'cut_saved': not any(v.printed_at is not None and _aware(v.printed_at) < PRINT_FIX_AT and v.unprinted is None for v in vs.values()),
            'printed_old': bool(db.scalar(select(ExamVariant.exam_id).where(ExamVariant.exam_id == e.id, ExamVariant.printed_at.is_not(None),
                                                                             ExamVariant.printed_at < PRINT_FIX_AT).limit(1)))}


@router.delete('/{ta_id}/{exam_id}')
def clear_scans(ta_id: int, exam_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """«🗑 Skanları sil» (docs/kart-skanlarini-silme-promtu.md): bu imtahanın KAĞIZ skanları və onların balı silinir – kartlar
    təzədən skan olunur. Onlayn yazılar, variantlar və skansız əl balları qalır. Kəsik şəkilləri saxlanır (ehtiyat)."""
    _, e = _exam(db, user, ta_id, exam_id)
    n = 0
    for sc in list(db.scalars(select(ExamScan).where(ExamScan.exam_id == e.id, ExamScan.source == 'paper'))):
        score = db.get(ExamScore, (e.id, sc.student_id))
        db.delete(sc)
        db.flush()
        if score is not None and score.chosen != 'manual':      # onlayn nəticə varsa – bal ondan; yoxdursa – silinir
            if scan_of(db, e.id, sc.student_id, 'online') is not None:
                recompute_score(db, e, sc.student_id)
            else:
                db.delete(score)
        n += 1
    audit(db, user, 'delete', 'exam_scans', e.id, deleted=n)
    db.commit()
    return {'deleted': n}


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

