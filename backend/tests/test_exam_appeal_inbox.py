"""Apelyasiya: sualın surəti (snapshot), ümumi qutu (inbox) və sahiblik (docs/tasks/testler-seriya-apelyasiya-2026-10-24.md, B)."""
from app.models import ExamAppeal, ExamVariant
from .test_api_portal import student_client
from .test_exam_appeal import _setup


def test_snapshot_inbox_and_ownership(world, monkeypatch):
    admin, ta, e, pr, who, a, b, c, bid, S = _setup(world, monkeypatch)
    assert admin.put(f'/api/exams/{ta}/{e["id"]}/publish', json={'published': True}).status_code == 200
    ca = student_client(who[a]['portal_code'], who[a]['initial_pin'])
    ap_id = ca.post(f'/api/portal/exams/{e["id"]}/appeals', json={'slot': 1, 'source': 'paper', 'reason': 'Cavabım düzdür'}).json()['id']
    with S() as db:
        snap = db.get(ExamAppeal, ap_id).bank_ref['q']
        q = next(x for x in db.get(ExamVariant, (e['id'], a)).questions if x['slot'] == 1)
        assert snap['text'] == q['text'] and snap['options'] == q.get('options') and snap['key']
        assert db.get(ExamAppeal, ap_id).bank_ref.get('text')            # köhnə ünvan açarları yerindədir
    url = f'/api/exam-appeals/{ta}/{e["id"]}'
    ap = admin.get(url).json()['appeals'][0]
    assert ap['question_changed'] is False and 'q' not in (ap['bank_ref'] or {})
    # sual variantda dəyişdi -> xəbərdarlıq, şagirdin gördüyü (snapshot) göstərilir
    with S() as db:
        v = db.get(ExamVariant, (e['id'], a))
        v.questions = [{**x, 'text': 'YENİ MƏTN'} if x['slot'] == 1 else x for x in v.questions]
        db.commit()
    ap2 = admin.get(url).json()['appeals'][0]
    assert ap2['question_changed'] is True and ap2['question']['text'] == snap['text']
    # variant silindi -> sual və açar snapshot-dan gəlir
    with S() as db:
        db.delete(db.get(ExamVariant, (e['id'], a)))
        db.commit()
    ap3 = admin.get(url).json()['appeals'][0]
    assert ap3['question']['text'] == snap['text'] and ap3['key_now'] == snap['key'] and ap3['question_changed'] is False
    # köhnə apelyasiya (snapshot yoxdur, variant var): indiki kimi variantdan
    with S() as db:
        db.add(ExamAppeal(exam_id=e['id'], student_id=b, slot=1, source='paper', reason='köhnə', bank_ref={'text': 'X · Y'}))
        db.commit()
    lst = {x['student_id']: x for x in admin.get(url).json()['appeals']}
    assert lst[b]['question']['text'] and lst[b]['question_changed'] is False
    # inbox: open sayı = open-count; imtahan məlumatı
    ib = admin.get('/api/exam-appeals/inbox').json()
    assert ib['open'] == admin.get('/api/exam-appeals/open-count').json()['open'] == 2
    first = ib['appeals'][0]
    assert first['ta_id'] == ta and first['exam']['id'] == e['id'] and first['exam']['ta_id'] == ta and 'class_name' in first['exam'] and 'appeal_until' in first
    # qərardan sonra: open filtri azalır, all saxlayır; açıqlar əvvəl
    assert admin.put(f'{url}/{ap_id}', json={'decision': 'reject', 'reply': 'Açar düzgündür'}).status_code == 200
    assert admin.get('/api/exam-appeals/inbox').json()['open'] == 1
    assert [x['status'] for x in admin.get('/api/exam-appeals/inbox?status=all').json()['appeals']] == ['open', 'rejected']
    assert admin.get('/api/exam-appeals/inbox?status=zzz').status_code == 422
    # başqa müəllim başqasının apelyasiyasını görmür
    assert world[0]('yad').get('/api/exam-appeals/inbox?status=all').json() == {'open': 0, 'appeals': []}
