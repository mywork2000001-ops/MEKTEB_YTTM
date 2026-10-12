"""Səliqə (docs/test-bolmeleri-seliqe-promtu.md): bütün siniflərin mövzu testləri bir siyahıda, reytinqdə iştirak qaydası,
sınaqda «Canlı izlə» faizi jurnalla eyni (cərimə ilə, qiymətsiz), sınaq siyahısı toplu sorğu ilə eyni nəticə verir."""
import datetime as dt

from app.test_stats import rating

from .test_api_exam_audit import ALL_OK, _answer, _two_classes
from .test_api_portal import UTC, as_topic, clock, mk_task, setup  # noqa: F401 – clock fixture


def test_my_tasks_all_classes(world, clock):
    admin, ta, cid, st, ids = setup(world)
    t = mk_task(admin, ta, ids).json()
    as_topic(world[1], t['id'])
    mine = admin.get('/api/tasks/mine').json()
    assert [(x['id'], x['class_name'], x['ta_id'], x['submitted']) for x in mine] == [(t['id'], 'X e', ta, 0)]
    assert admin.get('/api/tasks/mine', params={'archived': True}).json() == []
    assert world[0]('ilqar').get('/api/tasks/mine').json() == []          # başqa müəllimin testi görünmür


def _row(sid, unit, status, pct=None):
    return {'student_id': sid, 'full_name': f'Ş{sid}', 'class_name': 'X e', 'ta_id': 1, 'visible': True, 'unit': unit,
            'kind': 'movzu', 'title': unit, 'date': dt.date(2026, 10, int(unit[1:])), 'topic': None, 'task_id': 1,
            'status': status, 'pct': pct}


def test_rating_needs_40_participation():
    """Reytinqdə yer – testlərin ≥ 40 %-ni yazana (12.10.2026): 4-dən 1-ni 100% yazan yersiz, 4-dən 2-ni yazan reytinqdədir."""
    rows = [_row(1, 't1', 'yazıb', 100), _row(1, 't2', 'yazmayıb'), _row(1, 't3', 'yazmayıb'), _row(1, 't4', 'yazmayıb'),
            _row(2, 't1', 'yazıb', 60), _row(2, 't2', 'yazıb', 70), _row(2, 't3', 'yazıb', 65), _row(2, 't4', 'yazmayıb'),
            _row(4, 't1', 'yazıb', 100), _row(4, 't2', 'yazıb', 100), _row(4, 't3', 'yazmayıb'), _row(4, 't4', 'yazmayıb'),
            _row(3, 't1', 'yazıb', 50), _row(3, 't2', 'yazıb', 50), _row(3, 't3', 'yazıb', 50), _row(3, 't4', 'yazıb', 50)]
    rt = {r['student_id']: r for r in rating({'tests': [], 'rows': rows})['rows']}
    assert (rt[4]['place_all'], rt[2]['place_all'], rt[3]['place_all'], rt[1]['place_all']) == (1, 2, 3, None)
    assert rt[1]['ranked'] is False and rt[1]['avg_pct'] == 100.0 and rt[2]['place_class'] == 2


def test_live_watch_for_exam_matches_journal(world, clock, monkeypatch):
    admin, ta, ta_c, st, xs, bid, tid = _two_classes(world, clock, monkeypatch, penalty=4)
    clock.t = dt.datetime(2026, 9, 29, 11, 30, tzinfo=UTC)
    _answer(st[0], tid[ta], {**ALL_OK, 'x²=9, x>0': '4'})                      # 2 düz, 1 səhv → 58,3%
    w = next(r for r in admin.get(f'/api/tasks/{ta}/{tid[ta]}').json()['rows'] if r['student_id'] == st[0]['id'])
    assert (w['pct'], w['grade']) == (33.8, None)
    ex = admin.get('/api/exams-online').json()
    assert [(x['id'], x['classes'], x['wrote'], x['avg_pct'], x['state']) for x in ex] == [(bid, ['X e', 'X c'], 1, 33.8, 'açıqdır')]
    assert ex[0]['ta_ids'] == sorted([ta, ta_c])
    assert world[0]('yad').get('/api/exams-online').json() == []


def test_tidy_old_tests(world, clock):
    """Miqrasiya: təkrar surət (heç kim başlamayıb) silinir, nəticəsi olan qalır; açıq testin müddəti 45 dəqiqəyə qalxır."""
    from app.api.tasks import tidy_tasks
    from app.models import OnlineTask, TestBatch
    from .test_api_portal import student_client
    admin, ta, cid, st, ids = setup(world)
    S = world[1]
    a = mk_task(admin, ta, ids).json()                                        # 15:00–16:00
    b = mk_task(admin, ta, ids).json()                                        # eyni test ikinci dəfə (təsadüfən)
    c = mk_task(admin, ta, ids).json()
    with S() as db:                                                           # köhnə qayda ilə yaradılmış kimi – 20 dəq
        for x in (a, b, c):
            db.get(OnlineTask, x['id']).duration_min = 20
        db.commit()
    clock.t = dt.datetime(2026, 9, 29, 15, 10, tzinfo=UTC)
    s = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    s.post(f'/api/portal/tasks/{b["id"]}/start')                               # b-də nəticə var – silinməməlidir
    with S() as db:
        out = tidy_tasks(db.connection(), dt.datetime(2026, 9, 29, 15, 10, tzinfo=UTC))
        db.commit()
        left = {t.id: t.duration_min for t in db.query(OnlineTask)}
        assert out['deleted'] == 2 and set(left) == {b['id']} and left[b['id']] == 45
        assert db.query(TestBatch).count() == 1                               # silinənlərin boş paketi də getdi
