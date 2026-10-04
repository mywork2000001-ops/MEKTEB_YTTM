"""Test nəticələri mərkəzi: iki hissəli reytinq (mövzu testi və sınaq qarışmır), yazmayanlar və yenidən göndərmə
(surət kökün testinə aiddir), şagird / sinif / qrup / ümumi və süni intellektin rəyi (adlar provayderə getmir)."""
import datetime as dt

from app.models import PlanLesson

from .test_api_portal import UTC, clock, setup, student_client  # noqa: F401 – clock fixture


def _answer(st, task_id, by_text):
    c = student_client(st['portal_code'], st['initial_pin'])
    q = c.post(f'/api/portal/tasks/{task_id}/start').json()
    idx = {x['text']['az']: x['index'] for x in q['questions']}
    c.post(f'/api/portal/tasks/{task_id}/submit', json={'answers': {str(idx[k]): v for k, v in by_text.items()}})


ALL_OK = {'2+2=?': 1, 'x²=9, x>0': '3', '5·2=?': 0}


def test_results_center(world, clock, monkeypatch):
    as_, S = world
    for mod in ('app.api.exams_online', 'app.api.topic_tests', 'app.test_stats'):
        monkeypatch.setattr(f'{mod}.now', clock)
    admin, ta, cid, st, ids = setup(world)                     # X e – 3 şagird
    with S() as db:
        pl5 = db.query(PlanLesson).filter_by(assignment_id=ta, seq=5).one().id
    clock.t = dt.datetime(2026, 9, 29, 10, 0, tzinfo=UTC)
    win = {'opens_at': '2026-09-29T11:00:00Z', 'closes_at': '2026-09-29T14:00:00Z'}
    r = admin.post(f'/api/plan/{ta}/topics/{pl5}/test', json={'title': 'Kvadrat tənliklər – test', 'duration_min': 20,
                                                              'bank_ids': ids, 'targets': [{'ta_id': ta, 'plan_lesson_id': pl5, **win}]})
    assert r.status_code == 200, r.text
    tt = r.json()['tasks'][0]['id']
    r = admin.post('/api/exams-online', json={'title': 'Sınaq 1', 'bank_ids': ids, 'targets': [{'ta_id': ta, **win}]})
    bid = r.json()['id']
    from app.models import OnlineTask
    with S() as db:
        et = db.query(OnlineTask).filter_by(batch_id=bid).one().id

    clock.t = dt.datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
    _answer(st[0], tt, ALL_OK)                                  # mövzu: 100, 2/3 → 66.7, 3-cü yazmır
    _answer(st[1], tt, {'2+2=?': 1, '5·2=?': 0})
    _answer(st[2], et, ALL_OK)                                  # sınaq: yalnız 3-cü yazır

    # açıq ikən – yazmayan yoxdur (gözlənilir)
    assert admin.get('/api/results-center/missing').json()['students'] == []

    clock.t = dt.datetime(2026, 9, 29, 15, 0, tzinfo=UTC)
    mv = admin.get('/api/results-center/rating', params={'kind': 'movzu'}).json()
    sq = admin.get('/api/results-center/rating', params={'kind': 'sinaq'}).json()
    assert [(x['full_name'], x['avg_pct'], x['place_all']) for x in mv['rows']] == \
        [(st[0]['full_name'], 100.0, 1), (st[1]['full_name'], 66.7, 2), (st[2]['full_name'], None, None)]
    assert mv['rows'][2]['given'] == 1 and mv['rows'][2]['wrote'] == 0
    assert [(x['full_name'], x['avg_pct']) for x in sq['rows'] if x['avg_pct'] is not None] == [(st[2]['full_name'], 100.0)]
    assert mv['classes'][0]['participation'] == 66.7 and sq['classes'][0]['participation'] == 33.3
    assert len(mv['tests']) == 1 and mv['tests'][0]['topic'] == 'Kvadrat tənliklər'
    assert admin.get('/api/results-center/rating', params={'kind': 'movzu', 'subject': 'Fizika'}).json()['rows'] == []

    m = admin.get('/api/results-center/missing').json()
    got = {x['full_name']: (x['missed'], x['given']) for x in m['students']}
    assert got == {st[2]['full_name']: (1, 2), st[0]['full_name']: (1, 2), st[1]['full_name']: (1, 2)}
    assert {t['title']: t['missed'] for t in m['tests']} == {'Kvadrat tənliklər – test': 1, 'Sınaq 1': 2}
    assert admin.get('/api/results-center/missing', params={'kind': 'movzu'}).json()['students'][0]['tests'][0]['task_id'] == tt

    # yazmayanlara yenidən göndər – surət yazılandan sonra şagird yazmayanlardan çıxır, nəticə kök testə düşür
    miss = next(x for x in m['students'] if x['full_name'] == st[2]['full_name'])['tests'][0]
    r = admin.post('/api/results-center/missing/resend', json={
        'items': [{'ta_id': miss['ta_id'], 'task_id': miss['task_id'], 'student_ids': [st[2]['id']]}],
        'opens_at': '2026-09-30T08:00:00Z', 'closes_at': '2026-09-30T12:00:00Z'})
    assert r.status_code == 200 and r.json()['tasks'] == 1, r.text
    with S() as db:
        copy = db.query(OnlineTask).filter(OnlineTask.kind == 'movzu', OnlineTask.id != tt).one()
        assert copy.student_ids == [st[2]['id']]
    clock.t = dt.datetime(2026, 9, 30, 9, 0, tzinfo=UTC)
    _answer(st[2], copy.id, {'2+2=?': 1})
    clock.t = dt.datetime(2026, 9, 30, 13, 0, tzinfo=UTC)
    mv = admin.get('/api/results-center/rating', params={'kind': 'movzu'}).json()
    assert len(mv['tests']) == 1 and next(x for x in mv['rows'] if x['full_name'] == st[2]['full_name'])['avg_pct'] == 33.3
    assert st[2]['full_name'] not in {x['full_name'] for x in
                                      admin.get('/api/results-center/missing', params={'kind': 'movzu'}).json()['students']}

    # şagird portalı: mövzu testləri üzrə öz yeri (adsız)
    me0 = student_client(st[0]['portal_code'], st[0]['initial_pin']).get('/api/portal/topic-rating').json()
    assert me0 == [{'subject': 'Riyaziyyat', 'class_name': 'X e', 'tests': 1, 'avg_pct': 100.0, 'last_pct': 100.0, 'delta': None,
                    'given': 1, 'wrote': 1, 'missed': 0, 'place_class': 1, 'class_count': 3, 'class_avg': 66.7}]

    # şagird profili, sinif/qrup, ümumi
    p = admin.get(f'/api/results-center/student/{st[0]["id"]}').json()
    assert p['parts']['movzu']['summary']['avg_pct'] == 100.0 and p['parts']['movzu']['items'][0]['class_avg'] == 66.7
    assert p['parts']['sinaq']['items'][0]['status'] == 'yazmayıb'
    assert as_('yad').get(f'/api/results-center/student/{st[0]["id"]}').status_code == 404
    c = admin.get(f'/api/results-center/class/{ta}').json()
    assert c['parts']['movzu']['summary']['avg_pct'] == 66.7 and c['parts']['movzu']['distribution']['5'] == 1
    admin.put(f'/api/analytics/{ta}/levels/{st[0]["id"]}', json={'level': 'Güclü'})
    g = admin.get(f'/api/results-center/class/{ta}', params={'level': 'Güclü'}).json()
    assert g['parts']['movzu']['summary']['students'] == 1
    al = admin.get('/api/results-center/class', params={'level': 'Güclü'}).json()          # «Hamısı» – bütün siniflərim
    assert al['ta_id'] is None and al['class_name'] == 'Bütün siniflərim' and al['parts']['movzu']['summary']['students'] == 1
    assert admin.get('/api/results-center/class').json()['parts']['movzu']['summary']['avg_pct'] == 66.7
    o = admin.get('/api/results-center/overview').json()
    assert o['classes'][0]['class_name'] == 'X e' and o['summary']['sinaq']['tests'] == 1
    assert {x['full_name'] for x in admin.get('/api/results-center/students').json()} == {s['full_name'] for s in st}

    # süni intellektin rəyi: adlar provayderə getmir, cavabda geri qoyulur; sonuncu rəy saxlanır
    sent = {}

    def fake(cfg, system, user):
        sent['text'] = user
        return {'xulase': 'Ş-1 mövzu testində 100% göstərib.', 'guclu': ['Kvadrat tənliklər'], 'zeif': [],
                'sebebler': [], 'tovsiyeler': [{'ne': 'Sınaqda iştirak', 'kim': 'şagird', 'muddet': '2 həftə'}],
                'valideyne': 'Ş-1 yaxşı oxuyur', 'diqqet': []}
    monkeypatch.setattr('app.api.results_center.ai.complete_json', fake)
    monkeypatch.setattr('app.api.lessonplans.ai_config', lambda u: {'provider': 'gemini', 'model': 'm', 'api_key': 'k'})
    r = admin.post('/api/results-center/ai-review', json={'scope': 'student', 'student_id': st[0]['id']})
    assert r.status_code == 200, r.text
    assert st[0]['full_name'] not in sent['text'] and 'Ş-1' in sent['text']
    rv = r.json()['review']['payload']
    assert rv['xulase'].startswith(st[0]['full_name']) and rv['tovsiyeler'][0]['muddet'] == '2 həftə'
    last = admin.get('/api/results-center/ai-review', params={'scope': 'student', 'student_id': st[0]['id']}).json()
    assert last['review']['payload']['valideyne'].startswith(st[0]['full_name'])
    r = admin.post('/api/results-center/ai-review', json={'scope': 'class', 'ta_id': ta})
    assert r.status_code == 200 and all(s['full_name'] not in sent['text'] for s in st)
    assert r.json()['review']['payload']['valideyne'] == ''
    assert admin.post('/api/results-center/ai-review', json={'scope': 'group', 'ta_id': ta}).status_code == 400
    r = admin.post('/api/results-center/ai-review', json={'scope': 'class', 'kind': 'sinaq'})       # bütün siniflər, yalnız sınaq
    assert r.status_code == 200 and r.json()['review']['key'] == 'class:all:sinaq' and 'mövzu testləri' not in sent['text']
    assert admin.post('/api/results-center/ai-review', json={'scope': 'overall'}).status_code == 200
