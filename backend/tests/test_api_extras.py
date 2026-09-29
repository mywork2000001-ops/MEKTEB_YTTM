"""Qeydiyyat linki, ehtiyat nüsxə və geri yükləmə, təhlükəsizlik başlıqları, zəif parol xəbərdarlığı."""
import datetime as dt
import json

from fastapi.testclient import TestClient

from app.main import app


def mk(world):
    as_, S = world
    c = as_('admin')
    cid = c.post('/api/classes', json={'name': 'X e'}).json()['id']
    c.post(f'/api/classes/{cid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 1, 'slots': {'0': [1]}})
    return c, cid, S


def test_self_registration_link(world):
    c, cid, _ = mk(world)
    c.post('/api/students', json={'full_name': 'Əvvəlki Şagird Test oğlu', 'class_id': cid})      # XE-001
    link = c.post(f'/api/classes/{cid}/invites', json={'days': 3, 'max_uses': 2}).json()
    anon = TestClient(app)
    info = anon.get(f"/api/join/{link['token']}").json()
    assert info['class_name'] == 'X e'
    body = {'full_name': 'Əliyeva Aysel Rəşad qızı', 'birth_date': '2011-03-05'}
    r = anon.post(f"/api/join/{link['token']}", json=body).json()
    assert r['portal_code'] == 'XE-002' and len(r['pin']) == 4                                   # növbəti nömrə
    assert anon.post(f"/api/join/{link['token']}", json=body).status_code == 409                # təkrar
    assert anon.post(f"/api/join/{link['token']}", json={**body, 'full_name': 'Təkad'}).status_code in (400, 422)
    # yalnız ad + soyad, doğum tarixi yox → dərhal daxil olur
    with TestClient(app) as kid:
        r2 = kid.post(f"/api/join/{link['token']}", json={'full_name': 'Məmmədov Tural'})
        assert r2.status_code == 200 and r2.json()['logged_in'] and kid.get('/api/auth/me').json()['role'] == 'student'
    assert anon.post(f"/api/join/{link['token']}", json={**body, 'pinkod': 'x'}).status_code == 422   # rəsmi İD qəbul edilmir
    with TestClient(app) as st:
        assert st.post('/api/auth/login', json={'login': 'xe-002', 'password': r['pin']}).status_code == 200
    lst = c.get(f'/api/classes/{cid}/invites').json()
    assert lst[0]['uses'] == 2 and lst[0]['registered'][-1] == 'Əliyeva Aysel Rəşad qızı'
    c.post(f"/api/invites/{link['id']}/revoke")
    assert anon.get(f"/api/join/{link['token']}").status_code == 410
    assert anon.get('/api/join/yanlis-token').status_code == 410


def test_backup_and_restore(world, tmp_path):
    c, cid, _ = mk(world)
    c.post('/api/students', json={'full_name': 'Ehtiyat Şagird Test oğlu', 'class_id': cid, 'score_math': 55.5})
    r = c.get('/api/admin/backup')
    assert r.status_code == 200 and 'attachment' in r.headers['content-disposition']
    data = r.json()
    assert data['format'] == 'muellim-komekcisi-backup' and len(data['tables']['students']) == 1
    f = tmp_path / 'b.json'
    f.write_text(json.dumps(data), encoding='utf-8')
    from sqlalchemy import create_engine, text
    from app.db import Base
    from tools.restore_backup import restore
    eng = create_engine(f'sqlite:///{tmp_path}/new.db')
    Base.metadata.create_all(eng)
    counts = restore(str(f), eng)
    assert counts['students'] == 1
    with eng.connect() as conn:
        assert conn.execute(text('select score_math from students')).scalar() == 55.5


def test_security_headers_and_weak_password(world):
    as_, _ = world
    with TestClient(app) as c:
        r = c.post('/api/auth/login', json={'login': 'admin', 'password': 'admin-parol'})
        assert r.json()['weak_password'] is False
        h = c.get('/api/auth/me').headers
        assert h['x-frame-options'] == 'DENY' and h['x-content-type-options'] == 'nosniff'
        assert "frame-ancestors 'none'" in h['content-security-policy'] and h['cache-control'] == 'no-store'
    assert as_('ilqar').get('/api/admin/backup').status_code == 403
    from app.models import User
    from app.security import hash_password
    _, S = world
    with S() as db:
        db.query(User).filter_by(login='ilqar').one().password_hash = hash_password('1234')
        db.commit()
    with TestClient(app) as c:
        assert c.post('/api/auth/login', json={'login': 'ilqar', 'password': '1234'}).json()['weak_password'] is True
