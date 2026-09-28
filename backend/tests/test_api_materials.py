"""Materiallar: PDF tapşırıq, video dərs, şagird cavabı, gecikmə, qiymət, məxfilik."""
import datetime as dt

from fastapi.testclient import TestClient

from app.main import app

PDF = b'%PDF-1.4 test'


def setup(world, monkeypatch, tmp_path):
    monkeypatch.setattr('app.api.chat.upload_dir', lambda: tmp_path)
    as_, _ = world
    c = as_('admin')
    cid = c.post('/api/classes', json={'name': 'X e'}).json()['id']
    c.post(f'/api/classes/{cid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 1, 'slots': {'0': [1]}})
    st = [c.post('/api/students', json={'full_name': f'Şagird Mat{i} oğlu', 'class_id': cid}).json() for i in range(2)]
    ta = next(l['id'] for l in c.get('/api/my/lessons').json())
    return c, ta, st


def student(s):
    c = TestClient(app)
    c.__enter__()
    assert c.post('/api/auth/login', json={'login': s['portal_code'], 'password': s['initial_pin']}).status_code == 200
    return c


def test_pdf_task_and_video_flow(world, monkeypatch, tmp_path):
    c, ta, st = setup(world, monkeypatch, tmp_path)
    past = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)).isoformat()
    r = c.post(f'/api/materials/{ta}', data={'kind': 'task', 'title': 'Ev işi – tənliklər', 'due_at': past},
               files={'file': ('tapsiriq.pdf', PDF, 'application/pdf')})
    assert r.status_code == 200 and r.json()['file']['name'] == 'tapsiriq.pdf'
    task = r.json()['id']
    assert c.post(f'/api/materials/{ta}', data={'kind': 'video', 'title': 'Dərs videosu', 'url': 'javascript:alert(1)'}).status_code == 400
    assert c.post(f'/api/materials/{ta}', data={'kind': 'video', 'title': 'Dərs videosu', 'url': 'https://youtu.be/abc'}).status_code == 200
    s = student(st[0])
    mine = s.get('/api/portal/materials').json()
    assert {m['kind'] for m in mine} == {'task', 'video'}
    t = next(m for m in mine if m['kind'] == 'task')
    assert s.get(t['file']['url']).content == PDF                                   # şagird faylı endirir
    assert s.post(f'/api/portal/materials/{task}/submit', data={}).status_code == 400
    r = s.post(f'/api/portal/materials/{task}/submit', data={'text': 'x=3'}, files={'file': ('cavab.jpg', b'\xff\xd8jpg', 'image/jpeg')})
    assert r.status_code == 200 and r.json()['late'] is True                          # son vaxt keçib
    subs = c.get(f'/api/materials/{ta}/{task}/submissions').json()['rows']
    got = next(x for x in subs if x['student_id'] == st[0]['id'])['submission']
    assert got['text'] == 'x=3' and c.get(got['file']['url']).content == b'\xff\xd8jpg'
    c.put(f'/api/materials/{ta}/submissions/{got["id"]}', json={'grade': 5, 'comment': 'Əla'})
    t = next(m for m in s.get('/api/portal/materials').json() if m['kind'] == 'task')
    assert t['submission']['grade'] == 5 and t['submission']['comment'] == 'Əla'
    assert s.post(f'/api/portal/materials/{task}/submit', data={'text': 'dəyiş'}).status_code == 409
    # başqa şagird digərinin cavab faylını görə bilmir
    s2 = student(st[1])
    assert s2.get(got['file']['url']).status_code == 404


def test_material_for_selected_students(world, monkeypatch, tmp_path):
    c, ta, st = setup(world, monkeypatch, tmp_path)
    c.post(f'/api/materials/{ta}', data={'kind': 'note', 'title': 'Əlavə məşğələ', 'body': 'Cümə 15:00',
                                         'student_ids': str(st[1]['id'])})
    assert student(st[0]).get('/api/portal/materials').json() == []
    assert len(student(st[1]).get('/api/portal/materials').json()) == 1
