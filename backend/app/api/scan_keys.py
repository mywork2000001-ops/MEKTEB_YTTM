"""Kart oxuyucusu üçün ayrıca süni intellekt açarları (docs/kart-oxuyucu-acarlar-promtu.md, 13.10.2026).

Ən çox 5 açar (users.ai_settings.scan_keys): hər birində provayder (standart – Google Gemini · AI Studio), model, açar,
«aktiv». Oxuyucu açarları sıra ilə işlədir; limit / balans / açar xətasında avtomatik növbəti açara keçir
(domain/ksq_reader.key_pool). Açar heç vaxt geri göndərilmir – yalnız maska."""
from __future__ import annotations

import datetime as dt
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import ai
from ..db import get_db
from ..deps import staff
from ..domain import ksq_reader as R
from ..models import User
from ..security import secret_decrypt, secret_encrypt
from .common import audit, settings_unlocked

router = APIRouter(prefix='/api/ai/scan-keys', tags=['ai'])
MODELS = {'gemini': ['gemini-flash-latest', 'gemini-flash-lite-latest', 'gemini-pro-latest', 'gemini-2.5-flash'],   # «-latest» köhnəlmir
          'openrouter': ['google/gemini-2.5-flash', 'anthropic/claude-sonnet-4.5', 'openai/gpt-4o'],
          'anthropic': [R.MODEL]}


def _rows(user: User) -> list[dict]:
    return list(((user.ai_settings or {}).get('scan_keys') or [])[:R.SCAN_KEYS_MAX])


def _out(user: User) -> dict:
    rows = []
    for i, k in enumerate(_rows(user) + [None] * (R.SCAN_KEYS_MAX - len(_rows(user)))):
        key = secret_decrypt(k.get('key')) if k else None
        st = None
        if key:
            c = R._conn_of(k['provider'], k.get('model') or '', key)
            cl = R.cooling(c)
            st = {'state': 'cooldown' if cl else 'ok', 'code': cl['code'] if cl else None,
                  'until': dt.datetime.fromtimestamp(cl['until'], dt.timezone.utc).isoformat() if cl else None,
                  'today': R.today_count(c)}
        rows.append({'no': i + 1, 'provider': (k or {}).get('provider') or 'gemini',
                     'model': (k or {}).get('model') or MODELS[(k or {}).get('provider') or 'gemini'][0],
                     'on': bool(k and k.get('on', True)), 'has_key': bool(key),
                     'key_mask': ('••••' + key[-4:]) if key and len(key) > 8 else ('••••' if key else None), 'status': st})
    return {'keys': rows,
            'providers': [{'id': p, 'label': ai.PROVIDERS[p]['label'] + (' · AI Studio' if p == 'gemini' else ''),
                           'models': MODELS[p], 'key_url': ai.PROVIDERS[p].get('key_url'), 'hint': ai.PROVIDERS[p].get('hint')}
                          for p in R.SCAN_PROVIDERS]}


@router.get('')
def get_keys(user: User = Depends(staff)):
    return _out(user)


class KeyIn(BaseModel):
    provider: str | None = None                   # None – boş sətir (açar silinir)
    model: str | None = Field(None, max_length=120)
    api_key: str | None = Field(None, max_length=400)   # boş – bu sətirdəki köhnə açar qalır
    keep_from: int | None = Field(None, ge=1, le=5)     # sıra dəyişəndə: köhnə açar hansı sətirdən (1–5)
    on: bool = True


class KeysIn(BaseModel):
    keys: list[KeyIn] = Field(max_length=5)


@router.put('')
def put_keys(body: KeysIn, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    old = _rows(user)
    new = []
    for i, k in enumerate(body.keys):
        if not k.provider:
            continue
        if k.provider not in R.SCAN_PROVIDERS:
            raise HTTPException(400, 'Naməlum provayder')
        key = (k.api_key or '').strip()
        if key:
            if len(key) < 12 or re.search(r'\s', key):
                raise HTTPException(400, f'Açar {i + 1}: API açarı düzgün görünmür')
            enc = secret_encrypt(key)
        else:
            src = old[(k.keep_from or i + 1) - 1] if (k.keep_from or i + 1) <= len(old) else None
            if not src or not src.get('key'):
                continue                                  # açarsız sətir saxlanmır
            enc = src['key']
        model = (k.model or '').strip() or MODELS[k.provider][0]
        new.append({'provider': k.provider, 'model': model, 'key': enc, 'on': k.on})
    user.ai_settings = {**(user.ai_settings or {}), 'scan_keys': new}
    audit(db, user, 'update', 'ai_scan_keys', user.id, n=len(new), providers=[k['provider'] for k in new])
    db.commit()
    return _out(user)


@router.post('/{no}/test')
def test_key(no: int, user: User = Depends(staff)):
    rows = _rows(user)
    if not 1 <= no <= len(rows) or not rows[no - 1].get('key'):
        raise HTTPException(404, 'Açar yoxdur')
    k = rows[no - 1]
    key = secret_decrypt(k['key'])
    c = R._conn_of(k['provider'], k.get('model') or '', key)
    txt = ai.complete({'provider': c['provider'], 'model': c['model'], 'base_url': None, 'api_key': key},
                      'Qısa cavab ver.', 'Yalnız bu sözü yaz: HAZIR', json_mode=False, max_tokens=400)
    R.uncool(c)                                           # işləyir – dincdən çıxır
    return {'ok': True, 'reply': txt.strip()[:80], 'model': c['model']}


@router.post('/reset')
def reset(user: User = Depends(staff), db: Session = Depends(get_db)):
    """Müəllimin açar hovuzunun dincini sıfırla (balans artırılıb / yeni gün) – gözləyən kartlar növbəti dövrədə oxunur."""
    pool = R.key_pool(db, user.id)
    for c in pool:
        R.uncool(c)
    return {'ok': True, 'keys': len(pool)}
