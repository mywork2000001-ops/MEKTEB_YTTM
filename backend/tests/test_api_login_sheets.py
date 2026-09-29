"""Giriş vərəqələri (bütün siniflər), şagirdin ID-sinin və PIN-inin redaktəsi."""
from fastapi.testclient import TestClient

from app.main import app
from app.models import Student


def login(code, pin):
    c = TestClient(app)
    c.__enter__()
    return c, c.post('/api/auth/login', json={'login': code, 'password': pin}).status_code


def test_all_login_sheets_fill_only_unknown_pins(world):
    as_, S = world
    a = as_('admin')
    x = a.post('/api/classes', json={'name': 'X e'}).json()['id']
    y = a.post('/api/classes', json={'name': 'X c'}).json()['id']
    s1 = a.post('/api/students', json={'full_name': 'Birinci Şagird qızı', 'class_id': x}).json()
    s2 = a.post('/api/students', json={'full_name': 'İkinci Şagird oğlu', 'class_id': x}).json()
    s3 = a.post('/api/students', json={'full_name': 'Üçüncü Şagird qızı', 'class_id': y}).json()
    # s1 PIN-ini özü dəyişir (bilir); s2 – ilkin PIN itib (köhnə idxal kimi), heç daxil olmayıb; s3 – ilkin PIN var
    c1, st = login(s1['portal_code'], s1['initial_pin'])
    assert st == 200 and c1.post('/api/auth/password', json={'old': s1['initial_pin'], 'new': '4321'}).status_code == 200
    with S() as db:
        db.get(Student, s2['id']).initial_pin = None
        db.commit()
    r = a.post('/api/students/login-sheets').json()
    assert [c['class_name'] for c in r['classes']] == ['X c', 'X e'] and r['new_pins'] == 1
    rows = {s['portal_code']: s['pin'] for c in r['classes'] for s in c['students']}
    assert rows[s1['portal_code']] is None                          # özü dəyişib – toxunulmur
    assert rows[s3['portal_code']] == s3['initial_pin']
    new2 = rows[s2['portal_code']]
    assert new2 and login(s2['portal_code'], new2)[1] == 200         # yeni PIN işləyir
    assert login(s1['portal_code'], '4321')[1] == 200                # s1-in öz PIN-i qorunub
    assert a.post('/api/students/login-sheets').json()['new_pins'] == 0   # təkrar – yeni PIN yoxdur
    assert as_('yad').post('/api/students/login-sheets').json()['classes'] == []   # başqa məktəb


def test_edit_student_id_and_pin(world):
    as_, _ = world
    a = as_('admin')
    x = a.post('/api/classes', json={'name': 'X e'}).json()['id']
    s = a.post('/api/students', json={'full_name': 'Birinci Şagird qızı', 'class_id': x}).json()
    o = a.post('/api/students', json={'full_name': 'İkinci Şagird oğlu', 'class_id': x}).json()
    assert a.patch(f'/api/students/{s["id"]}', json={'portal_code': o['portal_code'].lower()}).status_code == 409
    assert a.patch(f'/api/students/{s["id"]}', json={'portal_code': 'ilqar'}).status_code == 409   # müəllimin login-i
    assert a.patch(f'/api/students/{s["id"]}', json={'portal_code': 'x e 1'}).status_code == 422
    r = a.patch(f'/api/students/{s["id"]}', json={'portal_code': 'xe-nigar'}).json()
    assert r['portal_code'] == 'XE-NIGAR'
    assert login(s['portal_code'], s['initial_pin'])[1] == 401      # köhnə kod işləmir
    assert login('XE-NIGAR', s['initial_pin'])[1] == 200
    assert a.post(f'/api/students/{s["id"]}/reset-pin', json={'pin': '12a4'}).status_code == 422
    assert a.post(f'/api/students/{s["id"]}/reset-pin', json={'pin': '2580'}).json()['pin'] == '2580'
    assert login('XE-NIGAR', '2580')[1] == 200
    rnd = a.post(f'/api/students/{s["id"]}/reset-pin').json()['pin']
    assert len(rnd) == 4 and login('XE-NIGAR', rnd)[1] == 200
    sheet = a.get(f'/api/students/by-class/{x}/login-sheet').json()['students']
    assert {z['portal_code']: z['pin'] for z in sheet}['XE-NIGAR'] == rnd
