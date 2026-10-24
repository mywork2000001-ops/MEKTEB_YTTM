"""Test: yenidən göndər (surət, başqa sinfə), silinəni geri qaytar, bir şagirdə təkrar icazə."""
import datetime as dt

from .test_api_portal import UTC, as_topic, clock, mk_task, setup, student_client  # noqa: F401


def test_copy_restore_and_retake(world, clock):
    admin, ta, cid, st, ids = setup(world)
    t = mk_task(admin, ta, ids).json()                              # 15:00–16:00, 40 dəq
    # başqa sinif (X c) – müəllimin öz dərsi
    xc = admin.post('/api/classes', json={'name': 'X c'}).json()['id']
    admin.post(f'/api/classes/{xc}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 1, 'slots': {}})
    ta2 = next(l['id'] for l in admin.get('/api/my/lessons').json() if l['class_id'] == xc)

    s = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    clock.t = dt.datetime(2026, 9, 29, 15, 10, tzinfo=UTC)
    s.post(f'/api/portal/tasks/{t["id"]}/start')
    s.post(f'/api/portal/tasks/{t["id"]}/submit', json={'answers': {}})
    # bir şagirdə təkrar icazə – cəhd silinir, yenidən başlaya bilir
    assert admin.delete(f'/api/tasks/{ta}/{t["id"]}/attempts/{st[0]["id"]}').status_code == 200
    assert s.post(f'/api/portal/tasks/{t["id"]}/start').status_code == 200
    assert admin.delete(f'/api/tasks/{ta}/{t["id"]}/attempts/{st[1]["id"]}').status_code == 404

    # yenidən göndər: həmin sinfə, yeni vaxtla; və başqa sinfə
    body = {'target_ta_id': ta, 'opens_at': '2026-09-30T08:00:00Z', 'closes_at': '2026-09-30T09:00:00Z', 'title': 'Test 1 (təkrar)'}
    c1 = admin.post(f'/api/tasks/{ta}/{t["id"]}/copy', json=body)
    assert c1.status_code == 200 and c1.json()['questions'] == 3 and c1.json()['duration_min'] == 45   # ən azı 45 dəq
    c2 = admin.post(f'/api/tasks/{ta}/{t["id"]}/copy', json={**body, 'target_ta_id': ta2, 'duration_min': 20}).json()
    assert c2['title'] == 'Test 1 (təkrar)' and len(admin.get(f'/api/tasks/{ta2}').json()) == 1
    assert admin.post(f'/api/tasks/{ta}/{t["id"]}/copy', json={**body, 'closes_at': '2026-09-29T10:00:00Z',
                                                              'opens_at': '2026-09-29T09:00:00Z'}).status_code == 400   # keçmiş
    assert admin.post(f'/api/tasks/{ta}/{t["id"]}/copy', json={**body, 'duration_min': 90}).status_code == 400
    assert admin.post(f'/api/tasks/{ta}/{t["id"]}/copy', json={**body, 'student_ids': [99999]}).status_code == 400

    assert c1.json()['kind'] == c2['kind'] == 'sinaq'                 # plandan kənar test – sınaq
    # sınaq silinəndə tam gedir
    assert admin.post(f'/api/tasks/{ta}/{c1.json()["id"]}/archive').json()['deleted'] is True
    assert admin.get(f'/api/tasks/{ta}', params={'archived': True}).json() == []
    # mövzu testi: sil → silinənlərdə görünür → geri qaytar
    as_topic(world[1], t['id'])
    admin.post(f'/api/tasks/{ta}/{t["id"]}/archive')
    assert t['id'] not in [x['id'] for x in admin.get(f'/api/tasks/{ta}').json()]
    assert [x['id'] for x in admin.get(f'/api/tasks/{ta}', params={'archived': True}).json()] == [t['id']]
    assert admin.post(f'/api/tasks/{ta}/{t["id"]}/restore').status_code == 200
    assert t['id'] in [x['id'] for x in admin.get(f'/api/tasks/{ta}').json()]
    # «Silinənlər»dən birdəfəlik silmə: aktiv mövzu testi birbaşa silinmir
    assert admin.delete(f'/api/tasks/{ta}/{t["id"]}').status_code == 400
    # bağlanmış testə təkrar icazə olmaz
    clock.t = dt.datetime(2026, 9, 29, 17, 0, tzinfo=UTC)
    assert admin.delete(f'/api/tasks/{ta}/{t["id"]}/attempts/{st[0]["id"]}').status_code == 409


def test_resume_attempt_keeps_answers(world, clock):
    """«Davam etsin»: şagird təsadüfən çıxıb (vaxt bitdi / təhvil getdi) — test bağlansa da cəhd açılır, cavablar saxlanır."""
    admin, ta, cid, st, ids = setup(world)
    t = mk_task(admin, ta, ids).json()                              # 15:00–16:00, 40 dəq
    s = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    clock.t = dt.datetime(2026, 9, 29, 15, 10, tzinfo=UTC)
    q = s.post(f'/api/portal/tasks/{t["id"]}/start').json()
    first = q['questions'][0]['index']
    s.put(f'/api/portal/tasks/{t["id"]}/answers', json={'answers': {str(first): 1}})
    clock.t = dt.datetime(2026, 9, 29, 15, 20, tzinfo=UTC)
    s.post(f'/api/portal/tasks/{t["id"]}/submit', json={'answers': {}})       # təsadüfən təhvil (10 dəq işlədib)
    clock.t = dt.datetime(2026, 9, 29, 17, 0, tzinfo=UTC)                     # test artıq bağlanıb
    assert admin.post(f'/api/tasks/{ta}/{t["id"]}/attempts/{st[1]["id"]}/resume').status_code == 404   # başlamayıb
    r = admin.post(f'/api/tasks/{ta}/{t["id"]}/attempts/{st[0]["id"]}/resume').json()
    assert r['minutes'] == 35 and r['answers'] == 1                           # qalan vaxt: 45 (ən azı) − 10
    again = s.post(f'/api/portal/tasks/{t["id"]}/start')
    assert again.status_code == 200 and again.json()['answers'] == {str(first): 1}
    assert next(x for x in s.get('/api/portal/tasks').json() if x['id'] == t['id'])['status'] == 'həll edilir'
    res = s.post(f'/api/portal/tasks/{t["id"]}/submit', json={'answers': {}}).json()
    assert res['total'] == 3
    assert admin.post(f'/api/tasks/{ta}/{t["id"]}/attempts/{st[0]["id"]}/resume', json={'minutes': 15}).json()['minutes'] == 15
    # bütün sinif: özü təhvil verən açılmır (yalnız təsadüfən kəsilənlər)
    s.post(f'/api/portal/tasks/{t["id"]}/submit', json={'answers': {}})
    r = admin.post(f'/api/tasks/{ta}/{t["id"]}/resume-all').json()
    assert r['resumed'] == 0 and r['skipped_submitted'] == 1
    assert next(x for x in s.get('/api/portal/tasks').json() if x['id'] == t['id'])['status'] != 'həll edilir'


def test_resume_all_only_accidental(world, clock):
    """Vaxtı bitən (avto-təhvil) açılır və bağlanmış testdə dərhal yenidən bitmir; özü təhvil verən açılmır."""
    admin, ta, cid, st, ids = setup(world)
    t = mk_task(admin, ta, ids).json()                                        # 15:00-16:00, 40 dəq
    s0 = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    s1 = student_client(st[1]['portal_code'], st[1]['initial_pin'])
    clock.t = dt.datetime(2026, 9, 29, 15, 10, tzinfo=UTC)
    s0.post(f'/api/portal/tasks/{t["id"]}/start')
    s1.post(f'/api/portal/tasks/{t["id"]}/start')
    s0.post(f'/api/portal/tasks/{t["id"]}/submit', json={'answers': {}})
    clock.t = dt.datetime(2026, 9, 29, 15, 55, tzinfo=UTC)                      # s1-in vaxtı bitdi
    admin.get(f'/api/tasks/{ta}')
    s1.get('/api/portal/tasks')
    clock.t = dt.datetime(2026, 9, 29, 17, 0, tzinfo=UTC)                       # test bağlanıb
    r = admin.post(f'/api/tasks/{ta}/{t["id"]}/resume-all').json()
    assert r['resumed'] == 1 and r['skipped_submitted'] == 1
    clock.t = dt.datetime(2026, 9, 29, 17, 1, tzinfo=UTC)
    admin.get(f'/api/tasks/{ta}')                                               # expire_due: açılan cəhd bitməməlidir
    assert next(x for x in s1.get('/api/portal/tasks').json() if x['id'] == t['id'])['status'] == 'həll edilir'
    assert next(x for x in s0.get('/api/portal/tasks').json() if x['id'] == t['id'])['status'] != 'həll edilir'


def test_resume_keeps_old_result_until_submit(world, clock):
    admin, ta, cid, st, ids = setup(world)
    t = mk_task(admin, ta, ids).json()
    s = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    clock.t = dt.datetime(2026, 9, 29, 15, 10, tzinfo=UTC)
    s.post(f'/api/portal/tasks/{t["id"]}/start')
    s.post(f'/api/portal/tasks/{t["id"]}/submit', json={'answers': {}})
    assert admin.post(f'/api/tasks/{ta}/{t["id"]}/attempts/{st[0]["id"]}/resume').status_code == 200
    with world[1]() as db:
        from app.models import TaskAttempt
        a = db.query(TaskAttempt).one()
        assert a.submitted_at is None and a.total == 3


def test_restore_resumed(world, clock):
    """Admin bərpa: dry_run yazmır; bal > 30 təhvil kimi bərpa, aşağı açıq qalır."""
    admin, ta, cid, st, ids = setup(world)
    t = mk_task(admin, ta, ids).json()
    s0 = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    s1 = student_client(st[1]['portal_code'], st[1]['initial_pin'])
    clock.t = dt.datetime(2026, 9, 29, 15, 10, tzinfo=UTC)
    for s in (s0, s1):
        q = s.post(f'/api/portal/tasks/{t["id"]}/start').json()
    from app.models import TaskAttempt
    with world[1]() as db:                                                      # s0 – bütün cavablar düz, s1 – boş-yaxın
        for a in db.query(TaskAttempt).order_by(TaskAttempt.student_id):
            t_ = db.get(__import__('app.models', fromlist=['OnlineTask']).OnlineTask, a.task_id)
            if a.student_id == st[0]['id']:
                a.answers = {str(i): (q_['correct'] if 'correct' in q_ else 0) for i, q_ in enumerate(t_.questions)}
            else:
                a.answers = {'0': 99}
        db.commit()
    assert admin.post(f'/api/tasks/{ta}/{t["id"]}/resume-all').status_code == 200   # audit qeydi (heç kim təhvil verməyib → 0 açılır)
    with world[1]() as db:
        from app.api.common import audit
        audit(db, None, 'update', 'online_task', t['id'], resume_all=2)
        db.commit()
    r = admin.post('/api/admin/restore-resumed', json={}).json()
    assert r['dry_run'] and r['count'] == 2
    with world[1]() as db:
        assert db.query(TaskAttempt).filter(TaskAttempt.submitted_at.isnot(None)).count() == 0
    r = admin.post('/api/admin/restore-resumed', json={'dry_run': False}).json()
    acts = {x['student']: x['action'] for x in r['items']}
    assert sorted(acts.values()) == ['keep_open', 'restore']
    with world[1]() as db:
        assert db.query(TaskAttempt).filter(TaskAttempt.submitted_at.isnot(None)).count() == 1
