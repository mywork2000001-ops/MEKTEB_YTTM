"""Dəftər yoxlaması API: AI (şəkil) və ƏL ilə (müəllim gözlə baxır) – eyni saxlama: material_submissions.ai_check.

ai_check = {source: 'ai'|'manual', checked_at, model, legible, summary_az, student_comment{az,ru,en},
            items: [{subtopic, status: done|partial|missing|illegible|None, wrong[], note, source: 'ai'|'manual'}]}
Əl ilə işarə AI-ni ÜSTƏLƏYİR (AI təkrar yoxlama əl işarələrinə toxunmur). Şəkli olmayan şagirdə də işarə qoymaq olar –
cavabsız (mətnsiz/faylsız) MaterialSubmission yaradılır; o, «təhvil verib» sayılmır. Qiymət QOYULMUR."""
from __future__ import annotations

import csv
import io
import logging
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import defter as D
from ..db import get_db
from ..deps import staff
from ..domain import ksq_reader as R
from ..models import BankFile, Material, MaterialSubmission, SchoolClass, Student, TeachingAssignment, User, now
from ..services import roster
from ..storage import storage_for_key
from .common import audit, get_or_404

router = APIRouter(prefix='/api', tags=['defter'])
log = logging.getLogger(__name__)
MARKS = ('done', 'partial', 'missing')
SL = {'done': 'icra olunub', 'partial': 'qismən', 'missing': 'icra olunmayıb', 'illegible': 'oxunmur'}


def _L(user: User, az: str, ru: str, en: str) -> str:
    return {'ru': ru, 'en': en}.get(getattr(user, 'language', None), az)


def _mat(db: Session, user: User, mid: int) -> tuple[Material, TeachingAssignment]:
    m = get_or_404(db, Material, mid, 'Material')
    ta = db.get(TeachingAssignment, m.assignment_id)
    if not ta or ta.teacher_id != user.id or ta.archived_at or m.archived_at:
        raise HTTPException(404, 'Material tapılmadı')
    return m, ta


def _students(db: Session, m: Material, ta: TeachingAssignment) -> list[Student]:
    return [s for s in roster(db, ta) if not m.student_ids or s.id in m.student_ids]


def _sub(db: Session, m: Material, st_id: int, create: bool = False) -> MaterialSubmission | None:
    s = db.scalar(select(MaterialSubmission).where(MaterialSubmission.material_id == m.id, MaterialSubmission.student_id == st_id))
    if s is None and create:
        s = MaterialSubmission(material_id=m.id, student_id=st_id, submitted_at=now())
        db.add(s)
        db.flush()
    return s


def _own_student(db: Session, m: Material, ta: TeachingAssignment, sid: int) -> Student:
    st = next((x for x in _students(db, m, ta) if x.id == sid), None)
    if not st:
        raise HTTPException(404, 'Şagird tapılmadı')
    return st


def _names(subs: list[str]) -> list[str]:
    out = []
    for s in subs:
        s = ' '.join(str(s).split())[:200]
        if s and s not in out:
            out.append(s)
    return out[:12]


# ---------------------------------------------------------------- alt mövzu təklifi
@router.get('/materials/{mid}/subtopics')
def suggest_subtopics(mid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Materialın sinfi + başlığı üzrə bank nişanları (alt mövzular). Tapılmasa – boş; müəllim özü yazır."""
    m, ta = _mat(db, user, mid)
    grade = db.get(SchoolClass, ta.class_id).grade
    words = [w.lower()[:5] for w in (m.title or '').replace('-', ' ').split() if len(w) >= 4]
    out: list[str] = []
    if words:
        for f in db.scalars(select(BankFile).where(BankFile.active.is_(True), BankFile.kind == 'movzu')):
            lab = (f.label or '').strip()
            if not lab or lab in out or (grade and f.grades and grade not in f.grades):
                continue
            if any(w in lab.lower() for w in words):
                out.append(lab)
            if len(out) >= 30:
                break
    saved = _saved_subtopics(db, m)
    return {'subtopics': out, 'saved': saved}


def _saved_subtopics(db: Session, m: Material) -> list[str]:
    seen: list[str] = []
    for s in db.scalars(select(MaterialSubmission).where(MaterialSubmission.material_id == m.id).order_by(MaterialSubmission.id)):
        for it in (s.ai_check or {}).get('items') or []:
            if it['subtopic'] not in seen:
                seen.append(it['subtopic'])
    return seen


# ---------------------------------------------------------------- AI yoxlama
class CheckIn(BaseModel):
    subtopics: list[str] = Field(min_length=1, max_length=12)
    topic: str | None = Field(None, max_length=200)


def _images(db: Session, s: MaterialSubmission, user: User) -> list[tuple[bytes, str]]:
    ctype = (s.file_type or '').split(';')[0]
    if not s.file_key or ctype not in D.IMG_TYPES:
        raise D.DefterError({'az': 'Yoxlamaq üçün dəftər şəkli (JPG/PNG) lazımdır', 'ru': 'Для проверки нужно фото тетради (JPG/PNG)',
                             'en': 'A notebook photo (JPG/PNG) is needed for the check'})
    data = b''.join(storage_for_key(s.file_key).stream(s.file_key, db))
    return [(data, ctype)]


def _ai_msg(user: User, ex: Exception) -> str:
    code = str(ex)
    if code == R.AI_CREDIT:
        return _L(user, 'Süni intellekt balansı bitib', 'Баланс ИИ закончился', 'The AI balance is used up')
    if code == R.AI_KEY:
        return _L(user, 'Süni intellekt açarı işləmir (Tənzimləmələr)', 'Ключ ИИ не работает (Настройки)', 'The AI key does not work (Settings)')
    return _L(user, 'Süni intellekt hazırda cavab vermir – bir azdan yenidən yoxlayın', 'ИИ сейчас не отвечает – попробуйте чуть позже',
              'The AI is not responding right now – try again shortly')


def run_check(db: Session, user: User, ta: TeachingAssignment, m: Material, s: MaterialSubmission, subtopics: list[str],
              topic: str | None) -> dict:
    """Bir göndərişi AI ilə yoxla, ai_check-ə yaz (əl işarələri qalır). Xəta – HTTPException/DefterError."""
    imgs = _images(db, s, user)
    st = db.get(Student, s.student_id)
    lang = getattr(db.get(User, st.user_id), 'language', None) if st and st.user_id else None
    pool = [c for c in R.key_pool(db, ta.teacher_id) if not R.cooling(c)]
    if not pool:
        raise HTTPException(503, _L(user, 'Süni intellekt açarı yoxdur və ya dincdədir (Tənzimləmələr → Kart oxuyucusu)',
                                    'Нет ключа ИИ или он отдыхает (Настройки)', 'No AI key, or it is resting (Settings)'))
    res, last = None, None
    for c in pool:
        try:
            res = D.check_notebook(c, imgs, topic or m.title, subtopics, lang or 'az')
            model = c['model']
            break
        except D.DefterError:
            raise
        except Exception as ex:                                      # noqa: BLE001
            last = ex
            if isinstance(ex, R.AiError):
                R.cool(c, ex)
    if res is None:
        raise HTTPException(502, _ai_msg(user, last or RuntimeError('')))
    old = {i['subtopic']: i for i in (s.ai_check or {}).get('items') or [] if i.get('source') == 'manual'}
    items = [old.get(i['subtopic']) or {**i, 'source': 'ai'} for i in res['items']]
    items += [i for k, i in old.items() if k not in {x['subtopic'] for x in items}]
    s.ai_check = {**res, 'items': items, 'source': 'ai', 'checked_at': now().isoformat(), 'model': model}
    db.flush()
    return s.ai_check


def _run_err(user: User, ex: Exception) -> HTTPException:
    if isinstance(ex, D.DefterError):
        return HTTPException(502 if ex.msg is D.ERR else 400, _L(user, ex.msg['az'], ex.msg['ru'], ex.msg['en']))
    return ex  # type: ignore[return-value]


@router.post('/materials/{mid}/submissions/{sid}/check')
def check_one(mid: int, sid: int, body: CheckIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    m, ta = _mat(db, user, mid)
    s = get_or_404(db, MaterialSubmission, sid, 'Cavab')
    if s.material_id != m.id:
        raise HTTPException(404, 'Cavab tapılmadı')
    try:
        ai = run_check(db, user, ta, m, s, _names(body.subtopics), body.topic)
    except (D.DefterError, HTTPException) as ex:
        db.rollback()
        raise _run_err(user, ex)
    audit(db, user, 'update', 'defter_check', s.id)
    db.commit()
    return ai


_JOBS: dict[int, dict] = {}


def _bg(bind, user_id: int, mid: int, subs: list[str], topic: str | None) -> None:
    job = _JOBS[mid]
    try:
        with Session(bind=bind, expire_on_commit=False) as db:
            user = db.get(User, user_id)
            m = db.get(Material, mid)
            ta = db.get(TeachingAssignment, m.assignment_id)
            for sid in job['ids']:
                try:
                    s = db.get(MaterialSubmission, sid)
                    run_check(db, user, ta, m, s, subs, topic)
                    db.commit()
                    job['done'] += 1
                except Exception:                                    # noqa: BLE001 – xəta olan keçilir
                    db.rollback()
                    job['failed'] += 1
    except Exception:                                                # noqa: BLE001
        log.exception('dəftər yoxlaması')
    finally:
        job['running'] = False


@router.post('/materials/{mid}/check-all')
def check_all(mid: int, body: CheckIn, bg: BackgroundTasks, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Hələ AI ilə yoxlanmamış şəkilli göndərişlər – fonda, ardıcıl."""
    m, ta = _mat(db, user, mid)
    if (_JOBS.get(mid) or {}).get('running'):
        raise HTTPException(409, _L(user, 'Yoxlama artıq gedir', 'Проверка уже идёт', 'The check is already running'))
    ids = [s.id for s in db.scalars(select(MaterialSubmission).where(MaterialSubmission.material_id == m.id))
           if s.file_key and (s.file_type or '').split(';')[0] in D.IMG_TYPES and not (s.ai_check or {}).get('checked_at')]
    _JOBS[mid] = {'ids': ids, 'total': len(ids), 'done': 0, 'failed': 0, 'running': bool(ids)}
    audit(db, user, 'update', 'defter_check_all', m.id, n=len(ids))
    db.commit()
    if ids:
        bg.add_task(_bg, db.get_bind(), user.id, m.id, _names(body.subtopics), body.topic)
    return {'started': len(ids)}


@router.get('/materials/{mid}/check-all')
def check_all_state(mid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    m, _ = _mat(db, user, mid)
    subs = db.scalars(select(MaterialSubmission).where(MaterialSubmission.material_id == m.id)).all()
    j = _JOBS.get(mid) or {}
    return {'ready': sum(bool((s.ai_check or {}).get('checked_at')) for s in subs),
            'with_photo': sum(bool(s.file_key) for s in subs), 'running': bool(j.get('running')),
            'done': j.get('done', 0), 'failed': j.get('failed', 0), 'total': j.get('total', 0)}


# ---------------------------------------------------------------- əl ilə işarə + cədvəl
class MarkIn(BaseModel):
    student_id: int
    subtopic: str = Field(min_length=1, max_length=200)
    status: Literal['done', 'partial', 'missing'] | None = None
    note: str | None = Field(None, max_length=200)


@router.put('/materials/{mid}/mark')
def mark(mid: int, body: MarkIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Bir xana: şagird × alt mövzu. Dərhal yazılır; status None – xana boşaldılır. Əl işarəsi AI-ni üstələyir."""
    m, ta = _mat(db, user, mid)
    _own_student(db, m, ta, body.student_id)
    sub = _sub(db, m, body.student_id, create=True)
    ai = dict(sub.ai_check or {'source': 'manual', 'items': []})
    items = [dict(i) for i in ai.get('items') or []]
    name = ' '.join(body.subtopic.split())
    it = next((i for i in items if i['subtopic'] == name), None)
    if it is None:
        it = {'subtopic': name, 'status': None, 'wrong': [], 'note': ''}
        items.append(it)
    it.update(status=body.status, note=(body.note or '').strip()[:200] if body.status == 'partial' else '', source='manual')
    ai['items'] = items
    ai.setdefault('source', 'manual')
    sub.ai_check = ai
    db.commit()
    return {'ok': True, 'status': body.status}


def _table(db: Session, m: Material, ta: TeachingAssignment, extra: list[str]) -> dict:
    subs = {s.student_id: s for s in db.scalars(select(MaterialSubmission).where(MaterialSubmission.material_id == m.id))}
    cols = _saved_subtopics(db, m)
    cols += [e for e in _names(extra) if e not in cols]
    studs = _students(db, m, ta)
    rows = []
    for st in studs:
        s = subs.get(st.id)
        items = {i['subtopic']: {'status': i.get('status'), 'note': i.get('note') or '', 'wrong': i.get('wrong') or [],
                                 'source': i.get('source', 'ai')} for i in (s.ai_check or {}).get('items') or []} if s else {}
        rows.append({'student_id': st.id, 'full_name': st.full_name, 'submission_id': s.id if s else None,
                     'has_photo': bool(s and s.file_key), 'items': items, 'grade': s.grade if s else None,
                     'teacher_comment': s.comment if s else None,
                     'comment': ((s.ai_check or {}).get('student_comment') or {}).get('az') if s else None,
                     'summary': (s.ai_check or {}).get('summary_az') if s else None})
    n = len(studs) or 1
    pct = {c: round(100 * sum((r['items'].get(c) or {}).get('status') == 'done' for r in rows) / n) for c in cols}
    return {'subtopics': cols, 'rows': rows, 'percent': pct}


@router.get('/materials/{mid}/defter')
def defter_table(mid: int, extra: str = '', user: User = Depends(staff), db: Session = Depends(get_db)):
    """Cədvəl: bütün sinif × alt mövzu + hər alt mövzunun icra faizi. extra – hələ işarəsiz əlavə sütunlar («a|b»)."""
    m, ta = _mat(db, user, mid)
    return {'material': {'id': m.id, 'title': m.title}, **_table(db, m, ta, [x for x in extra.split('|') if x.strip()])}


@router.get('/materials/{mid}/check.csv')
def check_csv(mid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    m, ta = _mat(db, user, mid)
    t = _table(db, m, ta, [])
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=';')
    w.writerow(['şagird', 'alt_mövzu', 'status', 'səhv', 'şərh'])
    for r in t['rows']:
        for sub in t['subtopics']:
            it = r['items'].get(sub)
            if not it or not it['status']:
                continue
            w.writerow([_safe(r['full_name']), _safe(sub), SL[it['status']], ', '.join(it['wrong']), _safe(it['note'])])
    for sub, p in t['percent'].items():
        w.writerow(['SİNİF', _safe(sub), f'{p}%', '', ''])
    return Response('﻿' + buf.getvalue(), media_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition': 'attachment; filename="defter-yoxlama.csv"'})


def _safe(v: str) -> str:
    v = v or ''
    return "'" + v if v[:1] in ('=', '+', '-', '@') else v
