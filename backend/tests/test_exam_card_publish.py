"""Şagirdə cavab kartı: yalnız nəticə göndərildikdən sonra, yalnız öz kartı (docs/tasks/ksq-bsq-elave-ve-iki-netice.md, mərhələ 3)."""
from app.models import ExamScan
from .test_api_portal import student_client
from .test_ksq_scan import _graded


def _other_class_student(admin):
    cid = admin.post('/api/classes', json={'name': 'Y a'}).json()['id']
    return admin.post('/api/students', json={'full_name': 'Başqa Sinif Şagirdi', 'class_id': cid}).json()


def test_card_only_after_publish_and_only_own(world, monkeypatch):
    admin, ta, e, pr, st, keys = _graded(world, monkeypatch)
    _, S = world
    with S() as db:
        scanned = {s.student_id for s in db.query(ExamScan).filter_by(exam_id=e['id'])}
    s0 = next(x for x in st if x['id'] in scanned)
    s_noscan = next(x for x in st if x['id'] not in scanned)
    c = student_client(s0['portal_code'], s0['initial_pin'])
    url = f'/api/portal/exams/{e["id"]}/card'
    assert c.get(url).status_code == 403                                   # nəşrdən əvvəl – variant sualları sızmır
    assert 'questions' not in c.get('/api/portal/results').text
    # müəllim göndərir; başqa müəllim edə bilməz
    assert world[0]('yad').put(f'/api/exams/{ta}/{e["id"]}/publish', json={'published': True}).status_code == 404
    r = admin.put(f'/api/exams/{ta}/{e["id"]}/publish', json={'published': True})
    assert r.status_code == 200 and r.json()['results_published_at']
    card = c.get(url).json()
    assert len(card['questions']) == len(pr['sheets'][0]['questions']) and card['questions'][0]['text']
    assert card['sources']['paper']['points'] == 0 and all(a['ok'] is False for a in card['sources']['paper']['answers'].values())
    assert card['final']['points'] == 0 and card['code']
    # variantı olub skanı olmayan şagird – kart yoxdur; başqa sinfin şagirdi – 403
    c2 = student_client(s_noscan['portal_code'], s_noscan['initial_pin'])
    assert c2.get(url).status_code == 404
    other = _other_class_student(admin)
    c3 = student_client(other['portal_code'], other['initial_pin'])
    assert c3.get(url).status_code == 403
    # geri al – yenə bağlıdır
    assert admin.put(f'/api/exams/{ta}/{e["id"]}/publish', json={'published': False}).status_code == 200
    assert c.get(url).status_code == 403
    assert c.get('/api/portal/results').json()['subjects'][0]['exams'][0]['published'] is False


def test_teacher_cards_for_print(world, monkeypatch):
    admin, ta, e, pr, st, keys = _graded(world, monkeypatch)
    d = admin.get(f'/api/exams/{ta}/{e["id"]}/cards').json()
    assert len(d['cards']) == 2 and d['class_name'] and all(c['full_name'] and c['questions'] and c['final'] for c in d['cards'])
    assert world[0]('yad').get(f'/api/exams/{ta}/{e["id"]}/cards').status_code == 404
