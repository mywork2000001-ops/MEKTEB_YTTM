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
    assert c1.status_code == 200 and c1.json()['questions'] == 3 and c1.json()['duration_min'] == 40
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
