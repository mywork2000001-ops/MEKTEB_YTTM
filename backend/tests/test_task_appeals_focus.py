"""Sınaq: yenidən göndərmə (resend), imtahandan çıxma sayğacı (focus) və sınaq apelyasiyası (task_appeals)."""
import datetime as dt

from app.models import TaskAppeal, TaskAttempt

from .test_api_portal import UTC, clock, mk_task, setup, student_client, as_topic  # noqa: F401


def _solve(s, tid, wrong=True):
    """Şagird başlayır; '2+2=?' sualına səhv (0), '5·2=?'-a düz (0) cavab verir; vaxt bitəndən sonra təhvil."""
    r = s.post(f'/api/portal/tasks/{tid}/start').json()
    by = {q['text']['az']: q['index'] for q in r['questions']}
    s.put(f'/api/portal/tasks/{tid}/answers', json={'answers': {str(by['2+2=?']): 0 if wrong else 1, str(by['5·2=?']): 0}})
    s.post(f'/api/portal/tasks/{tid}/submit', json={'answers': {}})
    return by


def test_resend_to_selected_students(world, clock):
    admin, ta, cid, st, ids = setup(world)
    t = mk_task(admin, ta, ids).json()
    s0 = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    s1 = student_client(st[1]['portal_code'], st[1]['initial_pin'])
    clock.t = dt.datetime(2026, 9, 29, 15, 10, tzinfo=UTC)
    _solve(s0, t['id'])
    clock.t = dt.datetime(2026, 9, 30, 9, 0, tzinfo=UTC)
    r = admin.post(f'/api/tasks/{ta}/{t["id"]}/resend', json={'student_ids': [st[0]['id']]})
    assert r.status_code == 200
    new = r.json()
    assert new['id'] != t['id'] and new['title'].endswith('(təkrar)') and new['student_ids'] == [st[0]['id']]
    assert new['duration_min'] == 45 and new['questions'] == 3 and new['batch_id'] == t['batch_id']
    # yeni tapşırıq yalnız seçilən şagirdə görünür, köhnə nəticə qalır
    assert new['id'] in [x['id'] for x in s0.get('/api/portal/tasks').json()]
    assert new['id'] not in [x['id'] for x in s1.get('/api/portal/tasks').json()]
    assert s0.post(f'/api/portal/tasks/{new["id"]}/start').status_code == 200
    res = admin.get(f'/api/tasks/{ta}/{t["id"]}').json()
    assert next(x for x in res['rows'] if x['student_id'] == st[0]['id'])['status'] == 'təhvil verib'
    # son tarix yox / pəncərə
    assert new['closes_at'].startswith('2100')
    w = admin.post(f'/api/tasks/{ta}/{t["id"]}/resend', json={'student_ids': [st[1]['id']], 'window_hours': 6}).json()
    assert w['closes_at'].startswith('2026-09-30T15:00')
    # xətalar: boş siyahı, kənar şagird, KSQ/mövzu, başqa müəllim
    assert admin.post(f'/api/tasks/{ta}/{t["id"]}/resend', json={'student_ids': []}).status_code == 422
    assert admin.post(f'/api/tasks/{ta}/{t["id"]}/resend', json={'student_ids': [999999]}).status_code == 400
    as_topic(world[1], t['id'])
    assert admin.post(f'/api/tasks/{ta}/{t["id"]}/resend', json={'student_ids': [st[0]['id']]}).status_code == 400
    other = world[0]('ilqar')
    assert other.post(f'/api/tasks/{ta}/{new["id"]}/resend', json={'student_ids': [st[0]['id']]}).status_code == 404


def test_focus_counter(world, clock):
    admin, ta, cid, st, ids = setup(world)
    t = mk_task(admin, ta, ids).json()
    s0 = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    s1 = student_client(st[1]['portal_code'], st[1]['initial_pin'])
    clock.t = dt.datetime(2026, 9, 29, 15, 10, tzinfo=UTC)
    assert s0.post(f'/api/portal/tasks/{t["id"]}/focus', json={'n': 1, 'ms': 10}).status_code == 404   # hələ başlamayıb
    s0.post(f'/api/portal/tasks/{t["id"]}/start')
    assert s0.post(f'/api/portal/tasks/{t["id"]}/focus', json={'n': 2, 'ms': 5000}).json()['n'] == 2
    assert s0.post(f'/api/portal/tasks/{t["id"]}/focus', json={'n': 1, 'ms': 100}).json() == {'n': 2, 'ms': 5000, 'closed': False}  # azalmır
    assert s1.post(f'/api/portal/tasks/{t["id"]}/focus', json={'n': 9, 'ms': 1}).status_code == 404     # başqasının cəhdi yox
    rows = admin.get(f'/api/tasks/{ta}/{t["id"]}').json()['rows']
    assert next(x for x in rows if x['student_id'] == st[0]['id'])['focus'] == {'n': 2, 'ms': 5000}
    assert next(x for x in rows if x['student_id'] == st[1]['id'])['focus'] is None
    s0.post(f'/api/portal/tasks/{t["id"]}/submit', json={'answers': {}})
    r = s0.post(f'/api/portal/tasks/{t["id"]}/focus', json={'n': 7, 'ms': 9999}).json()
    assert r == {'n': 2, 'ms': 5000, 'closed': True}                                                     # təhvildən sonra sayılmır


def _appeal_setup(world, clock):
    admin, ta, cid, st, ids = setup(world)
    t = mk_task(admin, ta, ids).json()
    clock.t = dt.datetime(2026, 9, 29, 15, 10, tzinfo=UTC)
    ss = [student_client(x['portal_code'], x['initial_pin']) for x in st]
    by = [_solve(s, t['id']) for s in ss[:2]]                    # ikisi də '2+2=?'-a səhv (0), '5·2=?'-a düz
    return admin, ta, st, t, ss, by


def test_appeal_permissions(world, clock):
    admin, ta, st, t, ss, by = _appeal_setup(world, clock)
    qi = by[0]['2+2=?']
    url = f'/api/portal/tasks/{t["id"]}/appeals'
    assert ss[0].post(url, json={'q_index': qi, 'reason': 'Cavabım düzdür'}).status_code == 403     # cavablar hələ açılmayıb (16:00-dan əvvəl)
    clock.t = dt.datetime(2026, 9, 29, 16, 5, tzinfo=UTC)
    assert ss[2].post(url, json={'q_index': qi, 'reason': 'Cavabım düzdür'}).status_code == 403     # təhvil verməyib
    assert ss[0].post(url, json={'q_index': qi, 'reason': 'qs'}).status_code == 422                 # qısa səbəb
    assert ss[0].post(url, json={'q_index': 99, 'reason': 'Cavabım düzdür'}).status_code == 404
    ok = ss[0].post(url, json={'q_index': qi, 'reason': 'Cavabım düzdür'})
    assert ok.status_code == 200 and ok.json()['status'] == 'open'
    assert ss[0].post(url, json={'q_index': qi, 'reason': 'Yenə cəhd edirəm'}).status_code == 409   # təkrar
    rev = ss[0].get(f'/api/portal/tasks/{t["id"]}/review').json()
    assert rev['can_appeal'] is True
    assert next(q for q in rev['questions'] if q['index'] == qi)['appeal']['status'] == 'open'
    clock.t = dt.datetime(2026, 10, 6, 16, 1, tzinfo=UTC)                                           # 7 gün keçdi
    assert ss[1].post(url, json={'q_index': qi, 'reason': 'Gec gəldim, amma düzdür'}).status_code == 400
    assert ss[1].get(f'/api/portal/tasks/{t["id"]}/review').json()['can_appeal'] is False


def test_appeal_inbox_accept_and_apply_all(world, clock):
    admin, ta, st, t, ss, by = _appeal_setup(world, clock)
    clock.t = dt.datetime(2026, 9, 29, 16, 5, tzinfo=UTC)
    qi = by[0]['2+2=?']
    ap = ss[0].post(f'/api/portal/tasks/{t["id"]}/appeals', json={'q_index': qi, 'reason': 'Cavabım düzdür'}).json()['id']
    # müəllim qutusu və sayğac
    assert admin.get('/api/exam-appeals/open-count').json()['open'] == 1
    card = next(x for x in admin.get('/api/exam-appeals/inbox').json()['appeals'] if x['kind'] == 'sinaq')
    assert card['id'] == ap and card['full_name'] == st[0]['full_name'] and card['my_answer'] == 'A' and card['key_now'] == 'B'
    assert card['question']['text']['az'] == '2+2=?' and card['exam']['title'] == t['title']
    # rədd — cavabsız 400
    assert admin.put(f'/api/task-appeals/{ap}', json={'status': 'rejected'}).status_code == 400
    assert admin.put(f'/api/task-appeals/{ap}', json={'status': 'rejected', 'apply_all': True, 'teacher_reply': 'yox'}).status_code == 400
    # başqa müəllim — 404
    assert world[0]('ilqar').put(f'/api/task-appeals/{ap}', json={'status': 'accepted'}).status_code == 404
    before = [x for x in admin.get(f'/api/tasks/{ta}/{t["id"]}').json()['rows'] if x['student_id'] == st[0]['id']][0]['pct']
    r = admin.put(f'/api/task-appeals/{ap}', json={'status': 'accepted'})
    assert r.status_code == 200 and len(r.json()['changes']) == 1
    rows = {x['student_id']: x for x in admin.get(f'/api/tasks/{ta}/{t["id"]}').json()['rows']}
    assert rows[st[0]['id']]['pct'] > before and rows[st[0]['id']]['correct'] == 2
    assert rows[st[1]['id']]['correct'] == 1                                  # apply_all olmadan başqası dəyişmir
    assert admin.get('/api/exam-appeals/open-count').json()['open'] == 0
    # şagird qərarı görür
    rev = ss[0].get(f'/api/portal/tasks/{t["id"]}/review').json()
    assert next(q for q in rev['questions'] if q['index'] == qi)['appeal']['status'] == 'accepted'
    assert any(n['key'] == f'tap-{ap}' for n in ss[0].get('/api/portal/notifications').json())
    # ikinci şagird: qəbul + hamıya tətbiq
    ap2 = ss[1].post(f'/api/portal/tasks/{t["id"]}/appeals', json={'q_index': by[1]['2+2=?'], 'reason': 'Açar səhvdir'}).json()['id']
    r2 = admin.put(f'/api/task-appeals/{ap2}', json={'status': 'accepted', 'apply_all': True, 'teacher_reply': 'Açar düzəldi'}).json()
    assert r2['changes'][0]['full_name']
    rows = {x['student_id']: x for x in admin.get(f'/api/tasks/{ta}/{t["id"]}').json()['rows']}
    assert rows[st[1]['id']]['correct'] == 2
    # cavabsız şagird (ss[2] heç başlamayıb) toxunulmaz
    assert rows[st[2]['id']]['correct'] is None


def test_apply_all_covers_every_attempt_in_batch(world, clock):
    """apply_all: eyni paketin başqa tapşırığındakı (təkrar) cəhdlər də, cavab verənlər üçün."""
    admin, ta, st, t, ss, by = _appeal_setup(world, clock)
    clock.t = dt.datetime(2026, 9, 29, 16, 5, tzinfo=UTC)
    rr = admin.post(f'/api/tasks/{ta}/{t["id"]}/resend', json={'student_ids': [st[2]['id']], 'window_hours': 48})
    assert rr.status_code == 200, rr.text
    new = rr.json()
    clock.t = dt.datetime(2026, 9, 29, 16, 10, tzinfo=UTC)
    by2 = _solve(ss[2], new['id'])
    clock.t = dt.datetime(2026, 10, 2, 9, 0, tzinfo=UTC)
    ap = ss[0].post(f'/api/portal/tasks/{t["id"]}/appeals', json={'q_index': by[0]['2+2=?'], 'reason': 'Açar səhvdir'}).json()['id']
    assert admin.put(f'/api/task-appeals/{ap}', json={'status': 'accepted', 'apply_all': True}).status_code == 200
    from app.models import OnlineTask
    S = world[1]
    with S() as db:
        a = db.query(TaskAttempt).filter_by(task_id=new['id'], student_id=st[2]['id']).one()
        assert (a.manual or {}).get(str(by2['2+2=?'])) is True and a.correct == 2
        assert db.query(TaskAppeal).count() == 1 and db.get(OnlineTask, new['id']).batch_id == t['batch_id']
