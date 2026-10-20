"""Müddətsiz testlər (docs/tasks/muddetsiz-testler.md): duration_min=0 + closes_at=NO_DEADLINE; KSQ dəyişmir; unlimit-tasks."""
import datetime as dt

import pytest
from pydantic import ValidationError

from app.api.ksq_online import SendIn
from app.models import OnlineTask
from app.student_report import MISSING_STATUSES
from app.timing import NO_DEADLINE, NOT_DONE, attempt_deadline, fits_window, is_unlimited, no_timer

from .test_api_portal import UTC, clock, mk_task, setup, student_client  # noqa: F401


def _open(admin, ta, ids, **kw):
    return mk_task(admin, ta, ids, duration_min=0, closes_at=None, opens_at='2026-09-29T15:00:00Z', **kw)


def test_timing_helpers():
    t = OnlineTask(duration_min=0, closes_at=NO_DEADLINE)
    s = dt.datetime(2026, 9, 29, 15, 0, tzinfo=UTC)
    assert is_unlimited(t) and no_timer(t) and attempt_deadline(t, s) == NO_DEADLINE
    t2 = OnlineTask(duration_min=40, closes_at=s + dt.timedelta(minutes=30))
    assert not is_unlimited(t2) and attempt_deadline(t2, s) == s + dt.timedelta(minutes=30)
    assert fits_window(0, s, s) and not fits_window(40, s, s + dt.timedelta(minutes=30))
    assert NOT_DONE in MISSING_STATUSES


def test_unlimited_flow(world, clock):
    admin, ta, cid, st, ids = setup(world)
    r = _open(admin, ta, ids)
    assert r.status_code == 200, r.text
    t = r.json()
    assert t['duration_min'] == 0 and t['closes_at'].startswith('2100-01-01')
    s = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    clock.t = dt.datetime(2026, 9, 29, 15, 5, tzinfo=UTC)
    lst = s.get('/api/portal/tasks').json()[0]
    assert lst['unlimited'] and lst['no_timer'] and lst['status'] == 'açıq'
    r = s.post(f'/api/portal/tasks/{t["id"]}/start').json()
    assert r['deadline'].startswith('2100-01-01') and r['unlimited'] and r['no_timer']
    by_text = {q['text']['az']: q['index'] for q in r['questions']}
    clock.t = dt.datetime(2026, 9, 29, 18, 30, tzinfo=UTC)                  # 3,5 saat sonra
    assert s.put(f'/api/portal/tasks/{t["id"]}/answers', json={'answers': {str(by_text['2+2=?']): 1}}).status_code == 200
    # hesabat: təhvil verilməyib – «işlənməyib» (başlamayanlar da)
    ml = admin.get(f'/api/results-center/class/{ta}/missing-list').json()
    assert {i['status'] for x in ml['rows'] for i in x['items']} == {NOT_DONE} and ml['students'] == 3
    assert s.get(f'/api/portal/tasks/{t["id"]}/review').status_code == 403   # təhvil verilməyib
    sub = s.post(f'/api/portal/tasks/{t["id"]}/submit', json={'answers': {str(by_text['x²=9, x>0']): '3'}})
    assert sub.status_code == 200 and sub.json()['auto_submitted'] is False
    # «bağlandıqdan sonra» cavablar = təhvildən dərhal sonra
    assert s.get(f'/api/portal/tasks/{t["id"]}/review').status_code == 200
    ml = admin.get(f'/api/results-center/class/{ta}/missing-list').json()
    assert ml['students'] == 2 and st[0]['id'] not in {x['student_id'] for x in ml['rows']}


def test_close_button_submits_open_attempts(world, clock):
    admin, ta, cid, st, ids = setup(world)
    t = _open(admin, ta, ids).json()
    s = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    clock.t = dt.datetime(2026, 9, 29, 15, 5, tzinfo=UTC)
    s.post(f'/api/portal/tasks/{t["id"]}/start')
    clock.t = dt.datetime(2026, 9, 29, 20, 0, tzinfo=UTC)
    r = admin.post(f'/api/tasks/{ta}/{t["id"]}/close')
    assert r.status_code == 200 and r.json()['auto_submitted'] == 1
    row = next(x for x in admin.get(f'/api/tasks/{ta}/{t["id"]}').json()['rows'] if x['student_id'] == st[0]['id'])
    assert row['status'] == 'təhvil verib' and row['auto_submitted']
    assert admin.get(f'/api/tasks/{ta}').json()[0]['closes_at'].startswith('2026-09-29T20:00')


def test_timer_and_deadline_still_work(world, clock):
    admin, ta, cid, st, ids = setup(world)
    t = admin.post(f'/api/tasks/{ta}', json={'title': 'Test T','opens_at': '2026-09-29T15:00:00Z', 'closes_at': '2026-09-29T17:00:00Z',
                                             'duration_min': 50, 'bank_ids': ids})
    assert t.status_code == 200, t.text
    t = t.json()
    assert t['duration_min'] == 50
    s = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    clock.t = dt.datetime(2026, 9, 29, 15, 10, tzinfo=UTC)
    assert s.post(f'/api/portal/tasks/{t["id"]}/start').json()['deadline'].startswith('2026-09-29T16:00')
    # taymer var, son tarix yoxdur
    t2 = mk_task(admin, ta, ids, duration_min=40, closes_at=None, opens_at='2026-09-29T15:00:00Z').json()
    assert t2['duration_min'] == 45 and t2['closes_at'].startswith('2100')


def test_ksq_online_not_unlimited():
    with pytest.raises(ValidationError):
        SendIn(duration_min=0)
    assert SendIn().duration_min == 45


def test_unlimit_tasks_endpoint(world, clock):
    as_, S = world
    admin, ta, cid, st, ids = setup(world)
    a = mk_task(admin, ta, ids, opens_at='2026-10-01T10:00:00Z', closes_at='2037-06-01T00:00:00Z').json()      # uyğun
    b = mk_task(admin, ta, ids, opens_at='2026-09-20T10:00:00Z', closes_at='2026-09-21T00:00:00Z').json()      # bağlanıb
    c = mk_task(admin, ta, ids, opens_at='2026-10-01T10:00:00Z', closes_at='2037-06-01T00:00:00Z').json()      # KSQ
    d = mk_task(admin, ta, ids, opens_at='2026-08-01T10:00:00Z', closes_at='2037-06-01T00:00:00Z').json()      # keçən il
    with S() as db:
        db.get(OnlineTask, c['id']).kind = 'ksq'
        db.commit()
    r = admin.post('/api/admin/unlimit-tasks', params={'dry': 1}).json()
    assert r['dry'] and r['count'] == 1 and r['tasks'][0]['id'] == a['id']
    with S() as db:
        assert db.get(OnlineTask, a['id']).duration_min == 45            # heç nə dəyişməyib
    r = admin.post('/api/admin/unlimit-tasks', params={'dry': 0}).json()
    assert not r['dry'] and r['count'] == 1
    with S() as db:
        ta_ = db.get(OnlineTask, a['id'])
        assert ta_.duration_min == 0 and is_unlimited(ta_)
        for x in (b, c, d):
            o = db.get(OnlineTask, x['id'])
            assert o.duration_min == 45 and not is_unlimited(o)
    assert admin.post('/api/admin/unlimit-tasks', params={'dry': 0}).json()['count'] == 0       # təkrar – heç nə


def test_tidy_keeps_unlimited(world, clock):
    from app.api.tasks import tidy_tasks
    as_, S = world
    admin, ta, cid, st, ids = setup(world)
    t = _open(admin, ta, ids).json()
    with S() as db:
        tidy_tasks(db.connection())
        db.commit()
        assert db.get(OnlineTask, t['id']).duration_min == 0
