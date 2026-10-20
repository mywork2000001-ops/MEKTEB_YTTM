"""Kağız KSQ/BSQ nəticə paketi: kartın skanı + öz testi (altmövzu və №) – docs/ksq-kagiz-netice-paketi-promtu.md §3."""
import datetime as dt
import json
import re

from app.models import ChatMessage, ExamDelivery, ExamScan, ExamVariant
from .test_api_portal import student_client
from .test_ksq_scan import _graded, ksq, photo


def _split(world, st, e):
    _, S = world
    with S() as db:
        scanned = {s.student_id for s in db.query(ExamScan).filter_by(exam_id=e['id'])}
    return next(x for x in st if x['id'] in scanned), next(x for x in st if x['id'] not in scanned)


def test_before_publish_image_and_reading_only(world, monkeypatch):
    admin, ta, e, pr, st, _ = _graded(world, monkeypatch)
    s0, _s1 = _split(world, st, e)
    c = student_client(s0['portal_code'], s0['initial_pin'])
    r = c.get(f'/api/portal/exams/{e["id"]}/package')
    assert r.status_code == 200, r.text
    p = r.json()
    assert p['published'] is False and p['total'] is None and p['scan']['scan_id'] and 'image' in p['scan']
    assert len(p['questions']) == len(pr['sheets'][0]['questions'])
    for q in p['questions']:
        assert 'my_answer' in q and 'n' in q
        for k in ('text', 'options', 'key', 'ok', 'earned', 'topic', 'topic_no', 'explanation', 'points'):
            assert k not in q, k                                         # açar, ✓/✗, altmövzu, №, hətta sual mətni sızmır
    assert 'Faiz' not in json.dumps(p, ensure_ascii=False)


def test_after_publish_topic_and_number_no_tech_ids(world, monkeypatch):
    admin, ta, e, pr, st, _ = _graded(world, monkeypatch)
    s0, _s1 = _split(world, st, e)
    assert admin.put(f'/api/exams/{ta}/{e["id"]}/publish', json={'published': True}).status_code == 200
    c = student_client(s0['portal_code'], s0['initial_pin'])
    p = c.get(f'/api/portal/exams/{e["id"]}/package').json()
    assert p['published'] is True and p['total']['max'] == 100 and p['total']['points'] == 0
    for q in p['questions']:
        assert q['topic'] and re.fullmatch(r'№\d+', q['topic_no']) and q['text'] and q['key'] != ''
        assert q['ok'] is False and 'my_answer' in q
    raw = json.dumps(p, ensure_ascii=False)
    assert not re.search(r'\bB\d+\b', raw) and 'file_id' not in raw and 'bank_id' not in raw and '"ref"' not in raw
    assert p['appeals'] == [] and p['appeal_until']


def test_not_mine_and_not_written_are_404(world, monkeypatch):
    admin, ta, e, pr, st, _ = _graded(world, monkeypatch)
    s0, s1 = _split(world, st, e)
    admin.put(f'/api/exams/{ta}/{e["id"]}/publish', json={'published': True})
    c1 = student_client(s1['portal_code'], s1['initial_pin'])
    assert c1.get(f'/api/portal/exams/{e["id"]}/package').status_code == 404          # yazmayan şagird
    cid = admin.post('/api/classes', json={'name': 'Y a'}).json()['id']
    o = admin.post('/api/students', json={'full_name': 'Başqa Sinif Şagirdi', 'class_id': cid}).json()
    c3 = student_client(o['portal_code'], o['initial_pin'])
    assert c3.get(f'/api/portal/exams/{e["id"]}/package').status_code == 404          # başqa sinif
    c0 = student_client(s0['portal_code'], s0['initial_pin'])
    _, S = world
    with S() as db:
        scan_id = db.query(ExamScan).filter_by(exam_id=e['id'], student_id=s0['id']).one().id
    assert c3.get(f'/api/portal/exam-card/{scan_id}/image').status_code == 404
    assert c1.get(f'/api/portal/exam-card/{scan_id}/image').status_code == 404
    assert c0.get(f'/api/portal/exams/{e["id"]}/package').status_code == 200
    assert world[0]('yad').get(f'/api/exams/{ta}/{e["id"]}/packages').status_code == 404       # başqa müəllim
    d = admin.get(f'/api/exams/{ta}/{e["id"]}/packages').json()
    assert len(d['packages']) == 2 and all(x['full_name'] and x['questions'][0]['topic_no'] for x in d['packages'])


def test_own_variant_text_is_shown(world, monkeypatch):
    """Hər şagirdə öz variantı (öz rəqəmləri də): paket həmin şagirdin dondurulmuş sual mətnindən qurulur."""
    admin, ta, e, pr, st, _ = _graded(world, monkeypatch)
    _, S = world
    with S() as db:
        vs = {v.student_id: v for v in db.query(ExamVariant).filter_by(exam_id=e['id'])}
        scanned = sorted(s.student_id for s in db.query(ExamScan).filter_by(exam_id=e['id']))
        for i, sid in enumerate(scanned):
            qs = [dict(q) for q in vs[sid].questions]
            qs[0]['text'] = {'az': f'$x^2 - {5 + i}x + {6 + i} = 0$ (öz rəqəmlərim {i})'}
            vs[sid].questions = qs
        db.commit()
    admin.put(f'/api/exams/{ta}/{e["id"]}/publish', json={'published': True})
    got = []
    for i, sid in enumerate(scanned):
        u = next(x for x in st if x['id'] == sid)
        p = student_client(u['portal_code'], u['initial_pin']).get(f'/api/portal/exams/{e["id"]}/package').json()
        got.append(p['questions'][0]['text']['az'])
        assert f'öz rəqəmlərim {i}' in got[-1]
    assert got[0] != got[1]


def test_republish_does_not_duplicate(world, monkeypatch):
    admin, ta, e, pr, st, _ = _graded(world, monkeypatch)
    _, S = world
    r1 = admin.put(f'/api/exams/{ta}/{e["id"]}/publish', json={'published': True}).json()
    assert r1['sent'] == 2
    with S() as db:
        n_msg, n_del = db.query(ChatMessage).count(), db.query(ExamDelivery).filter_by(exam_id=e['id']).count()
        assert n_del == 2 and n_msg == 2
    r2 = admin.put(f'/api/exams/{ta}/{e["id"]}/publish', json={'published': True}).json()
    assert r2['sent'] == 0
    admin.put(f'/api/exams/{ta}/{e["id"]}/publish', json={'published': False})
    admin.put(f'/api/exams/{ta}/{e["id"]}/publish', json={'published': True})
    with S() as db:
        assert db.query(ChatMessage).count() == n_msg and db.query(ExamDelivery).filter_by(exam_id=e['id']).count() == 2
    s0, _ = _split(world, st, e)
    c = student_client(s0['portal_code'], s0['initial_pin'])
    notes = [n for n in c.get('/api/portal/notifications').json() if n['key'] == f'pkg-{e["id"]}']
    assert len(notes) == 1 and notes[0]['link'] == f'/results?pkg={e["id"]}'
    # müəllim ekranı: göndərildi → şagird açdı → baxıb
    assert admin.get(f'/api/exams/{ta}/{e["id"]}/delivery').json()[str(s0['id'])]['status'] == 'sent'
    assert c.get(f'/api/portal/exams/{e["id"]}/package').status_code == 200
    d = admin.get(f'/api/exams/{ta}/{e["id"]}/delivery').json()
    assert d[str(s0['id'])]['status'] == 'seen' and sorted(v['status'] for v in d.values()).count('not_sent') == len(d) - 2
    admin.put(f'/api/exams/{ta}/{e["id"]}/publish', json={'published': False})
    assert all(v['status'] == 'not_sent' for v in admin.get(f'/api/exams/{ta}/{e["id"]}/delivery').json().values())


def _upload_fake(world, monkeypatch, admin, ta, e, pr):
    from app.domain import ksq_reader as R
    monkeypatch.setattr(R, 'call', lambda api_key, model, jpeg, slots, only=None, text=None: [{'slot': s['slot'], 'value': '', 'confidence': 0.99} for s in slots])
    monkeypatch.setattr(R, 'key_pool', lambda db, tid: [{'provider': 'anthropic', 'key': 'sk-ant-test', 'model': R.MODEL}])
    for sh in pr['sheets'][:2]:
        admin.post(f'/api/exam-scans/{ta}/{e["id"]}/upload', files=[('files', ('p.jpg', photo([sh['qr']]), 'image/jpeg'))])


def test_send_on_scan_per_student_and_guard(world, monkeypatch):
    from . import test_api_portal as P
    orig, box = P.setup, {}
    monkeypatch.setattr(P, 'setup', lambda w: box.setdefault('r', orig(w)))
    admin, ta, e, pr = ksq(world)
    st = box['r'][3]
    _, S = world
    body = {'kind': 'KSQ', 'no': 1, 'semester': 1, 'date': e['date'], 'max_points': 20, 'send_on_scan': True}
    # başqa sinifdə eyni imtahan hələ keçirilməyib (gələcək tarixli) → 409
    cid2 = admin.post('/api/classes', json={'name': 'X f'}).json()['id']
    ta2 = admin.post(f'/api/classes/{cid2}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 2, 'slots': {'1': [1, 5]}}).json()['mine']['ta_id']
    from app.models import Exam
    with S() as db:
        o = Exam(assignment_id=ta2, kind='KSQ', no=1, semester=1, date=dt.date(2099, 1, 1), max_points=20)
        db.add(o)
        db.commit()
        oid = o.id
    r = admin.patch(f'/api/exams/{ta}/{e["id"]}', json=body)
    assert r.status_code == 409, r.text
    with S() as db:
        db.get(Exam, oid).date = dt.date(2020, 1, 1)                      # başqa sinif artıq yazıb
        db.commit()
    r = admin.patch(f'/api/exams/{ta}/{e["id"]}', json=body)
    assert r.status_code == 200 and r.json()['send_on_scan'] is True
    _upload_fake(world, monkeypatch, admin, ta, e, pr)
    s0, s1 = _split(world, st, e)
    c = student_client(s0['portal_code'], s0['initial_pin'])
    p = c.get(f'/api/portal/exams/{e["id"]}/package')
    assert p.status_code == 200 and p.json()['published'] is True and p.json()['questions'][0]['key'] != ''
    assert p.json()['questions'][0]['topic_no']
    with S() as db:
        assert db.get(Exam, e['id']).results_published_at is None                 # ümumi göndəriş yoxdur
        assert {d.student_id for d in db.query(ExamDelivery).filter_by(exam_id=e['id'])} == {x.student_id for x in db.query(ExamScan).filter_by(exam_id=e['id'])}
        assert db.query(ChatMessage).count() == 2
    assert student_client(s1['portal_code'], s1['initial_pin']).get(f'/api/portal/exams/{e["id"]}/package').status_code == 404
    assert any(n['key'] == f'pkg-{e["id"]}' for n in c.get('/api/portal/notifications').json())
    # rejimi söndürəndə paket yenidən bağlanır
    admin.patch(f'/api/exams/{ta}/{e["id"]}', json={**body, 'send_on_scan': False})
    assert c.get(f'/api/portal/exams/{e["id"]}/package').json()['published'] is False
