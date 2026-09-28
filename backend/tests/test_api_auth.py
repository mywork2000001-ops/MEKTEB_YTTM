"""Giriş, rollar, PIN, kilid – test bazası ilə (məxfi fayllara ehtiyac yoxdur)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.db import Base, get_db
from app.main import app
from app.models import Role, User
from app.security import hash_password


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr('app.scheduler.start', lambda: None)      # testdə avtomatik yeniləmə işləmir
    eng = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    S = sessionmaker(eng, expire_on_commit=False)
    with S() as db:
        db.add_all([
            User(role=Role.admin, login='admin', password_hash=hash_password('admin-parol-1'), full_name='Admin'),
            User(role=Role.teacher, login='muellim', password_hash=hash_password('muellim-parol'), full_name='Müəllim'),
            User(role=Role.student, login='XE-001', password_hash=hash_password('1234'), full_name='Şagird'),
        ])
        db.commit()

    def _db():
        with S() as db:
            yield db
    app.dependency_overrides[get_db] = _db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def login(c, u, p):
    return c.post('/api/auth/login', json={'login': u, 'password': p})


def test_login_and_me(client):
    assert client.get('/api/auth/me').status_code == 401
    r = login(client, 'ADMIN', 'admin-parol-1')                   # login böyük/kiçik hərfə həssas deyil
    assert r.status_code == 200 and r.json()['role'] == 'admin'
    assert client.get('/api/auth/me').json()['login'] == 'admin'
    client.post('/api/auth/logout')
    assert client.get('/api/auth/me').status_code == 401


def test_student_login_with_pin(client):
    assert login(client, 'xe-001', '1234').json()['role'] == 'student'


def test_wrong_password_and_lockout(client):
    for _ in range(5):
        assert login(client, 'muellim', 'yanlis').status_code == 401
    assert login(client, 'muellim', 'muellim-parol').status_code == 429   # düzgün parol belə – 15 dəq kilid


def test_role_guards_on_bank(client):
    login(client, 'XE-001', '1234')
    assert client.get('/api/bank/status').status_code == 403            # şagird test bazasını görmür
    login(client, 'muellim', 'muellim-parol')
    assert client.get('/api/bank/status').status_code == 200
    assert client.post('/api/bank/sync').status_code == 403             # yeniləmə yalnız admin
    assert client.patch('/api/bank/sources/p004', json={'enabled': True}).status_code == 403


def test_student_pin_change_rules(client):
    login(client, 'XE-001', '1234')
    assert client.post('/api/auth/password', json={'old': '1234', 'new': '12a4'}).status_code == 400
    assert client.post('/api/auth/password', json={'old': '0000', 'new': '4321'}).status_code == 400
    assert client.post('/api/auth/password', json={'old': '1234', 'new': '4321'}).status_code == 200
    assert client.get('/api/auth/me').status_code == 200                 # yeni kuki verilib
    client.post('/api/auth/logout')
    assert login(client, 'XE-001', '1234').status_code == 401
    assert login(client, 'XE-001', '4321').status_code == 200


def test_old_session_invalid_after_password_change(client):
    login(client, 'muellim', 'muellim-parol')
    old = client.cookies.get('mk_session')
    client.post('/api/auth/password', json={'old': 'muellim-parol', 'new': 'yeni-parol-123'})
    client.cookies.set('mk_session', old)
    assert client.get('/api/auth/me').status_code == 401


def test_seed_real_data(tmp_path):
    """Real UTİS/DİM faylları varsa: ilkin doldurma 76 şagird, PIN-lər yalnız CSV-də, məxfi sahə yoxdur."""
    from app.seed import UTIS_XLSX, seed
    if not UTIS_XLSX.exists():
        pytest.skip('UTİS faylı yoxdur')
    eng = create_engine('sqlite://')
    Base.metadata.create_all(eng)
    with sessionmaker(eng)() as db:
        r = seed(db, out_dir=tmp_path)
        again = seed(db, out_dir=tmp_path)
        n = db.query(models.Student).count()
        codes = {s.portal_code for s in db.query(models.Student)}
        xe = db.query(models.Student).join(models.SchoolClass).filter(models.SchoolClass.name == 'X e').count()
    assert n == 76 and xe == 18 and 'XE-001' in codes and 'XB-020' in codes
    assert again['created'] == [] and again['secrets_file'] is None
    rows = open(r['secrets_file'], encoding='utf-8-sig').read().splitlines()
    assert len(rows) == 1 + 1 + 76                                         # başlıq + admin + şagirdlər
