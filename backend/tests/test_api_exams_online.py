"""Sınaq imtahanları: bank təsnifatı, bir neçə sinfə sınaq, sınaq jurnalı (bal, cərimə, bərabər bal → eyni yer),
sinif və ümumi reytinq, açıq sualın əl ilə yoxlanması, məxfilik, kumulyativ reytinq, şagird portalı."""
import datetime as dt

from app.bank.classify import classify, grades_from_label
from app.models import OnlineTask, TeachingAssignment

from .test_api_portal import UTC, clock, setup, student_client  # noqa: F401 – clock fixture


def test_classify():
    assert classify('p007', 'Natural ədədlər') == {'kind': 'movzu', 'grades': [9], 'subject': 'Riyaziyyat'}
    assert classify('p012', 'ÜSİ-3')['kind'] == 'sinaq' and classify('p009', 'Variant 4')['grades'] == [11]
    assert classify('sinaqlar', '2026 · İTM — Buraxılış sınaq imtahanı BSİ-1 (VIII–IX sinif, 27.09.2026)') == \
        {'kind': 'sinaq', 'grades': [8, 9], 'subject': 'Riyaziyyat'}
    assert classify('sinaqlar', '2026 · OBM — Natural ədədlər (Variant A) (Natural ədədlər, 2026)')['kind'] == 'movzu'
    assert classify('sinaqlar', 'Leibniz Academy — Mövzu sınağı 5 (XI sinif, 08.02.2026)')['kind'] == 'sinaq'
    assert classify('p003', 'Kitab I — Yekun Testi')['kind'] == 'yekun'
    assert classify('p011', 'Fəsil 1 · Dərs 1 — İlkin yoxlama') == {'kind': 'diaqnostik', 'grades': [6], 'subject': 'Riyaziyyat'}
    assert grades_from_label('IX–X sinif') == [9, 10] and grades_from_label('9-cu sinif') == [9]


def _answer(st, task_id, by_text):
    c = student_client(st['portal_code'], st['initial_pin'])
    q = c.post(f'/api/portal/tasks/{task_id}/start').json()
    idx = {x['text']['az']: x['index'] for x in q['questions']}
    c.post(f'/api/portal/tasks/{task_id}/submit', json={'answers': {str(idx[k]): v for k, v in by_text.items()}})
    return c


ALL_OK = {'2+2=?': 1, 'x²=9, x>0': '3', '5·2=?': 0}


def test_online_exam_journal_rating_privacy(world, clock, monkeypatch):
    as_, S = world
    monkeypatch.setattr('app.api.exams_online.now', clock)
    admin, ta, cid, st, ids = setup(world)                                     # X e – admin, 3 şagird
    xc = admin.post('/api/classes', json={'name': 'X c'}).json()['id']
    admin.post(f'/api/classes/{xc}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 1, 'slots': {}})
    xs = [admin.post('/api/students', json={'full_name': f'X c Şagird{i} oğlu', 'class_id': xc}).json() for i in range(2)]
    xd = admin.post('/api/classes', json={'name': 'X d'}).json()['id']
    ilqar = as_('ilqar')
    ilqar.post(f'/api/classes/{xd}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 1, 'slots': {}})
    ds = [admin.post('/api/students', json={'full_name': 'X d Şagird oğlu', 'class_id': xd}).json()]
    with S() as db:
        ta_c = db.query(TeachingAssignment).filter_by(class_id=xc).one().id
        ta_d = db.query(TeachingAssignment).filter_by(class_id=xd).one().id
    # admin məktəbin bütün dərslərini, müəllim yalnız özününküləri görür
    assert {x['class_name'] for x in admin.get('/api/exams-online/targets').json()} >= {'X e', 'X c', 'X d'}
    assert [x['class_name'] for x in ilqar.get('/api/exams-online/targets').json()] == ['X d']

    clock.t = dt.datetime(2026, 9, 29, 10, 0, tzinfo=UTC)
    win = {'opens_at': '2026-09-29T11:00:00Z', 'closes_at': '2026-09-29T14:00:00Z'}
    body = {'title': 'Buraxılış sınağı 1', 'bank_ids': ids, 'penalty': 4,
            'targets': [{'ta_id': x, **win} for x in (ta, ta_c, ta_d)]}
    assert ilqar.post('/api/exams-online', json={**body, 'targets': [{'ta_id': ta, **win}]}).status_code == 404
    r = admin.post('/api/exams-online', json=body)
    assert r.status_code == 200 and r.json()['tasks'] == 3
    bid = r.json()['id']
    with S() as db:
        tid = {t.assignment_id: t.id for t in db.query(OnlineTask).filter_by(batch_id=bid)}
    assert ilqar.get(f'/api/tasks/{ta_d}').json()[0]['kind'] == 'sinaq'          # sinif müəllimi öz tapşırıqlarında görür

    clock.t = dt.datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
    s0 = _answer(st[0], tid[ta], ALL_OK)                                        # 3 düz → 3 bal
    _answer(st[1], tid[ta], {**ALL_OK, 'x²=9, x>0': '4'})                       # 2 düz, 1 səhv → 1.75
    _answer(xs[0], tid[ta_c], {'2+2=?': 1, '5·2=?': 0})                         # 2 düz, 1 boş → 2
    _answer(xs[1], tid[ta_c], {**ALL_OK, 'x²=9, x>0': 'üç'})                    # 1.75 (sonra əl ilə düz)
    _answer(ds[0], tid[ta_d], {'2+2=?': 1, 'x²=9, x>0': '1', '5·2=?': 1})        # 1 düz, 2 səhv → 0.5
    assert admin.post(f'/api/tasks/{ta}/{tid[ta]}/to-journal', json={}).status_code == 400   # formativ jurnala yox

    clock.t = dt.datetime(2026, 9, 29, 15, 0, tzinfo=UTC)
    res = admin.get(f'/api/exams-online/{bid}').json()
    assert res['access'] == 'full' and res['summary']['wrote'] == 5 and res['summary']['students'] == 6
    got = [(r['full_name'], r['points'], r['place_all'], r['place_class']) for r in res['rows'] if r['status'] == 'yazıb']
    assert got[0] == (st[0]['full_name'], 3.0, 1, 1) and got[1] == (xs[0]['full_name'], 2.0, 2, 1)
    assert {g[2] for g in got[2:4]} == {3} and got[4] == (ds[0]['full_name'], 0.5, 5, 1)    # bərabər bal – eyni yer
    x0 = next(r for r in res['rows'] if r['student_id'] == xs[0]['id'])
    assert (x0['correct'], x0['wrong'], x0['blank']) == (2, 0, 1)
    assert [(c['class_name'], c['place']) for c in res['classes']] == [('X e', 1), ('X c', 2), ('X d', 3)]
    assert next(r for r in res['rows'] if r['student_id'] == st[2]['id'])['status'] == 'yazmayıb'
    assert res['questions'][1]['pct'] == 20.0                                   # açıq sual: 1/5

    # açıq sualın əl ilə yoxlanması: «üç» düz sayılır → 3 bal, birinci yeri bölüşür
    det = admin.get(f'/api/exams-online/{bid}/attempt/{tid[ta_c]}/{xs[1]["id"]}').json()['items']
    assert det[1]['given'] == 'üç' and not det[1]['ok']
    assert admin.put(f'/api/exams-online/{bid}/attempt/{tid[ta_c]}/{xs[1]["id"]}', json={'index': 0, 'ok': False}).status_code == 400
    assert admin.put(f'/api/exams-online/{bid}/attempt/{tid[ta_c]}/{xs[1]["id"]}', json={'index': 1, 'ok': True}).json()['correct'] == 3
    res = admin.get(f'/api/exams-online/{bid}').json()
    assert next(r for r in res['rows'] if r['student_id'] == xs[1]['id'])['place_all'] == 1

    # başqa müəllim: yalnız öz sinfinin adları; başqa məktəb – 404; başqa sinfin cavabları – 404
    mine = ilqar.get(f'/api/exams-online/{bid}').json()
    assert mine['access'] == 'own' and {r['full_name'] for r in mine['rows'] if r['class_name'] != 'X d'} == {None}
    assert [r['full_name'] for r in mine['rows'] if r['class_name'] == 'X d'] == [ds[0]['full_name']]
    assert as_('yad').get(f'/api/exams-online/{bid}').status_code == 404
    assert ilqar.get(f'/api/exams-online/{bid}/attempt/{tid[ta]}/{st[0]["id"]}').status_code == 404
    assert [b['id'] for b in ilqar.get('/api/exams-online').json()] == [bid]

    # ikinci sınaq (yalnız X e): 2-ci şagird irəliləyir → kumulyativ reytinqdə dinamika
    clock.t = dt.datetime(2026, 10, 6, 10, 0, tzinfo=UTC)
    win2 = {'opens_at': '2026-10-06T11:00:00Z', 'closes_at': '2026-10-06T14:00:00Z'}
    b2 = admin.post('/api/exams-online', json={**body, 'title': 'Sınaq 2', 'penalty': 0,
                                                'targets': [{'ta_id': ta, **win2}]}).json()['id']
    with S() as db:
        t2 = db.query(OnlineTask).filter_by(batch_id=b2).one().id
    clock.t = dt.datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
    _answer(st[1], t2, ALL_OK)
    _answer(st[0], t2, {'2+2=?': 1})
    clock.t = dt.datetime(2026, 10, 6, 15, 0, tzinfo=UTC)
    rt = admin.get('/api/exams-online/rating', params={'subject': 'Riyaziyyat'}).json()
    assert len(rt['batches']) == 2
    r1 = next(r for r in rt['rows'] if r['student_id'] == st[1]['id'])
    assert r1['count'] == 2 and r1['delta'] == round(100 - 58.3, 1) and rt['improved'][0]['student_id'] == st[1]['id']
    assert all(r['class_name'] == 'X d' for r in ilqar.get('/api/exams-online/rating').json()['rows'])

    # şagird portalı: öz yeri və ümumi statistika, başqasının adı yoxdur
    me = s0.get('/api/portal/exams').json()
    first = next(x for x in me['items'] if x['batch_id'] == bid)
    assert (first['place_class'], first['class_count'], first['place_all'], first['all_count']) == (1, 2, 1, 5)
    assert first['max_pct'] == 100.0 and 'rows' not in first
    assert me['delta'] == round(33.3 - 100, 1)

    # formativ jurnal: sınaq keçirildiyi günün ayrıca sütunundadır, formativ ortaya daxil deyil; yekunda ayrıca
    monkeypatch.setattr('app.api.journal.today', lambda: dt.date(2026, 10, 7))
    g = admin.get(f'/api/journal/{ta}/grid', params={'month': '2026-09'}).json()
    ci = next(i for i, c in enumerate(g['columns']) if c.get('sinaq'))
    assert g['columns'][ci]['date'] == '2026-09-29' and g['exams'] == 1
    r0 = next(r for r in g['rows'] if r['student_id'] == st[0]['id'])
    assert r0['cells'][ci]['sinaq'] == '100%' and r0['avg'] is None and r0['exam_count'] == 1
    sm = admin.get(f'/api/journal/{ta}/summary').json()
    assert sm['exams'] == 2 and next(x for x in sm['students'] if x['student_id'] == st[1]['id'])['exam_count'] == 2
    assert next(x for x in admin.get(f'/api/exams/{ta}/semester/1').json()['students']
                if x['student_id'] == st[0]['id'])['exam_pct'] is not None

    # silmə: başqa müəllim yalnız öz sinfini silir; silinən sınaq tam gedir (şagirddə də)
    assert ilqar.delete(f'/api/exams-online/{bid}').json()['deleted'] == 1
    assert admin.get(f'/api/exams-online/{bid}').json()['summary']['students'] == 5
    assert admin.delete(f'/api/exams-online/{bid}').json()['deleted'] == 2
    assert admin.get(f'/api/exams-online/{bid}').status_code == 404
    assert all(x['id'] != bid for x in admin.get('/api/exams-online').json())
    assert all(x['batch_id'] != bid for x in s0.get('/api/portal/exams').json()['items'])
    with S() as db:
        assert db.query(OnlineTask).filter_by(batch_id=bid).count() == 0
    # «Onlayn tapşırıqlar»dan silinən sınaq da arxivə yox, tam silinir; boş qalan paket də gedir
    assert admin.post(f'/api/tasks/{ta}/{t2}/archive').json()['deleted'] is True
    assert admin.get(f'/api/exams-online/{b2}').status_code == 404
    assert admin.get(f'/api/tasks/{ta}', params={'archived': True}).json() == []
    assert s0.get('/api/portal/tasks').json() == []


def test_exam_validation(world, clock, monkeypatch):
    as_, S = world
    monkeypatch.setattr('app.api.exams_online.now', clock)
    admin, ta, cid, st, ids = setup(world)
    xf = admin.post('/api/classes', json={'name': 'X f'}).json()['id']
    admin.post(f'/api/classes/{xf}/join', json={'subject': 'Fizika', 'weekly_hours': 1, 'slots': {}})
    with S() as db:
        ta_f = db.query(TeachingAssignment).filter_by(class_id=xf).one().id
    clock.t = dt.datetime(2026, 9, 29, 10, 0, tzinfo=UTC)
    win = {'opens_at': '2026-09-29T11:00:00Z', 'closes_at': '2026-09-29T12:00:00Z'}
    body = {'title': 'Sınaq', 'bank_ids': ids, 'targets': [{'ta_id': ta, **win}, {'ta_id': ta_f, **win}]}
    assert admin.post('/api/exams-online', json=body).status_code == 400                        # iki fənn
    one = {**body, 'targets': [{'ta_id': ta, **win}]}
    assert admin.post('/api/exams-online', json={**one, 'duration_min': 90}).status_code == 400  # müddət > aralıq
    assert admin.post('/api/exams-online', json={**one, 'penalty': 2}).status_code == 422
    assert admin.post('/api/exams-online', json={**one, 'targets': [{'ta_id': ta, 'opens_at': '2026-09-28T08:00:00Z',
                                                                     'closes_at': '2026-09-28T09:00:00Z'}]}).status_code == 400
    assert admin.get('/api/exams-online').json() == []


def test_bank_file_kind_patch(world, clock):
    as_, S = world
    admin, ta, cid, st, ids = setup(world)
    f = admin.get('/api/bank/lessons', params={'source': 'p012'}).json()[0]
    assert f['kind'] == 'movzu' and not f['meta_locked']                       # testdə təsnif olunmayıb – default
    assert as_('ilqar').patch(f'/api/bank/files/{f["id"]}', json={'kind': 'sinaq'}).status_code == 403
    r = admin.patch(f'/api/bank/files/{f["id"]}', json={'kind': 'sinaq', 'grades': [11, 11]}).json()
    assert (r['kind'], r['grades'], r['meta_locked']) == ('sinaq', [11], True)
    assert admin.patch(f'/api/bank/files/{f["id"]}', json={'grades': [13]}).status_code == 400
    assert admin.get('/api/bank/sources').json()[0]['kinds'] == {'sinaq': 1}
    r = admin.patch(f'/api/bank/files/{f["id"]}', json={'auto': True}).json()   # ÜSİ-1 → avtomatik sınaq, 11
    assert (r['kind'], r['grades'], r['meta_locked']) == ('sinaq', [11], False)
