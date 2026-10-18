"""Neon yatsın: _quiet sarğısı, _ksq_scan_job ipucu, /api/health/db."""
import datetime as dt

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import scheduler


def _at(h, m):
    return dt.datetime(2026, 10, 19, h, m, tzinfo=dt.timezone(dt.timedelta(hours=4)))


def _patch_now(monkeypatch, h, m):
    class FakeDT(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return _at(h, m)
    monkeypatch.setattr(scheduler.dt, 'datetime', FakeDT)


def test_health_db(monkeypatch):
    from app.main import app
    eng = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    monkeypatch.setattr('app.db.SessionLocal', sessionmaker(eng))
    c = TestClient(app)
    r = c.get('/api/health/db')
    assert r.status_code == 200 and r.json() == {'ok': True, 'db': True}

    def boom():
        raise RuntimeError('x')
    monkeypatch.setattr('app.db.SessionLocal', boom)
    r = c.get('/api/health/db')
    assert r.status_code == 503 and r.json() == {'ok': False, 'db': False}


def test_quiet(monkeypatch):
    calls = []
    f = scheduler._quiet(lambda: calls.append(1))
    _patch_now(monkeypatch, 22, 30)          # active_hours (8-22) xaricində, dəq 30
    f()
    assert calls == []
    _patch_now(monkeypatch, 22, 5)
    f()
    assert calls == [1]
    _patch_now(monkeypatch, 10, 30)          # dərs saatı
    f()
    assert calls == [1, 1]


def test_ksq_scan_job_hint(monkeypatch):
    calls = []
    monkeypatch.setattr('app.domain.ksq_reader.read_pending', lambda db, *a, **k: calls.append(1) or 0)
    eng = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    from app.db import Base
    Base.metadata.create_all(eng)
    monkeypatch.setattr(scheduler, 'SessionLocal', sessionmaker(eng))
    monkeypatch.setattr(scheduler, '_scan_hint', False)
    monkeypatch.setattr(scheduler, '_scan_last_db', scheduler.time.monotonic())
    scheduler._ksq_scan_job()
    assert calls == []                       # ipucu yox, <1 saat – bazaya getmir
    scheduler.hint_scans()
    scheduler._ksq_scan_job()
    assert calls == [1]
    assert scheduler._scan_hint is False     # pending kart qalmayıb
