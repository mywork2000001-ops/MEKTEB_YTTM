"""Əlavə test bazası (viktorina.html) – vəziyyət, əl ilə yeniləmə, mənbələr, sual axtarışı."""
import hmac
import threading
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..bank.sync import run_sync
from ..config import settings
from ..db import SessionLocal, get_db
from ..deps import admin_only, staff
from ..models import BankFile, BankQuestion, BankSource, BankSync, User
from .common import audit

router = APIRouter(prefix='/api/bank', tags=['bank'])


def _sync_out(s: BankSync | None):
    return s and {'status': s.status, 'at': s.started_at, 'finished': s.finished_at, 'trigger': s.trigger,
                  'files_changed': s.files_changed, 'added': s.added, 'updated': s.updated,
                  'deactivated': s.deactivated, 'message': s.message}


@router.get('/status')
def status(db: Session = Depends(get_db), _: User = Depends(staff)):
    last = db.scalar(select(BankSync).order_by(BankSync.id.desc()))
    last_ok = db.scalar(select(BankSync).where(BankSync.status.in_(('updated', 'unchanged')))
                        .order_by(BankSync.id.desc()))
    last_upd = db.scalar(select(BankSync).where(BankSync.status == 'updated').order_by(BankSync.id.desc()))
    total = db.scalar(select(func.count()).select_from(BankQuestion).where(BankQuestion.active.is_(True)))
    return {'source_url': settings().viktorina_url, 'auto_minutes': settings().bank_sync_minutes,
            'auto_hours': settings().bank_sync_hours,
            'questions': total, 'last': _sync_out(last), 'last_success_at': last_ok and last_ok.finished_at,
            'last_update': _sync_out(last_upd)}


@router.post('/sync')
def sync_now(force: bool = False, _: User = Depends(admin_only)):
    """Arxa planda başladılır; nəticə /status-da görünür."""
    def job():
        with SessionLocal() as db:
            run_sync(db, 'manual', force=force)
    threading.Thread(target=job, daemon=True).start()
    return {'started': True}


@router.post('/hook')
def sync_hook(x_hook_token: str | None = Header(None)):
    """Viktorina saytı deploy olunanda (GitHub Action) çağırılır – saatlıq yoxlamanı gözləmədən yeniləyir."""
    token = settings().bank_hook_token
    if not token:
        raise HTTPException(404, 'Not Found')
    if not x_hook_token or not hmac.compare_digest(x_hook_token.encode(), token.encode()):
        raise HTTPException(403, 'Yanlış açar')
    from ..scheduler import bank_window_open
    if not bank_window_open():                   # gündüz Chromium açılmır – viktorina dəyişikliyi axşam pəncərəsində götürülür
        return {'started': False, 'deferred': settings().bank_sync_hours}

    def job():
        with SessionLocal() as db:
            run_sync(db, 'hook')
    threading.Thread(target=job, daemon=True).start()
    return {'started': True}


@router.get('/sources')
def sources(db: Session = Depends(get_db), _: User = Depends(staff)):
    counts = dict(db.execute(select(BankFile.source_key, func.count(BankQuestion.id))
                             .join(BankQuestion, BankQuestion.file_id == BankFile.id)
                             .where(BankQuestion.active.is_(True)).group_by(BankFile.source_key)).all())
    kinds: dict[str, dict[str, int]] = {}
    for src, kind, n in db.execute(select(BankFile.source_key, BankFile.kind, func.count(BankFile.id))
                                   .where(BankFile.active.is_(True)).group_by(BankFile.source_key, BankFile.kind)):
        kinds.setdefault(src, {})[kind or 'movzu'] = n
    return [{'key': s.key, 'label': s.label, 'enabled': s.enabled, 'active': s.active,
             'questions': counts.get(s.key, 0), 'kinds': kinds.get(s.key, {})}
            for s in db.scalars(select(BankSource).order_by(BankSource.key))]


class SourcePatch(BaseModel):
    enabled: bool


@router.patch('/sources/{key}')
def patch_source(key: str, body: SourcePatch, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    s = db.get(BankSource, key)
    if not s:
        raise HTTPException(404, 'Mənbə tapılmadı')
    s.enabled = body.enabled
    db.commit()
    return {'key': key, 'enabled': s.enabled}


@router.get('/lessons')
def lessons(source: str, db: Session = Depends(get_db), _: User = Depends(staff)):
    rows = db.scalars(select(BankFile).where(BankFile.source_key == source, BankFile.active.is_(True))
                      .order_by(BankFile.id))
    return [{'id': f.id, 'label': f.label, 'questions': f.question_count, 'kind': f.kind or 'movzu',
             'grades': f.grades or [], 'subject': f.subject, 'meta_locked': bool(f.meta_locked)} for f in rows]


class FilePatch(BaseModel):
    kind: Literal['movzu', 'sinaq', 'yekun', 'diaqnostik'] | None = None
    grades: list[int] | None = None
    subject: str | None = Field(None, max_length=60)
    auto: bool = False                       # true – əl ilə düzəlişi götür, avtomatik təsnifata qaytar


@router.patch('/files/{file_id}')
def patch_file(file_id: int, body: FilePatch, db: Session = Depends(get_db), user: User = Depends(admin_only)):
    """Admin: faylın növü (mövzu testi / sınaq) və sinif(lər)i – avtomatik təsnifat səhv olanda."""
    from ..bank.classify import apply
    f = db.get(BankFile, file_id)
    if not f:
        raise HTTPException(404, 'Fayl tapılmadı')
    if body.auto:
        f.meta_locked = False
        apply(f)
    else:
        if body.grades is not None and any(not 1 <= g <= 12 for g in body.grades):
            raise HTTPException(400, 'Sinif 1–12 olmalıdır')
        for k in ('kind', 'grades', 'subject'):
            v = getattr(body, k)
            if v is not None:
                setattr(f, k, sorted(set(v)) if k == 'grades' else v)
        f.meta_locked = True
    audit(db, user, 'update', 'bank_file', f.id, kind=f.kind, grades=f.grades, locked=f.meta_locked)
    db.commit()
    return {'id': f.id, 'kind': f.kind, 'grades': f.grades or [], 'subject': f.subject, 'meta_locked': f.meta_locked}


@router.get('/questions')
def questions(file_id: int | None = None, source: str | None = None, q: str | None = None,
              kind: str | None = Query(None, pattern='^(mcq|open)$'), offset: int = 0,
              limit: int = Query(50, le=200), db: Session = Depends(get_db), _: User = Depends(staff)):
    st = (select(BankQuestion, BankFile).join(BankFile).join(BankSource, BankSource.key == BankFile.source_key)
          .where(BankQuestion.active.is_(True), BankSource.enabled.is_(True)))
    if file_id:
        st = st.where(BankQuestion.file_id == file_id)
    if source:
        st = st.where(BankFile.source_key == source)
    if kind:
        st = st.where(BankQuestion.kind == kind)
    if q:
        st = st.where(BankQuestion.text['az'].as_string().ilike(f'%{q}%'))
    total = db.scalar(select(func.count()).select_from(st.subquery()))
    rows = db.execute(st.order_by(BankFile.id, BankQuestion.n).offset(offset).limit(limit))
    return {'total': total, 'items': [{
        'id': x.id, 'source': f.source_key, 'lesson': f.label, 'n': x.n, 'kind': x.kind, 'text': x.text,
        'options': x.options, 'correct': x.correct, 'answer': x.answer, 'explanation': x.explanation,
        'image': x.image} for x, f in rows]}
