"""Sualın bank ünvanı və apelyasiya (docs/tasks/ksq-bsq-elave-ve-iki-netice.md, mərhələ 4)."""
import datetime as dt
import json

from app.api.exam_scans import apply
from app.models import AuditLog, BankFile, BankQuestion, Exam, ExamAppeal, ExamScan, ExamScore, ExamVariant, User, now
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
    assert admin.get('/api/exam-appeals/open-count').json() == {'open': 1, 'first': {'ta_id': ta, 'exam_id': e['id']}}   # nişan birbaşa apelyasiyaya aparır
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
    # bank ekranı: «yoxlanmalı» işarəsi, süzgəc, səbəb (qəbul şərhi), konkret sual (?id), «yoxlandı»
    only = admin.get('/api/bank/questions', params={'review': True}).json()
    assert [x['id'] for x in only['items']] == [bid] and only['items'][0]['needs_review'] and only['items'][0]['review_note']
    assert admin.get('/api/bank/questions', params={'id': bid}).json()['items'][0]['id'] == bid
    teacher = world[0]('ilqar')
    assert teacher.post(f'/api/bank/questions/{bid}/reviewed').status_code == 403           # redaktə qaydası: yalnız admin
    assert admin.post(f'/api/bank/questions/{bid}/reviewed').json()['needs_review'] is False
    assert admin.post('/api/bank/questions/99999999/reviewed').status_code == 404
    assert admin.get('/api/bank/questions', params={'review': True}).json()['items'] == []
    with S() as db:
        assert db.get(BankQuestion, bid).needs_review is False
        assert db.query(AuditLog).filter_by(entity='bank_question', action='update').count() == 1
        db.get(BankQuestion, bid).needs_review = True
        db.commit()
    # 3) rədd edəndə hamıya tətbiq geri alınır
    admin.put(d, json={'decision': 'reject', 'reply': 'Səhv idi'})
    assert _pts(S, e['id'], a) == 0 and _pts(S, e['id'], b) == 0


def _appeal(admin, ta, e, who, a, S, slot=1):
    admin.put(f'/api/exams/{ta}/{e["id"]}/publish', json={'published': True})
    ca = student_client(who[a]['portal_code'], who[a]['initial_pin'])
    ap = ca.post(f'/api/portal/exams/{e["id"]}/appeals', json={'slot': slot, 'source': 'paper', 'reason': 'Düzdür'}).json()['id']
    return f'/api/exam-appeals/{ta}/{e["id"]}/{ap}/fix', ap


def test_fix_key_all_same_bank_and_reply(world, monkeypatch):
    admin, ta, e, pr, who, a, b, c, bid, S = _setup(world, monkeypatch)
    with S() as db:
        q = next(x for x in db.get(ExamVariant, (e['id'], a)).questions if x['slot'] == 1)
        assert q['kind'] == 'mcq'
        new = (q['correct'] + 1) % len(q['options'])                 # şagirdlər bu variantı seçib – açar səhv idi
        for sid in (a, b):
            sc = db.query(ExamScan).filter_by(exam_id=e['id'], student_id=sid, source='paper').one()
            sc.reading = [{'slot': 1, 'value': 'ABCDE'[new], 'confidence': 1.0}]
            apply(db, db.get(Exam, e['id']), sc)
        db.get(BankQuestion, bid).needs_review = True
        db.commit()
    url, ap = _appeal(admin, ta, e, who, a, S)
    r = admin.post(url, json={'kind': 'key', 'correct': new, 'all_same': True, 'bank': True})
    assert r.status_code == 200, r.text
    r = r.json()
    assert r['status'] == 'accepted' and not r['still_wrong'] and 'Açar səhv' in r['reply']
    assert sorted(x['student_id'] for x in r['changes']) == [a, b]                # başqa variantdakı b də düzəldi, c yox
    assert _pts(S, e['id'], a) > 0 and _pts(S, e['id'], b) > 0 and _pts(S, e['id'], c) == 0
    with S() as db:
        bq = db.get(BankQuestion, bid)
        assert bq.correct == new and bq.needs_review is False
        assert db.query(AuditLog).filter_by(entity='exam_appeal', action='update').count() == 1
        assert db.get(ExamAppeal, ap).apply_all is True


def test_fix_reading_only_that_student(world, monkeypatch):
    admin, ta, e, pr, who, a, b, c, bid, S = _setup(world, monkeypatch)
    url, ap = _appeal(admin, ta, e, who, a, S)
    with S() as db:
        q = next(x for x in db.get(ExamVariant, (e['id'], a)).questions if x['slot'] == 1)
        val = 'ABCDE'[q['correct']] if q['kind'] == 'mcq' else str(q['answer']).split('|')[0]
    r = admin.post(url, json={'kind': 'reading', 'value': val}).json()
    assert r['status'] == 'accepted' and 'Kartınız' in r['reply'] and [x['student_id'] for x in r['changes']] == [a]
    assert _pts(S, e['id'], a) > 0 and _pts(S, e['id'], b) == 0


def test_fix_reading_still_wrong_rejects(world, monkeypatch):
    admin, ta, e, pr, who, a, b, c, bid, S = _setup(world, monkeypatch)
    url, ap = _appeal(admin, ta, e, who, a, S)
    r = admin.post(url, json={'kind': 'reading', 'value': 'Z'}).json()
    assert r['still_wrong'] is True and r['status'] == 'rejected' and r['reply']


def test_fix_annul_and_other_teacher_404(world, monkeypatch):
    admin, ta, e, pr, who, a, b, c, bid, S = _setup(world, monkeypatch)
    url, ap = _appeal(admin, ta, e, who, a, S)
    assert world[0]('yad').post(url, json={'kind': 'annul'}).status_code == 404
    r = admin.post(url, json={'kind': 'annul'})
    assert r.status_code == 200, r.text
    assert r.json()['status'] == 'accepted' and 'ləğv' in r.json()['reply']
    with S() as db:
        assert db.get(Exam, e['id']).items[0].get('annulled') is True


def test_fix_reply_language(world, monkeypatch):
    admin, ta, e, pr, who, a, b, c, bid, S = _setup(world, monkeypatch)
    url, ap = _appeal(admin, ta, e, who, a, S)
    with S() as db:
        from app.models import Student
        db.get(User, db.get(Student, a).user_id).language = 'ru'
        db.commit()
    r = admin.post(url, json={'kind': 'annul'}).json()
    assert 'аннулирован' in r['reply']
    lst = admin.get(f'/api/exam-appeals/{ta}/{e["id"]}').json()['appeals'][0]
    assert 'Ключ' in lst['fix_replies']['key'] and set(lst['fix_replies']) == {'key', 'reading', 'annul', 'wrong'}
