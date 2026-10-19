"""Şagird hissəsi audit düzəlişləri (19.10.2026): gizli nəticə, giriş limiti, RU mesajlar, material mətn limiti, student_ids."""
import datetime as dt

from fastapi.testclient import TestClient

from app.main import app
from app.models import Exam, ExamScan, ExamScore, TeachingAssignment, User, now
from tests.test_api_materials import PDF, setup as mat_setup, student as mat_student
from tests.test_api_portal import mk_task, setup, student_client


def _exam(S, ta, no, scan, published=False):
    with S() as db:
        e = Exam(assignment_id=ta, kind='KSQ', no=no, semester=1, date=dt.date(2026, 9, 29), max_points=10,
                 items=[{'n': 1, 'points': 10, 'standard': '1.1'}],
                 results_published_at=now() if published else None)
        db.add(e)
        db.flush()
        db.commit()
        return e.id


def test_results_hidden_until_published(world):
    admin, ta, cid, st, ids = setup(world)
    _, S = world
    e_scan = _exam(S, ta, 1, True)
    e_hand = _exam(S, ta, 2, False)
    with S() as db:
        sid = st[0]['id']
        for eid in (e_scan, e_hand):
            db.add(ExamScore(exam_id=eid, student_id=sid, points=9, item_marks=[1]))
        db.add(ExamScan(exam_id=e_scan, student_id=sid, code='X', source='paper', status='graded', points=9, history=[]))
        db.commit()
    s = student_client(st[0]['portal_code'], st[0]['initial_pin'])

    def rows():
        sub = s.get('/api/portal/results').json()['subjects'][0]
        return {r['no']: r for r in sub['exams']}, sub
    r, sub = rows()
    h = r[1]
    assert h['hidden'] is True and h['points'] is None and h['pct'] is None and h['grade'] is None
    assert h['items'] == [] and h['weak_standards'] == [] and h['taken_on'] is None
    assert r[2]['hidden'] is False and r[2]['points'] == 9 and r[2]['grade'] is not None   # skansız (əl ilə) – əvvəlki kimi
    assert sub['semester_grades']['1'] is None                                            # gizli imtahan olan yarımil
    with S() as db:
        db.get(Exam, e_scan).results_published_at = now()
        db.commit()
    r, sub = rows()
    assert r[1]['hidden'] is False and r[1]['points'] == 9 and r[1]['items']


def test_login_ip_limit(world):
    c = TestClient(app)
    for _ in range(30):
        assert c.post('/api/auth/login', json={'login': f'yoxdur{_}', 'password': 'yanlis-1'}).status_code in (401, 429)
    assert c.post('/api/auth/login', json={'login': 'yeni', 'password': 'yanlis-2'}).status_code == 429
    assert c.post('/api/auth/login', json={'login': 'yeni', 'password': 'yeni-parol'}).status_code == 429   # düzgün parol da


def test_ru_student_start_message(world, clock=None):
    admin, ta, cid, st, ids = setup(world)
    _, S = world
    t = mk_task(admin, ta, ids, opens_at='2099-01-01T10:00:00Z', closes_at='2099-01-01T11:00:00Z').json()
    s = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    s.patch('/api/auth/prefs', json={'language': 'ru', 'theme': 'forest'})
    r = s.post(f'/api/portal/tasks/{t["id"]}/start')
    assert r.status_code == 409 and r.json()['detail'] == 'Задание ещё не открыто'
    s.patch('/api/auth/prefs', json={'language': 'en', 'theme': 'forest'})
    assert s.post(f'/api/portal/tasks/{t["id"]}/start').json()['detail'] == 'The task is not open yet'


def test_material_text_limit_and_no_student_ids(world, monkeypatch, tmp_path):
    c, ta, st = mat_setup(world, monkeypatch, tmp_path)
    m = c.post(f'/api/materials/{ta}', data={'kind': 'task', 'title': 'Ev işi', 'body': 'x'}, files={'file': ('a.pdf', PDF, 'application/pdf')})
    assert m.status_code == 200, m.text
    mid = m.json()['id']
    s = mat_student(st[0])
    r = s.post(f'/api/portal/materials/{mid}/submit', data={'text': 'a' * 5001})
    assert r.status_code == 400
    assert s.post(f'/api/portal/materials/{mid}/submit', data={'text': 'a' * 5000}).status_code == 200
    mats = s.get('/api/portal/materials').json()
    assert mats and all('student_ids' not in x for x in mats)
    assert 'student_ids' in c.get(f'/api/materials/{ta}').json()[0]


def test_class_avg_hidden_small_class(world):
    admin, ta, cid, st, ids = setup(world)          # 3 şagird
    s = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    an = s.get('/api/portal/analytics').json()['subjects'][0]
    assert an['class_avg_hidden'] is True and all(v is None for v in an['class_avg'].values())
