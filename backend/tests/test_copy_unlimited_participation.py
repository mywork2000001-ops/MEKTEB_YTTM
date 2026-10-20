"""Yenidən göndər (müddətsiz rejim, KSQ 45 dəq) və iştirak faizi (yazmayana 0%, test yoxdursa None)."""
import datetime as dt

from app.models import OnlineTask

from .test_api_portal import UTC, clock, mk_task, setup  # noqa: F401 – clock fixture


def test_copy_unlimited_and_ksq(world, clock):
    admin, ta, cid, st, ids = setup(world)
    t = mk_task(admin, ta, ids, closes_at=None, duration_min=0)
    assert t.status_code == 200, t.text
    t = t.json()
    body = {'target_ta_id': ta, 'opens_at': '2026-09-30T08:00:00Z', 'title': 'Müddətsiz təkrar'}
    c1 = admin.post(f'/api/tasks/{ta}/{t["id"]}/copy', json=body)
    assert c1.status_code == 200, c1.text
    assert c1.json()['duration_min'] == 0 and c1.json()['closes_at'].startswith('2100-01-01')
    # vaxtlı mənbə + açıq «müddətsiz» seçimi
    t2 = mk_task(admin, ta, ids, title='Test 2').json()
    c2 = admin.post(f'/api/tasks/{ta}/{t2["id"]}/copy', json={**body, 'unlimited': True, 'closes_at': '2026-09-30T09:00:00Z'})
    assert c2.status_code == 200 and c2.json()['duration_min'] == 0 and c2.json()['closes_at'].startswith('2100-01-01')
    # seçim yoxdursa vaxtlı qalır
    c3 = admin.post(f'/api/tasks/{ta}/{t2["id"]}/copy', json={**body, 'closes_at': '2026-09-30T09:00:00Z'}).json()
    assert c3['duration_min'] == 45 and not c3['closes_at'].startswith('2100')
    # KSQ/BSQ: müddətsiz olmur, 45 dəq
    with world[1]() as db:
        db.get(OnlineTask, t2['id']).kind = 'ksq'
        db.commit()
    assert admin.post(f'/api/tasks/{ta}/{t2["id"]}/copy', json={**body, 'unlimited': True}).status_code == 400
    c4 = admin.post(f'/api/tasks/{ta}/{t2["id"]}/copy', json={**body, 'closes_at': '2026-09-30T10:00:00Z', 'unlimited': True})
    assert c4.status_code == 200 and c4.json()['duration_min'] == 45 and not c4.json()['closes_at'].startswith('2100')


def test_participation_zero_when_nobody_wrote(world, clock, monkeypatch):
    for mod in ('app.api.exams_online', 'app.api.topic_tests', 'app.test_stats'):
        monkeypatch.setattr(f'{mod}.now', clock)
    admin, ta, cid, st, ids = setup(world)
    clock.t = dt.datetime(2026, 9, 29, 10, 0, tzinfo=UTC)
    c = admin.get(f'/api/results-center/class/{ta}').json()['parts']['sinaq']
    assert c['summary']['participation'] is None and c['students'] == []
    win = {'opens_at': '2026-09-29T11:00:00Z', 'closes_at': '2026-09-29T14:00:00Z'}
    r = admin.post('/api/exams-online', json={'title': 'Sınaq 1', 'bank_ids': ids, 'targets': [{'ta_id': ta, **win}]})
    assert r.status_code == 200, r.text
    clock.t = dt.datetime(2026, 9, 29, 15, 0, tzinfo=UTC)        # bağlanıb, heç kim yazmayıb
    c = admin.get(f'/api/results-center/class/{ta}').json()['parts']['sinaq']
    assert c['summary']['participation'] == 0.0
    assert [s['participation'] for s in c['students']] == [0.0, 0.0, 0.0]
