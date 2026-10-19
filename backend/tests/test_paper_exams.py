"""Yazılı (kağız) rejim: mövzu testi / sınaq / sərbəst yazılı iş (docs/yazili-sinaq-ve-skan-duymesi-promtu.md §A).
Exam(kind TEST|SINAQ|YI) + ExamVariant; mövcud kart/skan/apelyasiya axını dəyişmədən işləyir; nəticə jurnala yalnız seçilərsə düşür."""
import datetime as dt

from app.domain.ksq_scan import grade
from app.models import BankFile, BankQuestion, BankSource, Exam, OnlineTask, TestBatch

from .test_api_portal import as_topic, mk_task, setup
from .test_ksq_scan import photo


def _bank(S, n=60):
    """Plansız sərbəst iş üçün test faylı: n sual (yarısı test, yarısı açıq)."""
    with S() as db:
        db.add(BankSource(key='px', label='PX'))
        db.flush()
        f = BankFile(source_key='px', lesson='x/serbest.html', label='Sərbəst fayl', url='http://x', kind='movzu', question_count=n)
        db.add(f)
        db.flush()
        for i in range(n):
            kind = 'mcq' if i % 2 == 0 else 'open'
            db.add(BankQuestion(file_id=f.id, n=i + 1, kind=kind, text={'az': f'Sərbəst sual {i}'}, content_hash=f'sx{i}',
                                options=[{'az': '1'}, {'az': '2'}, {'az': '3'}] if kind == 'mcq' else None,
                                correct=i % 3 if kind == 'mcq' else None, answer=None if kind == 'mcq' else str(i),
                                diff_auto=['asan', 'orta', 'çətin'][i % 3]))
        db.commit()
        return f.id


def test_score_slot_grading():
    qs = [{'slot': 1, 'kind': 'mcq', 'correct': 0, 'points': 40}, {'slot': 2, 'kind': 'score', 'points': 40, 'answer': 'həll'},
          {'slot': 3, 'kind': 'open', 'answer': '5', 'points': 20}]
    g = grade(qs, [{'slot': 1, 'value': 'A', 'confidence': 1}, {'slot': 2, 'value': '3/4', 'confidence': 1},
                   {'slot': 3, 'value': '5', 'confidence': 1}])
    assert g['points'] == 90 and g['flagged'] == []
    g2 = grade(qs, [{'slot': 1, 'value': 'A', 'confidence': 1}, {'slot': 2, 'value': '0,5', 'confidence': 1}, {'slot': 3, 'value': '', 'confidence': 1}])
    assert g2['points'] == 60
    assert grade(qs, [{'slot': 1, 'value': 'A', 'confidence': 1}, {'slot': 2, 'value': '1', 'confidence': 1}, {'slot': 3, 'value': '5', 'confidence': 1}])['points'] == 100


def test_paper_from_topic_test_school_flow(world):
    admin, ta, cid, st, ids = setup(world)
    _, S = world
    t = mk_task(admin, ta, ids).json()
    as_topic(S, t["id"])
    with S() as db:                                           # üçüncü sual: kart xanasına sığmayan açıq cavab → müəllim balı (score)
        task = db.get(OnlineTask, t['id'])
        qs = [dict(q) for q in task.questions]
        qs.append({'bank_id': None, 'kind': 'open', 'text': {'az': 'İsbat edin'}, 'answer': 'uzun həll mətni burada', 'points': None})
        task.questions = qs
        db.commit()
    r = admin.post(f'/api/paper-exams/{ta}', json={'task_id': t['id'], 'date': '2026-10-05'})
    assert r.status_code == 200, r.text
    e = r.json()['exam']
    assert e['kind'] == 'TEST' and e['online_task_id'] == t['id'] and e['to_journal'] is False and e['max_points'] == 100
    # bir tapşırıq – bir yazılı imtahan
    assert admin.post(f'/api/paper-exams/{ta}', json={'task_id': t['id'], 'date': '2026-10-05'}).status_code == 409
    pr = admin.get(f'/api/exams/{ta}/{e["id"]}/variants/print').json()
    assert len(pr['sheets']) == 3 and all(len(s['questions']) == 4 for s in pr['sheets'])
    assert [q['kind'] for q in pr['sheets'][0]['questions']] == [q['kind'] for q in pr['sheets'][1]['questions']]   # hamıya eyni
    assert {q['kind'] for q in pr['sheets'][0]['questions']} == {'mcq', 'open', 'score'}
    assert abs(sum(q['points'] for q in pr['sheets'][0]['questions']) - 100) < 1e-6
    # KSQ/BSQ siyahısında və yarımil hesabında görünmür; yazılı siyahıda var
    assert admin.get(f'/api/exams/{ta}').json()['exams'] == []
    lst = admin.get(f'/api/paper-exams/{ta}').json()
    assert lst[0]['id'] == e['id'] and lst[0]['variants'] == 3 and lst[0]['scanned'] == 0
    # skan: ümumi düymə ilə; oxunuş idxalı (test A–E, açıq, müəllim balı)
    a = pr['sheets'][0]
    d = admin.post('/api/scans/any', files=[('files', ('p.jpg', photo([a['qr']]), 'image/jpeg'))]).json()
    assert d['found'][0]['exam_id'] == e['id']
    keys = {k['code']: k['answers'] for k in pr['key']}[a['code']]
    ans = [{'slot': k['slot'], 'value': k['value'], 'confidence': 0.99} for k in keys]
    ans[-1]['value'] = '1/2'                                    # score slotu: müəllim balı ½
    assert admin.post('/api/exam-scans/import', json=[{'scan_id': d['found'][0]['scan_id'], 'answers': ans}]).json()['graded'] == 1
    res = admin.get(f'/api/paper-exams/{ta}/{e["id"]}/results').json()
    row = next(x for x in res['rows'] if x['student_id'] == a['student_id'])
    last_pts = pr['sheets'][0]['questions'][-1]['points']
    assert abs(row['points'] - (100 - last_pts / 2)) < 0.01 and row['grade'] in (4, 5) and row['online_points'] is None
    # jurnalda görünmür (to_journal=False); seçilsə görünür
    up = admin.patch(f'/api/paper-exams/{ta}/{e["id"]}', json={'to_journal': True})
    assert up.status_code == 200 and up.json()['to_journal'] is True


def test_paper_from_sinaq_batch(world):
    admin, ta, cid, st, ids = setup(world)
    _, S = world
    t = mk_task(admin, ta, ids).json()
    with S() as db:
        b = TestBatch(kind='sinaq', title='DİM Sınaq 3', subject='Riyaziyyat', grade=10)
        db.add(b)
        db.flush()
        task = db.get(OnlineTask, t['id'])
        task.kind, task.batch_id = 'sinaq', b.id
        db.commit()
        bid = b.id
    e = admin.post(f'/api/paper-exams/{ta}', json={'task_id': t['id'], 'date': '2026-10-05', 'to_journal': True}).json()['exam']
    assert e['kind'] == 'SINAQ' and e['batch_id'] == bid and e['title'] == 'Test 1' and e['to_journal'] is True
    with S() as db:
        assert db.get(Exam, e['id']).kind == 'SINAQ'


def test_free_written_work_without_plan_different_and_same(world):
    admin, ta, cid, st, ids = setup(world)
    _, S = world
    fid = _bank(S)
    r = admin.post(f'/api/paper-exams/{ta}', json={'file_ids': [fid], 'n': 10, 'date': '2026-10-05', 'variant_mode': 'different', 'title': 'Yazılı iş 1'})
    assert r.status_code == 200, r.text
    e = r.json()['exam']
    assert e['kind'] == 'YI' and e['title'] == 'Yazılı iş 1'
    pr = admin.get(f'/api/exams/{ta}/{e["id"]}/variants/print').json()
    texts = [tuple(q['text'] for q in s['questions']) for s in pr['sheets']]
    assert len(set(texts)) == 3 and all(len(s['questions']) == 10 for s in pr['sheets'])      # hər şagirdə fərqli
    r2 = admin.post(f'/api/paper-exams/{ta}', json={'file_ids': [fid], 'n': 10, 'date': '2026-10-06', 'variant_mode': 'same'}).json()['exam']
    assert r2['kind'] == 'YI' and r2['no'] == e['no'] + 1
    pr2 = admin.get(f'/api/exams/{ta}/{r2["id"]}/variants/print').json()
    assert len({tuple(q['text'] for q in s['questions']) for s in pr2['sheets']}) == 1             # hamıya eyni
    # «eyni suallar, öz rəqəmləri» rejimi artıq var (tests/test_own_numbers_api.py); sadə mətnli suallar dəyişmir
    assert admin.post(f'/api/paper-exams/{ta}', json={'file_ids': [fid], 'n': 10, 'date': '2026-10-06', 'variant_mode': 'same_numbers'}).status_code == 200
    # çatışmazlıq – 409, bank faylı yoxdursa 400
    assert admin.post(f'/api/paper-exams/{ta}', json={'file_ids': [fid], 'n': 30, 'date': '2026-10-06', 'variant_mode': 'different'}).status_code in (200, 409)
    assert admin.post(f'/api/paper-exams/{ta}', json={'n': 10, 'date': '2026-10-06'}).status_code == 400
    # başqa müəllimin dərsi
    assert world[0]('ilqar').post(f'/api/paper-exams/{ta}', json={'file_ids': [fid], 'n': 10, 'date': '2026-10-06'}).status_code == 404
    # silmək: nəticə yoxdur → olar
    assert admin.delete(f'/api/paper-exams/{ta}/{r2["id"]}').status_code == 200
    left = [x['id'] for x in admin.get(f'/api/paper-exams/{ta}').json()]
    assert e['id'] in left and r2['id'] not in left


def test_private_workspace_paper_exam(world):
    as_, S = world
    fid = _bank(S)
    il = as_('ilqar')
    cid = il.post('/api/classes', json={'name': 'IX hazırlıq', 'kind': 'adi', 'private': True}).json()['id']
    il.post(f'/api/classes/{cid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 2, 'has_summative': False, 'slots': {'0': [7], '2': [7]}})
    for i in range(2):
        il.post('/api/students', json={'full_name': f'Fərdi Şagird{i} oğlu', 'class_id': cid})
    ta = il.get('/api/my/lessons').json()[0]['assignment_id'] if 'assignment_id' in il.get('/api/my/lessons').json()[0] else None
    if ta is None:
        from app.models import TeachingAssignment
        with S() as db:
            ta = db.query(TeachingAssignment).filter_by(class_id=cid).one().id
    r = il.post(f'/api/paper-exams/{ta}', json={'file_ids': [fid], 'n': 10, 'date': dt.date.today().isoformat(), 'variant_mode': 'same'})
    assert r.status_code == 200, r.text
    e = r.json()['exam']
    pr = il.get(f'/api/exams/{ta}/{e["id"]}/variants/print').json()
    assert len(pr['sheets']) == 2
    # fərdi məkanda ümumi skan düyməsi də görür
    assert il.get('/api/scans/any/summary').json()['waiting'] >= 1
