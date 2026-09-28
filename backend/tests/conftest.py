"""Ortaq test mühiti: yaddaşda SQLite, iki məktəb, admin + iki müəllim, cari tədris ili."""
import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import AcademicYear, Role, School, User
from app.security import hash_password


@pytest.fixture
def world(monkeypatch):
    monkeypatch.setattr('app.scheduler.start', lambda: None)
    eng = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    S = sessionmaker(eng, expire_on_commit=False)
    with S() as db:
        s1 = School(name='Tərtər şəhər Rafiq Nuriyev adına 6 nömrəli tam orta ümumtəhsil məktəbi', utis='111')
        s2 = School(name='Bərdə şəhər 1 nömrəli məktəb', utis='222')
        db.add_all([s1, s2])
        db.flush()
        for s in (s1, s2):
            db.add(AcademicYear(school_id=s.id, name='2026–2027', start=dt.date(2026, 9, 15),
                                sem1_end=dt.date(2027, 1, 26), sem2_start=dt.date(2027, 2, 1),
                                end=dt.date(2027, 6, 14), is_current=True))
        db.add_all([
            User(role=Role.admin, login='admin', password_hash=hash_password('admin-parol'), full_name='Həsənov Fərid',
                 school_id=s1.id),
            User(role=Role.teacher, login='ilqar', password_hash=hash_password('ilqar-parol'), full_name='Nəcəfov İlqar',
                 school_id=s1.id),
            User(role=Role.teacher, login='yad', password_hash=hash_password('yad-parol1'), full_name='Başqa Müəllim',
                 school_id=s2.id),
            User(role=Role.teacher, login='yeni', password_hash=hash_password('yeni-parol'), full_name='Yeni Müəllim'),
        ])
        db.commit()

    def _db():
        with S() as db:
            yield db
    app.dependency_overrides[get_db] = _db
    clients = {}

    def as_(login):
        if login not in clients:
            c = TestClient(app)
            c.__enter__()
            pw = {'admin': 'admin-parol', 'ilqar': 'ilqar-parol', 'yad': 'yad-parol1', 'yeni': 'yeni-parol'}[login]
            assert c.post('/api/auth/login', json={'login': login, 'password': pw}).status_code == 200
            clients[login] = c
        return clients[login]
    yield as_, S
    for c in clients.values():
        c.__exit__(None, None, None)
    app.dependency_overrides.clear()
