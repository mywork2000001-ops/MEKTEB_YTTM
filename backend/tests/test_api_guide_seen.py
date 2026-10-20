"""Şagirdin giriş videosu: guide_due / POST /api/portal/guide-seen / GUIDE_VERSION / müəllim siyahısında nişan."""
from fastapi.testclient import TestClient

from app.main import app


def _student(code, pin):
    c = TestClient(app)
    c.__enter__()
    assert c.post('/api/auth/login', json={'login': code, 'password': pin}).status_code == 200
    return c


def _setup(world):
    as_, S = world
    admin = as_('admin')
    cid = admin.post('/api/classes', json={'name': 'X e'}).json()['id']
    st = [admin.post('/api/students', json={'full_name': f'Şagird Test{i} qızı', 'class_id': cid, 'force': True}).json()
          for i in range(2)]
    return admin, cid, st


def test_guide_flow(world, monkeypatch):
    admin, cid, st = _setup(world)
    a = _student(st[0]['portal_code'], st[0]['initial_pin'])
    b = _student(st[1]['portal_code'], st[1]['initial_pin'])
    assert a.get('/api/auth/me').json()['guide_due'] is True
    assert a.get('/api/portal/me').json()['guide_due'] is True
    assert a.post('/api/portal/guide-seen').json()['ok'] is True
    assert a.get('/api/auth/me').json()['guide_due'] is False
    assert a.get('/api/portal/me').json()['guide_due'] is False
    assert b.get('/api/auth/me').json()['guide_due'] is True          # başqa şagirdin bayrağı dəyişmir
    rows = {r['id']: r for r in admin.get(f'/api/students?class_id={cid}').json()}
    assert rows[st[0]['id']]['guide_seen'] is True and rows[st[1]['id']]['guide_seen'] is False
    monkeypatch.setattr('app.api.auth.GUIDE_VERSION', 2)               # video yenilənib – yenidən göstərilir
    assert a.get('/api/auth/me').json()['guide_due'] is True
    a.__exit__(None, None, None)
    b.__exit__(None, None, None)


def test_guide_staff(world):
    as_, _ = world
    assert as_('ilqar').post('/api/portal/guide-seen').status_code == 403
    assert as_('ilqar').get('/api/auth/me').json()['guide_due'] is False
    assert as_('admin').get('/api/auth/me').json()['guide_due'] is False


def test_single_migration_head():
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    cfg = Config('alembic.ini')
    cfg.set_main_option('script_location', 'migrations')
    assert len(ScriptDirectory.from_config(cfg).get_heads()) == 1
