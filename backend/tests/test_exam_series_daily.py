"""Sınaq seriyası: gündə 2 sınaq (per_slot), yenidən köhnəyə (newest_first), «bütün siniflər üçün avtomatik seriya» (auto-all)."""
import datetime as dt

from sqlalchemy import select

from app.api.exam_series import _newest_key, run_series
from app.models import BankFile, BankQuestion, ExamSeries, OnlineTask, TeachingAssignment

from .test_api_portal import clock, setup  # noqa: F401 – clock fixture


def _mk(S, label, held=None, grades=(10,), kind='sinaq', questions=2):
    with S() as db:
        f = BankFile(source_key='p012', lesson=f'{label}.html', label=label, url='http://x/' + label, grades=list(grades), kind=kind,
                     held_on=held, question_count=questions)
        db.add(f)
        db.flush()
        for n in range(questions):
            db.add(BankQuestion(file_id=f.id, n=n + 1, kind='mcq', text={'az': f'{label}: {n}+1=?'}, options=[{'az': '1'}, {'az': '2'}],
                                correct=0, content_hash=f'{label}{n}'))
        db.commit()
        return f.id


def _body(ta, queue, **kw):
    return {'title': 'Gündəlik', 'targets': [{'ta_id': ta}], 'sources': ['p012'], 'auto_new': False, 'queue': queue,
            'period': 'day', 'every': 1, 'open_time': '15:00', 'window_hours': 24, **kw}


def _tick(S, sid):
    """Seriyanın yuvasını işə salır (zaman – yuvadan 1 dəqiqə sonra)."""
    with S() as db:
        s = db.get(ExamSeries, sid)
        at = s.next_at if s.next_at.tzinfo else s.next_at.replace(tzinfo=dt.timezone.utc)
        return run_series(db, at=at + dt.timedelta(minutes=1), only=sid)


def _done(S, sid):
    with S() as db:
        return [d['file_id'] for d in db.get(ExamSeries, sid).done]


def test_per_slot_two_then_next_day(world, clock):
    as_, S = world
    admin, ta, cid, st, ids = setup(world)
    f = [_mk(S, f'S{i}', dt.date(2026, 10, 10 - i)) for i in range(5)]
    s = admin.post('/api/exam-series', json=_body(ta, f, per_slot=2)).json()
    assert s['per_slot'] == 2 and len(s['preview'][0]['labels']) == 2 and len(s['preview'][1]['labels']) == 2
    assert s['preview'][0]['label'] == s['preview'][0]['labels'][0]
    assert _tick(S, s['id']) == 2
    assert _done(S, s['id']) == f[:2]
    assert _tick(S, s['id']) == 2
    assert _done(S, s['id']) == f[:4]
    assert _tick(S, s['id']) == 1                                   # növbədə 1 qalıb


def test_per_slot_default_one(world, clock):
    as_, S = world
    admin, ta, cid, st, ids = setup(world)
    f = [_mk(S, f'S{i}') for i in range(3)]
    s = admin.post('/api/exam-series', json=_body(ta, f)).json()
    assert s['per_slot'] == 1 and not s['newest_first']
    assert _tick(S, s['id']) == 1 and _done(S, s['id']) == f[:1]
    assert admin.post('/api/exam-series', json=_body(ta, f, per_slot=3)).status_code == 422


def test_unsendable_file_not_counted(world, clock):
    as_, S = world
    admin, ta, cid, st, ids = setup(world)
    a = _mk(S, 'A')
    empty = _mk(S, 'E', questions=0)                                # sualı yoxdur – _send / atlanma, say
    b = _mk(S, 'B')
    c = _mk(S, 'C')
    with S() as db:
        db.get(BankFile, empty).question_count = 3                  # saxta say: sual yoxdur → _send None qaytarır
        db.commit()
    s = admin.post('/api/exam-series', json=_body(ta, [a, empty, b, c], per_slot=2)).json()
    assert _tick(S, s['id']) == 2
    assert _done(S, s['id']) == [a, b]


def test_newest_first_order_and_null_last(world, clock):
    as_, S = world
    admin, ta, cid, st, ids = setup(world)
    old = _mk(S, 'old', dt.date(2026, 3, 1))
    new = _mk(S, 'new', dt.date(2026, 10, 5))
    none1 = _mk(S, 'none1')
    mid = _mk(S, 'mid', dt.date(2026, 6, 1))
    none2 = _mk(S, 'none2')
    s = admin.post('/api/exam-series', json=_body(ta, [old, new, none1, mid, none2], newest_first=True)).json()
    assert [q['id'] for q in s['queue']] == [new, mid, old, none2, none1]
    s2 = admin.post('/api/exam-series', json=_body(ta, [old, new, none1], newest_first=False)).json()
    assert [q['id'] for q in s2['queue']] == [old, new, none1]      # seçilmiş sıra


def test_sync_new_places_by_key(world, clock):
    as_, S = world
    admin, ta, cid, st, ids = setup(world)
    old = _mk(S, 'old', dt.date(2026, 3, 1))
    mid = _mk(S, 'mid', dt.date(2026, 6, 1))
    s = admin.post('/api/exam-series', json=_body(ta, [mid, old], newest_first=True, auto_new=True)).json()
    new = _mk(S, 'new', dt.date(2026, 10, 5))
    with S() as db:
        run_series(db, at=dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc), only=s['id'])      # yuva gəlməyib, yalnız sinxron
        assert db.get(ExamSeries, s['id']).queue == [new, mid, old]
    s2 = admin.post('/api/exam-series', json=_body(ta, [mid, old], newest_first=False, auto_new=True)).json()
    new2 = _mk(S, 'new2', dt.date(2026, 10, 6))
    with S() as db:
        run_series(db, at=dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc), only=s2['id'])
        assert db.get(ExamSeries, s2['id']).queue == [mid, old, new2]                         # köhnə davranış – sona


def test_newest_key():
    a = BankFile(id=1, held_on=dt.date(2026, 1, 1))
    b = BankFile(id=2, held_on=dt.date(2026, 5, 1))
    c = BankFile(id=3, held_on=None)
    d = BankFile(id=4, held_on=None)
    assert sorted([a, b, c, d], key=_newest_key) == [b, a, d, c]


def _today():
    from app.api.exam_series import TZ
    from app.models import now
    return now().astimezone(TZ).date()


def _auto(c, **kw):
    r = c.post('/api/exam-series/auto-all', json=kw)
    assert r.status_code == 200, r.text
    return r.json()


def test_auto_all_dry_run_both_spaces(world, clock):
    as_, S = world
    admin, ta, cid, st, ids = setup(world)
    pid = admin.post('/api/classes', json={'name': 'Fərdi X', 'kind': 'adi', 'private': True, 'grade': 10}).json()['id']
    admin.post(f'/api/classes/{pid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 2, 'slots': {}})
    a = _mk(S, 'A', dt.date(2026, 10, 1))
    b = _mk(S, 'B', dt.date(2026, 10, 9))
    _mk(S, 'Other', dt.date(2026, 10, 9), grades=(11,))             # başqa sinif – düşmür
    _mk(S, 'Movzu', kind='movzu')
    yad = as_('yad')
    res = _auto(admin)
    assert res['dry_run'] is True
    by = {x['class_name']: x for x in res['items']}
    assert set(by) == {'X e', 'Fərdi X'}
    assert by['X e']['space'] == 'school' and by['Fərdi X']['space'] == 'private'
    for x in by.values():
        assert x['status'] == 'create' and x['queue_n'] == 2 and x['first'] == ['B', 'A']
    with S() as db:
        assert db.query(ExamSeries).count() == 0                    # dry_run yazmır
    assert _auto(yad)['items'] == []                                # başqa müəllimin dərsi görünmür
    del a, b


def test_auto_all_create_exists_and_given(world, clock):
    as_, S = world
    admin, ta, cid, st, ids = setup(world)
    a = _mk(S, 'A', dt.date(2026, 10, 1))
    b = _mk(S, 'B', dt.date(2026, 10, 9))
    c = _mk(S, 'C', dt.date(2026, 10, 3))
    # B bu sinfə artıq verilib
    with S() as db:
        from app.api.exam_series import _send
        s0 = ExamSeries(created_by=db.scalar(select(TeachingAssignment.teacher_id).where(TeachingAssignment.id == ta)), title='x',
                        subject='Riyaziyyat', targets=[{'ta_id': ta}], sources=['p012'], period='day', every=1, open_time='15:00',
                        window_hours=24, duration_min=0, penalty=0, show_answers='after_close', shuffle=True, auto_new=False,
                        queue=[], done=[], since_file_id=0, next_at=dt.datetime(2030, 1, 1, tzinfo=dt.timezone.utc), active=False)
        db.add(s0)
        db.flush()
        assert _send(db, s0, db.get(BankFile, b), dt.datetime(2026, 10, 20, 12, tzinfo=dt.timezone.utc)) is not None
        db.commit()
    res = _auto(admin)
    assert res['items'][0]['queue_n'] == 2 and res['items'][0]['first'] == ['C', 'A']
    out = _auto(admin, dry_run=False, start=str(_today() - dt.timedelta(days=1)))
    assert len(out['created']) == 1
    sid = out['created'][0]
    with S() as db:
        s = db.get(ExamSeries, sid)
        assert s.per_slot == 2 and s.newest_first and s.period == 'day' and s.window_hours == 0 and s.show_answers == 'teacher' and s.auto_new
        assert s.targets == [{'ta_id': ta}] and s.grade == 10
        assert sorted(s.queue + [d['file_id'] for d in s.done]) == sorted([a, c])      # B növbəyə düşmədi
        assert db.query(OnlineTask).filter_by(kind='sinaq').count() >= 1
    again = _auto(admin, dry_run=False)
    assert again['created'] == [] and again['items'][0]['status'] == 'exists'


def test_auto_all_empty_queue_still_creates(world, clock):
    as_, S = world
    admin, ta, cid, st, ids = setup(world)
    out = _auto(admin, dry_run=False, start=str(_today() - dt.timedelta(days=1)))
    assert len(out['created']) == 1 and out['items'][0]['queue_n'] == 0
    assert admin.get('/api/exam-series').json()[0]['auto_new'] is True


def test_migration_up_down_up():
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    import importlib.util
    import pathlib
    p = next(pathlib.Path(__file__).resolve().parents[1].glob('migrations/versions/f7c1e5a9b3d2_*.py'))
    spec = importlib.util.spec_from_file_location('mig_f7c1', p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert m.down_revision == 'e6b0d4f8a2c5'
    eng = sa.create_engine('sqlite://')
    with eng.begin() as cx:
        cx.execute(sa.text('CREATE TABLE exam_series (id INTEGER PRIMARY KEY, title VARCHAR(200))'))
        cx.execute(sa.text("INSERT INTO exam_series (id, title) VALUES (1, 'a')"))
        cx.execute(sa.text('CREATE TABLE task_attempts (id INTEGER PRIMARY KEY)'))
        ops = Operations(MigrationContext.configure(cx))
        with Operations.context(MigrationContext.configure(cx)):
            def cols():
                return {c['name'] for c in sa.inspect(cx).get_columns('exam_series')}
            m.upgrade()
            assert {'per_slot', 'newest_first'} <= cols() and 'answers_released_at' in {c['name'] for c in sa.inspect(cx).get_columns('task_attempts')}
            m.downgrade()
            assert cols() == {'id', 'title'}
            m.upgrade()
            assert {'per_slot', 'newest_first'} <= cols() and 'answers_released_at' in {c['name'] for c in sa.inspect(cx).get_columns('task_attempts')}
            assert cx.execute(sa.text('SELECT per_slot, newest_first FROM exam_series')).one() == (None, None)
        del ops


def test_teacher_mode_review_released_by_teacher(world, clock):
    from .test_api_portal import mk_task, student_client
    admin, ta, cid, st, ids = setup(world)
    t = mk_task(admin, ta, ids, show_answers='teacher').json()
    clock.t = dt.datetime(2026, 9, 29, 15, 40, tzinfo=dt.timezone.utc)
    cl = [student_client(x['portal_code'], x['initial_pin']) for x in st[:2]]
    for c in cl:
        c.post(f'/api/portal/tasks/{t["id"]}/start')
        assert c.post(f'/api/portal/tasks/{t["id"]}/submit', json={'answers': {}}).status_code == 200
    clock.t = dt.datetime(2026, 9, 29, 17, 0, tzinfo=dt.timezone.utc)       # bağlandıqdan sonra da
    row = cl[0].get('/api/portal/tasks').json()[0]
    assert row['result']['pct'] is not None and row['result']['total'] == 3 and row['can_review'] is False   # bal görünür
    assert cl[0].get(f'/api/portal/tasks/{t["id"]}/review').status_code == 403
    r = admin.post(f'/api/tasks/{ta}/{t["id"]}/release-answers', json={'student_ids': [st[0]['id'], st[2]['id']]}).json()
    assert r['released'] == 1 and r['not_submitted'] == [st[2]['full_name']]     # təhvil verməmişə olmur
    assert cl[0].get(f'/api/portal/tasks/{t["id"]}/review').status_code == 200
    assert cl[1].get(f'/api/portal/tasks/{t["id"]}/review').status_code == 403   # başqa şagird hələ yox
    rows = {x['student_id']: x for x in admin.get(f'/api/tasks/{ta}/{t["id"]}').json()['rows']}
    assert rows[st[0]['id']]['answers_released_at'] and not rows[st[1]['id']]['answers_released_at']
    w = admin.request('DELETE', f'/api/tasks/{ta}/{t["id"]}/release-answers', json={'student_ids': [st[0]['id']]}).json()
    assert w['withdrawn'] == 1
    assert cl[0].get(f'/api/portal/tasks/{t["id"]}/review').status_code == 403
    assert admin.post(f'/api/tasks/{ta}/{t["id"]}/release-answers').json()['released'] == 2     # boş body – hamısı


def test_teacher_mode_batch_release(world, clock):
    as_, S = world
    admin, ta, cid, st, ids = setup(world)
    f = _mk(S, 'A')
    s = admin.post('/api/exam-series', json=_body(ta, [f], show_answers='teacher', window_hours=0)).json()
    _tick(S, s['id'])
    with S() as db:
        t = db.scalars(select(OnlineTask).where(OnlineTask.kind == 'sinaq')).first()
        assert t.show_answers == 'teacher'
        bid = t.batch_id
    assert admin.post(f'/api/exams-online/{bid}/release-answers').json()['released'] == 0       # hələ heç kim təhvil verməyib


def test_past_start_backfill_unlimited(world, clock):
    from app.api.exam_series import TZ
    as_, S = world
    admin, ta, cid, st, ids = setup(world)
    f = [_mk(S, f'S{i}', dt.date(2026, 10, 20 - i)) for i in range(6)]
    start = _today() - dt.timedelta(days=2)
    s = admin.post('/api/exam-series', json=_body(ta, f, per_slot=2, window_hours=0, start=str(start))).json()
    n = len(s['done'])
    assert n in (4, 6)                                              # 2 keçmiş gün + (bu gün 15:00 keçibsə) bu gün; hər yuvada 2
    assert [d['file_id'] for d in s['done']] == f[:n]               # növbə sırası ilə
    with S() as db:
        opens = sorted(t.opens_at if t.opens_at.tzinfo else t.opens_at.replace(tzinfo=dt.timezone.utc)
                       for t in db.scalars(select(OnlineTask).where(OnlineTask.kind == 'sinaq')))
        assert {o.astimezone(TZ).strftime('%H:%M') for o in opens} == {'15:00'}
        assert opens[0].astimezone(TZ).date() == start and len(opens) == n


def test_past_start_limited_no_backfill_and_too_old(world, clock):
    as_, S = world
    admin, ta, cid, st, ids = setup(world)
    f = [_mk(S, f'S{i}') for i in range(4)]
    start = _today() - dt.timedelta(days=2)
    s = admin.post('/api/exam-series', json=_body(ta, f, per_slot=2, window_hours=24, start=str(start))).json()
    assert len(s['done']) <= 2                                       # müddətli – keçmiş yuvalar doldurulmur
    old = _today() - dt.timedelta(days=15)
    assert admin.post('/api/exam-series', json=_body(ta, f, window_hours=0, start=str(old))).status_code == 422
    assert admin.post('/api/exam-series/auto-all', json={'start': str(old)}).status_code == 422


def test_auto_all_open_now_and_defaults(world, clock):
    as_, S = world
    admin, ta, cid, st, ids = setup(world)
    for i in range(6):
        _mk(S, f'S{i}', dt.date(2026, 10, 20 - i))
    st_ = str(_today() - dt.timedelta(days=1))
    r = _auto(admin, start=st_)
    assert r['items'][0]['open_now'] in (2, 4)                       # dünən + (bu gün 15:00 keçibsə) bu gün
    out = _auto(admin, dry_run=False, start=st_)
    with S() as db:
        s = db.get(ExamSeries, out['created'][0])
        assert len(s.done) == r['items'][0]['open_now'] and s.show_answers == 'teacher' and s.window_hours == 0
