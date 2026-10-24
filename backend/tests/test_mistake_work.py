"""«Səhvlər üzərində iş» (metodik audit M3): yalnız səhv/boş suallar, bir dəfə, jurnala yazılmır, yalnız mövzu testi."""
import datetime as dt

from sqlalchemy import func, select

from app.models import Mark, OnlineTask, TaskAttempt

from .test_api_portal import UTC, as_topic, clock, mk_task, setup, student_client  # noqa: F401


def _solve(s, tid, right_text_to_val: dict):
    """Testi başlat, verilən cavabları yaz, təhvil ver."""
    r = s.post(f'/api/portal/tasks/{tid}/start').json()
    by_text = {q['text']['az']: q['index'] for q in r['questions']}
    ans = {str(by_text[t]): v for t, v in right_text_to_val.items()}
    assert s.post(f'/api/portal/tasks/{tid}/submit', json={'answers': ans}).status_code == 200


def _topic_task(world, clock, **kw):
    as_, S = world
    admin, ta, cid, st, ids = setup(world)
    t = mk_task(admin, ta, ids, closes_at=None, duration_min=0, show_answers='after_submit', **kw).json()
    as_topic(S, t['id'])
    clock.t = dt.datetime(2026, 9, 29, 15, 30, tzinfo=UTC)
    s = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    return S, admin, ta, st, t, s


def test_created_only_after_submit_and_only_wrong(world, clock):
    S, admin, ta, st, t, s = _topic_task(world, clock)
    tid = t['id']
    assert s.post(f'/api/portal/tasks/{tid}/mistake-work').status_code == 409          # hələ başlamayıb
    _solve(s, tid, {'2+2=?': 1, 'x²=9, x>0': '5'})                                        # 1 düz, 1 səhv, 1 boş
    card = s.get('/api/portal/tasks').json()[0]
    assert card['mistake_work'] == {'allowed': True, 'task_id': None, 'correct': None, 'total': None, 'done': False}
    r = s.post(f'/api/portal/tasks/{tid}/mistake-work')
    assert r.status_code == 200 and r.json()['questions'] == 2
    mid = r.json()['task_id']
    with S() as db:
        x = db.get(OnlineTask, mid)
        assert x.kind == 'sehv' and x.student_ids == [st[0]['id']] and x.show_answers == 'after_submit'
        assert sorted(q['text']['az'] for q in x.questions) == ['5·2=?', 'x²=9, x>0']
    # şagird siyahısında ayrıca sətir yox; əsas kartda düymə vəziyyəti
    lst = s.get('/api/portal/tasks').json()
    assert [c['id'] for c in lst] == [tid] and lst[0]['mistake_work']['task_id'] == mid
    # həll: bir düz, bir səhv
    _solve(s, mid, {'x²=9, x>0': '3', '5·2=?': 1})
    card = s.get('/api/portal/tasks').json()[0]
    assert card['mistake_work'] == {'allowed': False, 'task_id': mid, 'correct': 1, 'total': 2, 'done': True}
    # müəllim: sətirdə nəticə, test siyahısında səhv-işi yoxdur
    rows = {x['student_id']: x for x in admin.get(f'/api/tasks/{ta}/{tid}').json()['rows']}
    assert rows[st[0]['id']]['mistake_work']['correct'] == 1 and rows[st[0]['id']]['mistake_work']['total'] == 2
    assert rows[st[1]['id']]['mistake_work'] is None
    assert [x['id'] for x in admin.get(f'/api/tasks/{ta}').json()] == [tid]
    assert [x['id'] for x in admin.get(f'/api/tasks/{ta}', params={'archived': False}).json()] == [tid]


def test_journal_and_original_unchanged(world, clock):
    S, admin, ta, st, t, s = _topic_task(world, clock)
    tid = t['id']
    _solve(s, tid, {'2+2=?': 1})
    with S() as db:
        a0 = db.scalar(select(TaskAttempt).where(TaskAttempt.task_id == tid))
        before = (a0.correct, a0.total, a0.points, a0.grade)
        marks0 = db.scalar(select(func.count()).select_from(Mark))
    mid = s.post(f'/api/portal/tasks/{tid}/mistake-work').json()['task_id']
    _solve(s, mid, {'x²=9, x>0': '3', '5·2=?': 0})
    from app.task_journal import run_due
    with S() as db:
        run_due(db)
        db.commit()
    with S() as db:
        a1 = db.scalar(select(TaskAttempt).where(TaskAttempt.task_id == tid))
        assert (a1.correct, a1.total, a1.points, a1.grade) == before
        assert db.scalar(select(func.count()).select_from(Mark)) == marks0
        x = db.get(OnlineTask, mid)
        assert x.journal_auto is False and x.journal_done_at is None


def test_second_start_409_three_languages(world, clock):
    S, admin, ta, st, t, s = _topic_task(world, clock)
    tid = t['id']
    _solve(s, tid, {'2+2=?': 1})
    assert s.post(f'/api/portal/tasks/{tid}/mistake-work').status_code == 200
    r = s.post(f'/api/portal/tasks/{tid}/mistake-work')
    assert r.status_code == 409 and 'artıq' in r.json()['detail']
    from app.models import User
    for lang, word in (('ru', 'уже'), ('en', 'already')):
        with S() as db:
            u = db.scalar(select(User).where(User.login == st[0]['portal_code']))
            u.language = lang
            db.commit()
        r = s.post(f'/api/portal/tasks/{tid}/mistake-work')
        assert r.status_code == 409 and word in r.json()['detail']


def test_not_allowed_for_sinaq_kind(world, clock):
    as_, S = world
    admin, ta, cid, st, ids = setup(world)
    t = mk_task(admin, ta, ids, closes_at=None, duration_min=0, show_answers='after_submit').json()   # as_topic yox → sınaq
    clock.t = dt.datetime(2026, 9, 29, 15, 30, tzinfo=UTC)
    s = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    _solve(s, t['id'], {'2+2=?': 0})
    with S() as db:
        assert db.get(OnlineTask, t['id']).kind == 'sinaq'
    assert s.get('/api/portal/tasks').json()[0]['mistake_work'] is None
    assert s.post(f"/api/portal/tasks/{t['id']}/mistake-work").status_code == 409


def test_not_allowed_without_mistakes_or_review(world, clock):
    S, admin, ta, st, t, s = _topic_task(world, clock)
    tid = t['id']
    _solve(s, tid, {'2+2=?': 1, 'x²=9, x>0': '3', '5·2=?': 0})                            # hamısı düz
    assert s.get('/api/portal/tasks').json()[0]['mistake_work'] is None
    assert s.post(f'/api/portal/tasks/{tid}/mistake-work').status_code == 409
    with S() as db:
        assert db.scalar(select(func.count()).select_from(OnlineTask).where(OnlineTask.kind == 'sehv')) == 0


def test_not_allowed_when_answers_hidden(world, clock):
    as_, S = world
    admin, ta, cid, st, ids = setup(world)
    t = mk_task(admin, ta, ids, closes_at=None, duration_min=0, show_answers='never').json()
    as_topic(S, t['id'])
    clock.t = dt.datetime(2026, 9, 29, 15, 30, tzinfo=UTC)
    s = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    _solve(s, t['id'], {'2+2=?': 0})
    assert s.post(f"/api/portal/tasks/{t['id']}/mistake-work").status_code == 409
