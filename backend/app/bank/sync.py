"""Əlavə test bazası – işləyən viktorina saytından avtomatik yenilənmə.

Suallar viktorina.html-in ÖZ idxal funksiyaları ilə oxunur (IMPORT_SOURCES[*].extract) – format dəyişəndə
və ya yeni baza əlavə olunanda burada heç nə dəyişmək lazım gəlmir.

Addımlar:
1. Yüngül yoxlama (brauzersiz): viktorina.html və bütün məlum mənbə fayllarının SHA-256-sı.
   Heç nə dəyişməyibsə – bitir («unchanged»).
2. Dəyişiklik varsa: headless brauzerdə viktorina açılır, mənbə/dərs siyahısı oxunur (yeni dərslər də görünür),
   yalnız dəyişən və yeni fayllar extract olunur.
3. Suallar (fayl, sıra) üzrə yenilənir; itən suallar/fayllar silinmir – active=False (verilmiş testlər
   sualların surətini saxlayır)."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import os
import threading
from dataclasses import dataclass, field
from urllib.parse import urljoin

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from .classify import apply as classify_file
from ..models import AppState, BankFile, BankQuestion, BankSource, BankSync, now

log = logging.getLogger('bank')
_lock = threading.Lock()
LANGS = ('az', 'ru', 'en')
CHROME_DEFAULTS = ['C:/Program Files/Google/Chrome/Application/chrome.exe',
                   '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser']


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------- normallaşdırma
def _ml(v) -> dict | None:
    """Mətn və ya {az,ru,en} -> {az,ru,en} (boşlar atılır)."""
    if v is None:
        return None
    if isinstance(v, str):
        return {'az': v} if v.strip() else None
    if isinstance(v, dict):
        out = {k: v[k] for k in LANGS if isinstance(v.get(k), str) and v[k].strip()}
        return out or None
    return {'az': str(v)}


def to_row(q: dict) -> dict:
    """viktorina normalizeQ/normalizeOpenQ nəticəsi -> BankQuestion sahələri."""
    kind = 'open' if q.get('type') == 'open' else 'mcq'
    row = dict(
        n=int(q['n']), qid=str(q['_qid']) if q.get('_qid') is not None else None, kind=kind,
        text=_ml(q.get('q')) or {'az': ''},
        options=[_ml(o) or {'az': ''} for o in q.get('o') or []] if kind == 'mcq' else None,
        correct=int(q['c']) if kind == 'mcq' else None,
        answer=q.get('a') if kind == 'open' else None,
        explanation=_ml(q.get('ex')), image=q.get('img'),
    )
    row['content_hash'] = sha(json.dumps({k: row[k] for k in ('kind', 'text', 'options', 'correct', 'answer',
                                                              'explanation', 'image')},
                                         ensure_ascii=False, sort_keys=True).encode())
    return row


# ---------------------------------------------------------------- şəbəkə
def fetch_all(urls: list[str], workers: int = 12) -> dict[str, bytes | Exception]:
    """Faylları paralel yükləyir (thread pool – Playwright-in öz event loop-u ilə toqquşmur)."""
    from concurrent.futures import ThreadPoolExecutor
    out: dict[str, bytes | Exception] = {}
    with httpx.Client(timeout=60, follow_redirects=True, headers={'Cache-Control': 'no-cache'}) as c:
        def one(u):
            try:
                r = c.get(u)
                r.raise_for_status()
                return u, r.content
            except Exception as e:                           # noqa: BLE001 – fayl üzrə xəta hesabatda göstərilir
                return u, e
        with ThreadPoolExecutor(workers) as ex:
            out.update(ex.map(one, dict.fromkeys(urls)))
    return out


# ---------------------------------------------------------------- brauzer (viktorina-nın öz funksiyaları)
LIST_JS = """() => Object.entries(IMPORT_SOURCES).filter(([k, s]) => !s.dynamic).map(([k, s]) => ({
  key: k, label: s.label, base: new URL(s.base, location.href).href,
  lessons: s.lessons.map(l => ({ id: l.id, label: l.label || l.id }))
}))"""
EXTRACT_JS = """([key, lesson, url, html]) => {
  const src = IMPORT_SOURCES[key];
  const qs = src.extract(html, 'az', lesson, new URL(url.split('?')[0]).href);
  return (qs || []).map((q, i) => ({ n: i + 1, ...q }));
}"""


class Browser:
    def __init__(self, url: str):
        self.url = url

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        exe = settings().chrome_path or next((p for p in CHROME_DEFAULTS if os.path.exists(p)), None)
        self._b = self._pw.chromium.launch(executable_path=exe) if exe else self._pw.chromium.launch()
        self.page = self._b.new_page()
        self.page.goto(self.url, wait_until='domcontentloaded', timeout=90_000)
        self.page.wait_for_function("typeof IMPORT_SOURCES === 'object'", timeout=60_000)
        return self

    def sources(self) -> list[dict]:
        return self.page.evaluate(LIST_JS)

    def extract(self, key: str, lesson: str, url: str, html: str) -> list[dict]:
        return self.page.evaluate(EXTRACT_JS, [key, lesson, url, html])

    def __exit__(self, *a):
        try:
            self._b.close()
        finally:
            self._pw.stop()


# ---------------------------------------------------------------- əsas funksiya
@dataclass
class SyncResult:
    status: str = 'unchanged'
    files_checked: int = 0
    files_changed: int = 0
    added: int = 0
    updated: int = 0
    deactivated: int = 0
    errors: list[str] = field(default_factory=list)


def _state(db: Session, key: str) -> str | None:
    s = db.get(AppState, key)
    return s.value if s else None


def _set_state(db: Session, key: str, value: str):
    s = db.get(AppState, key) or AppState(key=key)
    s.value = value
    db.merge(s)


def _apply_questions(db: Session, f: BankFile, qs: list[dict], res: SyncResult):
    existing = {q.n: q for q in db.scalars(select(BankQuestion).where(BankQuestion.file_id == f.id))}
    seen = set()
    for q in qs:
        row = to_row(q)
        seen.add(row['n'])
        cur = existing.get(row['n'])
        if cur is None:
            db.add(BankQuestion(file_id=f.id, **row))
            res.added += 1
        elif cur.content_hash != row['content_hash'] or not cur.active or cur.qid != row['qid']:   # qid – kitab nömrəsi (plan testi)
            for k, v in row.items():
                setattr(cur, k, v)
            cur.active, cur.updated_at = True, now()
            res.updated += 1
    for n, cur in existing.items():
        if n not in seen and cur.active:
            cur.active = False
            res.deactivated += 1
    f.question_count = len(qs)


def run_sync(db: Session, trigger: str = 'manual', force: bool = False,
             browser_factory=Browser, fetcher=fetch_all) -> SyncResult:
    """Bir sinxronizasiya. Eyni anda yalnız biri işləyir (qalanları dərhal «busy» qaytarır)."""
    if not _lock.acquire(blocking=False):
        return SyncResult(status='busy')
    cfg = settings()
    log_row = BankSync(trigger=trigger)
    db.add(log_row)
    db.commit()
    res = SyncResult()
    try:
        exclude = {x.strip() for x in cfg.bank_exclude_sources.split(',') if x.strip()}
        files = list(db.scalars(select(BankFile).where(BankFile.active.is_(True))))
        # 1) yüngül yoxlama
        got = fetcher([cfg.viktorina_url] + [f.url for f in files])
        page = got.get(cfg.viktorina_url)
        if isinstance(page, Exception):
            raise RuntimeError(f'viktorina.html açılmadı: {page}')
        page_hash = sha(page)
        page_changed = force or page_hash != _state(db, 'viktorina_sha')
        changed = {f.url for f in files if isinstance(got.get(f.url), bytes) and sha(got[f.url]) != f.sha256}
        res.errors += [f'{f.url}: {got[f.url]}' for f in files if isinstance(got.get(f.url), Exception)]
        res.files_checked = len(files)
        for f in files:
            f.checked_at = now()
        if not page_changed and not changed and not force:
            res.status = 'unchanged'
            db.commit()
            return res

        # 2) brauzer: siyahı + dəyişən/yeni faylların oxunması
        with browser_factory(cfg.viktorina_url) as br:
            listed = [s for s in br.sources() if s['key'] not in exclude]
            by_key = {f'{f.source_key}\u0000{f.lesson}': f for f in db.scalars(select(BankFile))}
            live = set()
            todo: list[tuple[BankFile, str]] = []
            new_urls = []
            for s in listed:
                src = db.get(BankSource, s['key'])
                if src is None:
                    src = BankSource(key=s['key'], label=s['label'], enabled=s['key'] != 'p004')   # TAİM – müəllim imtahanı
                    db.add(src)
                src.label, src.active = s['label'], True
                db.flush()                                    # fayllardan əvvəl (FK)
                for l in s['lessons']:
                    url = urljoin(s['base'], l['id'])
                    k = f"{s['key']}\u0000{l['id']}"
                    live.add(k)
                    f = by_key.get(k)
                    if f is None:
                        f = BankFile(source_key=s['key'], lesson=l['id'], label=l['label'], url=url)
                        db.add(f)
                        db.flush()
                        new_urls.append(url)
                    f.label, f.url, f.active = l['label'], url, True
                    classify_file(f)                              # növ (mövzu/sınaq) və sinif – kilidlidirsə toxunulmur
                    todo.append((f, url))
            for src in db.scalars(select(BankSource)):
                if src.key not in {s['key'] for s in listed}:
                    src.active = False
            if new_urls:
                got.update(fetcher([u for u in new_urls if u not in got]))
            for f, url in todo:
                body = got.get(url)
                if body is None:
                    body = fetcher([url])[url]
                if isinstance(body, Exception):
                    res.errors.append(f'{url}: {body}')
                    continue
                h = sha(body)
                if not force and f.sha256 == h and f.question_count:
                    continue
                try:
                    qs = br.extract(f.source_key, f.lesson, url, body.decode('utf-8', errors='replace'))
                except Exception as e:                       # noqa: BLE001
                    res.errors.append(f'{url}: extract – {str(e)[:200]}')
                    continue
                _apply_questions(db, f, qs, res)
                f.sha256, f.changed_at, f.checked_at = h, now(), now()
                res.files_changed += 1
            for k, f in by_key.items():                       # viktorina-dan çıxarılan dərslər
                if k not in live and f.active:
                    f.active = False
                    for q in db.scalars(select(BankQuestion).where(BankQuestion.file_id == f.id,
                                                                   BankQuestion.active.is_(True))):
                        q.active = False
                        res.deactivated += 1
        _set_state(db, 'viktorina_sha', page_hash)
        res.files_checked = len(todo)
        res.status = 'updated' if (res.added or res.updated or res.deactivated) else 'unchanged'
        db.commit()
        return res
    except Exception as e:                                   # noqa: BLE001
        db.rollback()
        res.status = 'error'
        res.errors.append(str(e)[:500])
        log.exception('bank sync failed')
        return res
    finally:
        row = db.get(BankSync, log_row.id)
        for k in ('status', 'files_checked', 'files_changed', 'added', 'updated', 'deactivated'):
            setattr(row, k, getattr(res, k))
        row.finished_at = now()
        row.message = '\n'.join(res.errors[:50]) or None
        db.commit()
        _lock.release()
