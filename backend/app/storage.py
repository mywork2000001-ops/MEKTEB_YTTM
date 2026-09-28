"""Çat faylları üçün saxlama – üç rejim (MK_STORAGE):
- gdrive: Google Drive qovluğu (pulsuz 15 GB, 2 GB-a qədər fayl) – istifadəçinin OAuth icazəsi ilə (refresh token);
- db:     verilənlər bazası (1 MB hissələr) – hostinq yenidən başlayanda silinmir (Neon pulsuz 0,5 GB – cəmi həcm);
- local:  disk qovluğu (inkişaf).
Hamısı axınla işləyir: fayl yaddaşa bütöv yüklənmir."""
from __future__ import annotations

import secrets
import time
from pathlib import Path
from typing import BinaryIO, Iterator

import httpx
from fastapi import HTTPException
from sqlalchemy import LargeBinary, Integer, String, delete, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .config import settings
from .db import Base

CHUNK = 1024 * 1024


class FileBlob(Base):
    __tablename__ = 'file_blobs'
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[bytes] = mapped_column(LargeBinary)


def _read_limited(src: BinaryIO, limit: int, size: int = CHUNK) -> Iterator[bytes]:
    total = 0
    while chunk := src.read(size):
        total += len(chunk)
        if total > limit:
            raise HTTPException(413, f'Fayl {limit // 1024 ** 2} MB-dan böyükdür')
        yield chunk


class LocalStorage:
    kind = 'local'

    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def save(self, src: BinaryIO, name: str, mime: str, limit: int, db: Session) -> tuple[str, int]:
        key = secrets.token_hex(16)
        dest, size = self.root / key, 0
        try:
            with open(dest, 'wb') as out:
                for ch in _read_limited(src, limit):
                    out.write(ch)
                    size += len(ch)
        except BaseException:
            dest.unlink(missing_ok=True)
            raise
        return key, size

    def stream(self, key: str, db: Session) -> Iterator[bytes]:
        with open(self.root / key, 'rb') as f:
            while ch := f.read(CHUNK):
                yield ch


class DbStorage:
    kind = 'db'

    def save(self, src: BinaryIO, name: str, mime: str, limit: int, db: Session) -> tuple[str, int]:
        key, size, seq = 'db:' + secrets.token_hex(16), 0, 0
        try:
            for ch in _read_limited(src, limit):
                db.add(FileBlob(key=key, seq=seq, data=ch))
                db.flush()
                seq += 1
                size += len(ch)
        except BaseException:
            db.rollback()
            raise
        return key, size

    def stream(self, key: str, db: Session) -> Iterator[bytes]:
        n = db.scalar(select(func.count()).select_from(FileBlob).where(FileBlob.key == key)) or 0
        for i in range(n):
            yield db.scalar(select(FileBlob.data).where(FileBlob.key == key, FileBlob.seq == i))

    @staticmethod
    def used_bytes(db: Session) -> int:
        return db.scalar(select(func.coalesce(func.sum(func.length(FileBlob.data)), 0))) or 0

    @staticmethod
    def remove(db: Session, key: str):
        db.execute(delete(FileBlob).where(FileBlob.key == key))


class GDriveStorage:
    """Google Drive REST (httpx): resumable yükləmə 8 MB hissələrlə, axınla endirmə."""
    kind = 'gdrive'
    UP = 'https://www.googleapis.com/upload/drive/v3/files'
    API = 'https://www.googleapis.com/drive/v3/files'
    PART = 8 * 1024 * 1024                       # 256 KB-ın misli olmalıdır

    def __init__(self, folder: str, client_id: str, client_secret: str, refresh_token: str):
        self.folder, self.cid, self.secret, self.refresh = folder, client_id, client_secret, refresh_token
        self._tok, self._exp = None, 0.0

    def token(self) -> str:
        if self._tok and time.time() < self._exp - 60:
            return self._tok
        r = httpx.post('https://oauth2.googleapis.com/token', timeout=30, data={
            'client_id': self.cid, 'client_secret': self.secret, 'refresh_token': self.refresh,
            'grant_type': 'refresh_token'})
        if r.status_code != 200:
            raise HTTPException(503, 'Google Drive icazəsi etibarsızdır – admin yenidən qoşmalıdır')
        j = r.json()
        self._tok, self._exp = j['access_token'], time.time() + j.get('expires_in', 3600)
        return self._tok

    def save(self, src: BinaryIO, name: str, mime: str, limit: int, db: Session) -> tuple[str, int]:
        h = {'Authorization': f'Bearer {self.token()}'}
        r = httpx.post(self.UP, params={'uploadType': 'resumable', 'fields': 'id'}, timeout=60,
                       headers={**h, 'X-Upload-Content-Type': mime or 'application/octet-stream'},
                       json={'name': name, 'parents': [self.folder]})
        if r.status_code != 200:
            raise HTTPException(502, f'Google Drive: yükləmə başlamadı ({r.status_code})')
        loc, pos, buf, file_id = r.headers['Location'], 0, b'', None
        with httpx.Client(timeout=300) as c:
            def send(data: bytes, final: bool):
                nonlocal pos, file_id
                end = pos + len(data) - 1
                total = str(pos + len(data)) if final else '*'
                rng = f'bytes {pos}-{end}/{total}' if data else f'bytes */{pos}'
                resp = c.put(loc, content=data, headers={'Authorization': f'Bearer {self.token()}', 'Content-Range': rng})
                if resp.status_code in (200, 201):
                    file_id = resp.json()['id']
                elif resp.status_code != 308:
                    raise HTTPException(502, f'Google Drive: yükləmə kəsildi ({resp.status_code})')
                pos += len(data)
            for ch in _read_limited(src, limit):
                buf += ch
                while len(buf) >= self.PART + 1:              # son hissə «final» kimi göndərilsin deyə 1 bayt saxlanır
                    send(buf[:self.PART], False)
                    buf = buf[self.PART:]
            send(buf, True)
        if not file_id:
            raise HTTPException(502, 'Google Drive: fayl yaranmadı')
        return 'gd:' + file_id, pos

    def stream(self, key: str, db: Session) -> Iterator[bytes]:
        fid = key.removeprefix('gd:')
        with httpx.stream('GET', f'{self.API}/{fid}', params={'alt': 'media'}, timeout=300,
                          headers={'Authorization': f'Bearer {self.token()}'}) as r:
            if r.status_code != 200:
                raise HTTPException(404, 'Fayl Google Drive-da tapılmadı')
            yield from r.iter_bytes(CHUNK)


_cache: dict = {}


def storage_for_key(key: str):
    """Köhnə fayllar öz yerindən oxunur (rejim dəyişsə də)."""
    if key.startswith('gd:'):
        return get_storage('gdrive')
    if key.startswith('db:'):
        return DbStorage()
    return get_storage('local')


def get_storage(kind: str | None = None):
    cfg = settings()
    kind = kind or cfg.storage
    if kind == 'gdrive':
        if not (cfg.gdrive_folder_id and cfg.gdrive_client_id and cfg.gdrive_client_secret and cfg.gdrive_refresh_token):
            raise HTTPException(503, 'Google Drive qoşulmayıb')
        k = ('gdrive', cfg.gdrive_folder_id)
        if k not in _cache:
            _cache[k] = GDriveStorage(cfg.gdrive_folder_id, cfg.gdrive_client_id, cfg.gdrive_client_secret,
                                      cfg.gdrive_refresh_token)
        return _cache[k]
    if kind == 'db':
        return DbStorage()
    from .api.chat import upload_dir
    return LocalStorage(upload_dir())


def upload_limit() -> int:
    """gdrive/local – 2 GB; db – pulsuz bazanın həcminə görə 50 MB (bütöv baza 0,5 GB)."""
    return 50 * 1024 ** 2 if settings().storage == 'db' else 2 * 1024 ** 3
