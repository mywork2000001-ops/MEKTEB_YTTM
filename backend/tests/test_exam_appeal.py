"""Sualın bank ünvanı və apelyasiya (docs/tasks/ksq-bsq-elave-ve-iki-netice.md, mərhələ 4)."""
import datetime as dt
import json

from app.api.exam_scans import apply
from app.models import AuditLog, BankFile, BankQuestion, Exam, ExamAppeal, ExamScan, ExamScore, ExamVariant, now
from .test_api_portal import student_client
from .test_ksq_scan import _graded


def _setup(world, monkeypatch):
    """İki şagirdin kartı skan olunub; a və b-nin 1-ci sualı EYNİ bank sualıdır və ikisi də 'X' yazıb; c-nin sualı başqadır."""
    admin, ta, e, pr, st, keys = _graded(world, monkeypatch)
    _, S = world
    with S() as db:
        scanned = [s.student_id for s in db.query(ExamScan).filter_by(exam_id=e['id'], source='paper').order_by(ExamScan.id)]
        vs = {v.student_id: v for v in db.query(ExamVariant).filter_by(exam_id=e['id'])}
        a, b = scanned
        c = next(i for i in vs if i not in scanned)
        q1 = next(q for q in vs[a].questions if q['slot'] == 1)
        assert q1.get('bank_id')
        vs[b].questions = [q1 if q['slot'] == 1 else q for q in vs[b].questions]
        db.add(ExamScan(exam_id=e['id'], student_id=c, code=vs[c].code, source='paper', status='pending', history=[]))
        db.flush()
        for sid in (a, b, c):
            sc = db.query(ExamScan).filter_by(exam_id=e['id'], student_id=sid, source='paper').one()
            sc.reading = [{'slot': 1, 'value': 'X', 'confidence': 1.0}]
            sc.read_by = 'import'
            apply(db, db.get(Exam, e['id']), sc)
        db.commit()
        assert q1['bank_id'] != next(q for q in vs[c].questions if q['slot'] == 1).get('bank_id')
    who = {x['id']: x for x in st}
    return admin, ta, e, pr, who, a, b, c, q1['bank_id'], S


def _pts(S, eid, sid, source='paper'):
    with S() as db:
        return db.query(ExamScan).filter_by(exam_id=eid, student_id=sid, source=source).one().points


def test_ref_frozen_teacher_only_and_hidden_from_students(world, monkeypatch):
    admin, ta, e, pr, who, a, b, c, bid, S = _setup(world, monkeypatch)
    with S() as db:
        v = db.get(ExamVariant, (e['id'], a))
        q = next(x for x in v.questions if x['slot'] == 1)
        assert q['ref']['bank_id'] == bid and '№' in q['ref']['text'] and f'B{bid}' in q['ref']['text']
        frozen = q['ref']['text']
        bq = db.get(BankQuestion, bid)
        db.get(BankFile, bq.file_id).label = 'Başqa ad'                 # bank sonra dəyişdi – variantda köhnə ünvan qalır
        db.commit()
    vs = admin.get(f'/api/exams/{ta}/{e["id"]}/variants').json()['variants']
    assert next(x for x in vs if x['student_id'] == a)['questions'][0]['ref']['text'] == frozen
    # köhnə variant (ref yoxdur): oxuyanda hesablanır
    with S() as db:
        v = db.get(ExamVariant, (e['id'], c))
        v.questions = [{k: x for k, x in q.items() if k != 'ref'} for q in v.questions]
        db.commit()
    vs = admin.get(f'/api/exams/{ta}/{e["id"]}/variants').json()['variants']
    assert '№' in next(x for x in vs if x['student_id'] == c)['questions'][0]['ref']['text']
    # çap: ref yalnız müəllim açarında; şagird vərəqində yoxdur
    pr2 = admin.get(f'/api/exams/{ta}/{e["id"]}/variants/print').json()
    assert 'ref' not in json.dumps(pr2['sheets']) and '№' not in json.dumps(pr2['sheets'])
    assert all('topic' not in q for sh in pr2['sheets'] for q in sh['questions'])   # altmövzu şagird vərəqində yoxdur
    assert all(a_['ref'] for k in pr2['key'] for a_ in k['answers'])
    # şagirdə gedən onlayn test: ref yoxdur
    from app.api.ksq_online import _questions
    with S() as db:
        assert all('ref' not in q and 'topic' not in q for q in _questions(db.get(ExamVariant, (e['id'], a))))
    assert admin.post(f'/api/ksq-online/{ta}/{e["id"]}', json={'student_ids': [a, b, c]}).status_code == 200
    with S() as db:
        from app.models import OnlineTask
        assert 'ref' not in json.dumps([t.questions for t in db.query(OnlineTask).filter_by(exam_id=e['id'])])


def test_appeal_rules(world, monkeypatch):
    admin, ta, e, pr, who, a, b, c, bid, S = _setup(world, monkeypatch)
    ca = student_client(who[a]['portal_code'], who[a]['initial_pin'])
    cb = student_client(who[b]['portal_code'], who[b]['initial_pin'])
    url = f'/api/portal/exams/{e["id"]}/appeals'
    body = {'slot': 1, 'source': 'paper', 'reason': 'Cavabım düzdür'}
    assert ca.post(url, json=body).status_code == 403                        # nəşrdən əvvəl
    assert admin.put(f'/api/exams/{ta}/{e["id"]}/publish', json={'published': True}).json()['appeal_until']
    r = ca.post(url, json=body)
    assert r.status_code == 200, r.text
    assert ca.post(url, json=body).status_code == 409                         # bir sual – bir apelyasiya
    assert ca.post(url, json={**body, 'slot': 999}).status_code == 404
    # başqasının apelyasiyasını silmək – 403
    assert cb.delete(f'/api/portal/exam-appeals/{r.json()["id"]}').status_code == 403
    # başqa sinfin şagirdi – 403
    cid = admin.post('/api/classes', json={'name': 'Y a'}).json()['id']
    o = admin.post('/api/students', json={'full_name': 'Başqa Sinif Şagirdi', 'class_id': cid}).json()
    assert student_client(o['portal_code'], o['initial_pin']).post(url, json=body).status_code == 403
    # müddət bitib – 400
    with S() as db:
        db.get(Exam, e['id']).appeal_until = now() - dt.timedelta(hours=1)
        db.commit()
    assert cb.post(url, json=body).status_code == 400
    # statusu şagird kartında görür
    card = ca.get(f'/api/portal/exams/{e["id"]}/card').json()
    assert [(x['slot'], x['status']) for x in card['appeals']] == [(1, 'open')]
    # müəllim: başqa müəllim 404; açıq sayı; geri götürmə
    assert world[0]('yad').get(f'/api/exam-appeals/{ta}/{e["id"]}').status_code == 404
    assert admin.get('/api/exam-appeals/open-count').json() == {'open': 1}
    lst = admin.get(f'/api/exam-appeals/{ta}/{e["id"]}').json()
    ap = lst['appeals'][0]
    assert ap['bank_ref']['text'].count('№') == 1 and ap['question']['text'] and ap['scan_id'] and ap['bank']['needs_review'] is False
    assert admin.get(f'/api/exams/{ta}/{e["id"]}').json()['appeals_open'] == 1
    # rədd – cavab məcburi
    d = f'/api/exam-appeals/{ta}/{e["id"]}/{ap["id"]}'
    assert admin.put(d, json={'decision': 'reject'}).status_code == 400
    assert admin.put(d, json={'decision': 'reject', 'reply': 'Açar düzgündür'}).json()['status'] == 'rejected'
    assert _pts(S, e['id'], a) == 0
    assert ca.get(f'/api/portal/exams/{e["id"]}/card').json()['appeals'][0]['teacher_reply'] == 'Açar düzgündür'


def test_accept_single_and_apply_all(world, monkeypatch):
    admin, ta, e, pr, who, a, b, c, bid, S = _setup(world, monkeypatch)
    assert admin.put(f'/api/exams/{ta}/{e["id"]}/publish', json={'published': True}).status_code == 200
    ca = student_client(who[a]['portal_code'], who[a]['initial_pin'])
    ap_id = ca.post(f'/api/portal/exams/{e["id"]}/appeals', json={'slot': 1, 'source': 'paper', 'reason': 'Düzdür'}).json()['id']
    d = f'/api/exam-appeals/{ta}/{e["id"]}/{ap_id}'
    # b «əl ilə» seçilib – xəbərdarlıq gəlməlidir (apply_all-da)
    with S() as db:
        db.get(ExamScore, (e['id'], b)).chosen = 'manual'
        db.commit()
    # 1) tək qəbul: yalnız a düzəlir
    r = admin.put(d, json={'decision': 'accept', 'reply': 'Qəbul'}).json()
    assert r['status'] == 'accepted' and [x['student_id'] for x in r['changes']] == [a] and r['changes'][0]['new'] > 0
    assert _pts(S, e['id'], a) > 0 and _pts(S, e['id'], b) == 0
    with S() as db:
        sa = db.query(ExamScan).filter_by(exam_id=e['id'], student_id=a, source='paper').one()
        assert sa.marks[0] == 1 and sa.history[-1]['appeal'] == ap_id and sa.history[-1]['new_points'] == sa.points
        assert db.get(ExamScore, (e['id'], a)).points == sa.points             # jurnal balı yeniləndi
    # «Yenilə» qəbul olunmuş düzəlişi silmir
    assert admin.post(f'/api/exam-scans/{ta}/{e["id"]}/regrade').status_code == 200
    assert _pts(S, e['id'], a) > 0
    # 2) hamıya tətbiq et: eyni bank sualı + eyni cavab ('X') – b düzəlir, c (başqa sual) toxunulmaz
    r = admin.put(d, json={'decision': 'accept', 'apply_all': True}).json()
    assert sorted(x['student_id'] for x in r['changes']) == [b] and r['manual_students']
    assert _pts(S, e['id'], b) > 0 and _pts(S, e['id'], c) == 0
    with S() as db:
        assert db.get(BankQuestion, bid).needs_review is True
        assert db.get(ExamScore, (e['id'], b)).points == 0                       # «əl ilə» bal toxunulmaz
        assert db.query(AuditLog).filter_by(entity='exam_appeal', action='update').count() == 2
        assert db.query(AuditLog).filter_by(entity='exam_appeal', action='create').count() == 1
    # 3) rədd edəndə hamıya tətbiq geri alınır
    admin.put(d, json={'decision': 'reject', 'reply': 'Səhv idi'})
    assert _pts(S, e['id'], a) == 0 and _pts(S, e['id'], b) == 0
