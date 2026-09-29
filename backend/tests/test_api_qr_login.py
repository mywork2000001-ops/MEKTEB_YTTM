"""Avtomatik giriş: vərəqədəki QR kod (PIN dəyişəndə etibarsız), sürüşən sessiya."""
from fastapi.testclient import TestClient

from app.main import app


def test_qr_login_and_invalidation(world):
    as_, _ = world
    a = as_('admin')
    cid = a.post('/api/classes', json={'name': 'X e'}).json()['id']
    s = a.post('/api/students', json={'full_name': 'Birinci Şagird qızı', 'class_id': cid}).json()
    sheet = a.get(f'/api/students/by-class/{cid}/login-sheet').json()['students'][0]
    assert sheet['qr'] and sheet['pin'] == s['initial_pin']
    c = TestClient(app); c.__enter__()
    r = c.post('/api/auth/qr', json={'token': sheet['qr']})
    assert r.status_code == 200 and r.json()['role'] == 'student'
    assert c.get('/api/portal/me').json()['portal_code'] == s['portal_code']        # kuki qoyulub – daxil olub
    assert TestClient(app).post('/api/auth/qr', json={'token': sheet['qr'] + 'x'}).status_code == 401
    # PIN-i özü dəyişir → köhnə QR işləmir, yeni vərəqədə QR yoxdur (PIN-i yalnız şagird bilir)
    assert c.post('/api/auth/password', json={'old': s['initial_pin'], 'new': '9876'}).status_code == 200
    assert TestClient(app).post('/api/auth/qr', json={'token': sheet['qr']}).status_code == 401
    assert a.get(f'/api/students/by-class/{cid}/login-sheet').json()['students'][0]['qr'] is None
    # müəllim hesabı üçün QR yoxdur
    me = a.get('/api/auth/me').json()
    from app.security import make_qr_token
    from app.db import get_db
    db = next(app.dependency_overrides[get_db]())
    from app.models import User
    u = db.get(User, me['id'])
    assert TestClient(app).post('/api/auth/qr', json={'token': make_qr_token(u.id, u.password_hash)}).status_code == 401


def test_sliding_session(world, monkeypatch):
    as_, _ = world
    a = as_('admin')
    r = a.get('/api/auth/me')
    assert 'set-cookie' not in r.headers                                              # təzə sessiya – yenilənmir
    monkeypatch.setattr('app.api.auth.session_age', lambda t: 2 * 24 * 3600)
    r = a.get('/api/auth/me')
    assert 'mk_session' in r.headers.get('set-cookie', '') and 'Max-Age=15552000' in r.headers['set-cookie']
