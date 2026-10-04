"""Tapşırıqların şagirdlər üzrə təyini (docs/sagird-secimi-promtu.md): «Kimə» siyahısı, seçilmiş şagirdlərə sınaq,
başlamış şagirdi auditoriyadan çıxarmaq qadağası, mövzu testində seçim."""
import datetime as dt

from app.models import OnlineTask

from .test_api_portal import UTC, clock, setup, student_client  # noqa: F401 – clock fixture


def test_target_students_list_and_access(world):
    as_, _ = world
    admin, ta, cid, st, ids = setup(world)
    lst = admin.get(f'/api/exams-online/targets/{ta}/students').json()
    assert [x['id'] for x in lst] == sorted([s['id'] for s in st], key=lambda i: next(x['full_name'] for x in st if x['id'] == i))
    assert {'id', 'full_name', 'portal_code', 'level'} <= set(lst[0])
    assert as_('ilqar').get(f'/api/exams-online/targets/{ta}/students').status_code == 404      # başqasının sinfi


def test_exam_to_selected_students(world, clock, monkeypatch):
    as_, S = world
    monkeypatch.setattr('app.api.exams_online.now', clock)
    admin, ta, cid, st, ids = setup(world)
    clock.t = dt.datetime(2026, 9, 29, 10, 0, tzinfo=UTC)
    win = {'opens_at': '2026-09-29T11:00:00Z', 'closes_at': '2026-09-29T14:00:00Z'}
    picked = [st[0]['id'], st[2]['id']]
    r = admin.post('/api/exams-online', json={'title': 'Seçilmiş sınaq', 'bank_ids': ids,
                                              'targets': [{'ta_id': ta, **win, 'student_ids': picked}]})
    assert r.status_code == 200, r.text
    with S() as db:
        t = db.query(OnlineTask).filter_by(assignment_id=ta, kind='sinaq').one()
        assert sorted(t.student_ids) == sorted(picked)
        tid = t.id
    seen = lambda s: [x['id'] for x in student_client(s['portal_code'], s['initial_pin']).get('/api/portal/tasks').json()]
    assert tid in seen(st[0]) and tid in seen(st[2]) and tid not in seen(st[1])
    bad = admin.post('/api/exams-online', json={'title': 'Boş sınaq', 'bank_ids': ids, 'targets': [{'ta_id': ta, **win, 'student_ids': []}]})
    assert bad.status_code == 400


def test_cannot_remove_started_student(world, clock, monkeypatch):
    as_, S = world
    for m in ('app.api.tasks.now', 'app.api.portal.now', 'app.api.exams_online.now'):
        monkeypatch.setattr(m, clock, raising=False)
    admin, ta, cid, st, ids = setup(world)
    clock.t = dt.datetime(2026, 9, 29, 11, 30, tzinfo=UTC)
    win = {'opens_at': '2026-09-29T11:00:00Z', 'closes_at': '2026-09-29T14:00:00Z'}
    admin.post('/api/exams-online', json={'title': 'Sınaq', 'bank_ids': ids, 'targets': [{'ta_id': ta, **win}]})
    with S() as db:
        tid = db.query(OnlineTask).filter_by(assignment_id=ta).one().id
    c = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    assert c.post(f'/api/portal/tasks/{tid}/start').status_code == 200
    r = admin.patch(f'/api/tasks/{ta}/{tid}', json={'student_ids': [st[1]['id']]})
    assert r.status_code == 409 and 'artıq başlayıb' in r.json()['detail']
    ok = admin.patch(f'/api/tasks/{ta}/{tid}', json={'student_ids': [st[0]['id'], st[1]['id']]})
    assert ok.status_code == 200 and sorted(ok.json()['student_ids']) == sorted([st[0]['id'], st[1]['id']])


def test_topic_test_to_selected_students(world, clock, monkeypatch):
    as_, S = world
    monkeypatch.setattr('app.api.topic_tests.now', clock, raising=False)
    admin, ta, cid, st, ids = setup(world)
    clock.t = dt.datetime(2026, 9, 29, 10, 0, tzinfo=UTC)
    with S() as db:
        from app.models import PlanLesson
        pl = db.query(PlanLesson).filter_by(assignment_id=ta, seq=5).one().id
    r = admin.post(f'/api/plan/{ta}/topics/{pl}/test', json={
        'title': 'Kvadrat tənliklər – test', 'duration_min': 20, 'bank_ids': ids,
        'targets': [{'ta_id': ta, 'plan_lesson_id': pl, 'opens_at': '2026-09-29T11:00:00Z', 'closes_at': '2026-09-30T18:00:00Z',
                     'student_ids': [st[1]['id']]}]})
    assert r.status_code == 200, r.text
    assert r.json()['tasks'][0]['student_ids'] == [st[1]['id']]
