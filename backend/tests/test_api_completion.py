"""Tamamlama: mövzu testində səviyyə hədəfi və variantlar, əvvəlki testlərdən götürmə, əlavə məşğələ materialları,
şagird bildirişləri."""
import datetime as dt

from app.models import Mark, OnlineTask, PlanLesson, TeachingAssignment

from .test_api_portal import UTC, clock, setup, student_client  # noqa: F401 – clock fixture


def _patch(monkeypatch, clock, day):
    for mod in ('app.api.topic_tests', 'app.task_journal', 'app.api.exams_online', 'app.api.extra'):
        monkeypatch.setattr(f'{mod}.now', clock)
    for mod in ('app.task_journal', 'app.api.journal'):
        monkeypatch.setattr(f'{mod}.today', lambda: day[0])


def test_topic_test_levels_and_variants(world, clock, monkeypatch):
    as_, S = world
    day = [dt.date(2026, 9, 29)]
    _patch(monkeypatch, clock, day)
    admin, ta, cid, st, ids = setup(world)
    admin.put(f'/api/levels/{ta}/{st[0]["id"]}', json={'level': 'Güclü'})
    admin.put(f'/api/levels/{ta}/{st[1]["id"]}', json={'level': 'Zəif'})          # st[2] – səviyyəsiz → «Orta»
    with S() as db:
        pl5 = db.query(PlanLesson).filter_by(assignment_id=ta, seq=5).one().id
    clock.t = dt.datetime(2026, 9, 29, 10, 0, tzinfo=UTC)
    tg = {'ta_id': ta, 'plan_lesson_id': pl5, 'opens_at': '2026-09-29T11:00:00Z', 'closes_at': '2026-09-29T14:00:00Z'}
    base = {'title': 'Kvadrat tənliklər', 'duration_min': 20, 'targets': [tg]}
    # yalnız Zəif qrupa
    r = admin.post(f'/api/plan/{ta}/topics/{pl5}/test', json={**base, 'bank_ids': ids, 'targets': [{**tg, 'levels': ['Zəif']}]})
    assert r.status_code == 200 and r.json()['tasks'][0]['student_ids'] == [st[1]['id']]
    assert admin.post(f'/api/plan/{ta}/topics/{pl5}/test', json={**base, 'bank_ids': ids,
                                                                  'targets': [{**tg, 'levels': ['Orta']}]}).status_code == 400
    # variantlar: «Orta» məcburi; hər səviyyəyə öz tapşırığı
    v = {'Zəif': {'bank_ids': ids[:1]}, 'Güclü': {'bank_ids': ids}}
    assert admin.post(f'/api/plan/{ta}/topics/{pl5}/test', json={**base, 'variants': v}).status_code == 422
    v['Orta'] = {'bank_ids': ids[:2]}
    r = admin.post(f'/api/plan/{ta}/topics/{pl5}/test', json={**base, 'variants': v}).json()
    got = {t['title']: (t['student_ids'], t['questions']) for t in r['tasks']}
    assert got == {'Kvadrat tənliklər · Zəif variant': ([st[1]['id']], 1),
                   'Kvadrat tənliklər · Orta variant': ([st[2]['id']], 2),
                   'Kvadrat tənliklər · Güclü variant': ([st[0]['id']], 3)}
    tid = {t['title'].split(' · ')[1]: t['id'] for t in r['tasks']}
    clock.t = dt.datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
    for s_, key in ((st[0], 'Güclü variant'), (st[1], 'Zəif variant')):
        c = student_client(s_['portal_code'], s_['initial_pin'])
        assert [x['id'] for x in c.get('/api/portal/tasks').json() if x['id'] in tid.values()] == [tid[key]]
        q = c.post(f'/api/portal/tasks/{tid[key]}/start').json()
        idx = {x['text']['az']: x['index'] for x in q['questions']}
        c.post(f'/api/portal/tasks/{tid[key]}/submit', json={'answers': {str(idx['2+2=?']): 1}})
    clock.t = dt.datetime(2026, 9, 29, 15, 0, tzinfo=UTC)
    from app.task_journal import run_due
    with S() as db:
        run_due(db)
        marks = {m.student_id: (m.test_correct, m.test_total) for m in db.query(Mark).filter(Mark.task_id.in_(tid.values()))}
    assert marks == {st[0]['id']: (1, 3), st[1]['id']: (1, 1)}           # hər biri öz variantının sual sayından

    # başqa sinifdə eyni mövzu – əvvəlki testlərdən sualları götürmək
    xc = admin.post('/api/classes', json={'name': 'X c'}).json()['id']
    admin.post(f'/api/classes/{xc}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 1, 'slots': {}})
    with S() as db:
        ta2 = db.query(TeachingAssignment).filter_by(class_id=xc).one().id
        db.add(PlanLesson(assignment_id=ta2, seq=1, semester=1, assessment_type='formativ', topic='KVADRAT TƏNLİKLƏR',
                          date=dt.date(2026, 9, 17)))
        db.commit()
        pl_c = db.query(PlanLesson).filter_by(assignment_id=ta2).one().id
    prev = admin.get(f'/api/plan/{ta2}/topics/{pl_c}/previous').json()
    assert {p['title'] for p in prev} == {'Kvadrat tənliklər', *got} and all(p['questions'] for p in prev)
    assert as_('yad').get(f'/api/plan/{ta2}/topics/{pl_c}/previous').status_code == 404


def test_extra_materials_and_notifications(world, clock, monkeypatch):
    as_, S = world
    day = [dt.date(2026, 10, 2)]
    _patch(monkeypatch, clock, day)
    admin, ta, cid, st, ids = setup(world)
    clock.t = dt.datetime(2026, 10, 2, 8, 0, tzinfo=UTC)
    m_all = admin.post(f'/api/materials/{ta}', data={'kind': 'link', 'title': 'Kəsrlər – video', 'url': 'https://example.org/v'}).json()
    m_one = admin.post(f'/api/materials/{ta}', data={'kind': 'note', 'title': 'Fərdi qeyd', 'body': 'yalnız Şagird0',
                                                     'student_ids': str(st[0]['id'])}).json()
    c = admin.post('/api/extra', json={'title': 'Təkrar', 'format': 'onlayn', 'ta_ids': [ta],
                                       'schedule': [{'weekday': 5, 'start': '10:00', 'end': '11:00', 'link': 'https://meet.example/x'}],
                                       'starts_on': '2026-10-03', 'ends_on': '2026-10-10'}).json()
    sid = admin.get(f'/api/extra/{c["id"]}').json()['session_list'][0]['id']
    assert admin.put(f'/api/extra/{c["id"]}/sessions/{sid}', json={'material_ids': [999999]}).status_code == 400
    u = admin.put(f'/api/extra/{c["id"]}/sessions/{sid}', json={'material_ids': [m_all['id'], m_one['id']]}).json()
    assert [m['title'] for m in u['materials']] == ['Kəsrlər – video', 'Fərdi qeyd']
    s0 = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    s1 = student_client(st[1]['portal_code'], st[1]['initial_pin'])
    titles = lambda cl: [m['title'] for m in cl.get('/api/portal/extra').json()[0]['sessions'][0]['materials']]
    assert titles(s0) == ['Kəsrlər – video', 'Fərdi qeyd'] and titles(s1) == ['Kəsrlər – video']   # yalnız ona açıq olan

    # bildirişlər: sabahkı məşğələ, 24 saat ərzində açılacaq test, açıq test
    admin.post(f'/api/tasks/{ta}', json={'title': 'Test A', 'opens_at': '2026-10-02T12:00:00Z', 'closes_at': '2026-10-02T18:00:00Z',
                                         'duration_min': 20, 'bank_ids': ids})
    n = s1.get('/api/portal/notifications').json()
    keys = {x['key'].split('-')[0] + '-' + x['key'].split('-')[1] for x in n}
    assert {'extra-' + str(sid).split('-')[0], 'task-soon'} <= keys
    assert next(x for x in n if x['kind'] == 'məşğələ')['title'].startswith('Təkrar – sabah 10:00')
    clock.t = dt.datetime(2026, 10, 2, 13, 0, tzinfo=UTC)
    monkeypatch.setattr('app.api.portal.now', clock)
    n = s1.get('/api/portal/notifications').json()
    assert any(x['key'].startswith('task-open-') and x['link'].startswith('/t/') for x in n)
