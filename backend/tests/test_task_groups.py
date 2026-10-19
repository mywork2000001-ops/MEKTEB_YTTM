"""Test qrupları (app/task_groups.py): təkrar göndərişlər bir qrup; mənbə siyahısı növlərə ayrılır; yazılı iş qrupun birləşməsinə."""
import datetime as dt
from types import SimpleNamespace as NS

from app.models import OnlineTask, PlanLesson
from app.task_groups import grade_hint, group_tasks

from .test_api_portal import mk_task, setup

D = dt.datetime(2026, 10, 1, 9, 0, tzinfo=dt.timezone.utc)


def T(id, *, kind='movzu', pl=5, batch=None, ids=None, qs=(1, 2), title='T', day=0, ta=1):
    return NS(id=id, assignment_id=ta, kind=kind, plan_lesson_id=pl, batch_id=batch, student_ids=ids, title=title,
              opens_at=D + dt.timedelta(days=day), questions=[{'bank_id': q, 'text': {'az': str(q)}} for q in qs])


def test_grade_hint():
    assert grade_hint('OTK … №1 (IX sinif)') == 9 and grade_hint('Sınaq (XI sinif, A)') == 11
    assert grade_hint('Sınaq (9-cu sinif)') == 9 and grade_hint('Mövzu 5') is None


def test_group_resends_and_split_by_questions():
    ts = [T(1, day=0), T(2, ids=[1, 2], day=1), T(3, ids=[2, 3], day=2), T(4, qs=(7, 8), title='P0010', day=1)]
    gs = {g['main_task_id']: g for g in group_tasks(ts, submitted={1: 5, 2: 1, 3: 2})}
    assert set(gs) == {1, 4}                                          # eyni mövzuya fərqli suallı test – ayrı qrup
    g = gs[1]
    assert g['sends'] == 3 and g['task_ids'] == [1, 2, 3] and g['students'] == 'all' and g['submitted'] == 8
    assert g['first_opens_at'] == D and g['last_opens_at'] == D + dt.timedelta(days=2) and g['student_ids'] is None


def test_group_main_prefers_all_and_union_students():
    gs = group_tasks([T(1, ids=[1], day=0), T(2, ids=[2, 3], day=1)])
    assert gs[0]['main_task_id'] == 1 and gs[0]['students'] == 3 and gs[0]['student_ids'] == [1, 2, 3]
    gs = group_tasks([T(1, ids=[1], day=0), T(2, day=3)])
    assert gs[0]['main_task_id'] == 2 and gs[0]['students'] == 'all'


def test_group_sinaq_by_batch_and_other_class():
    ts = [T(1, kind='sinaq', pl=None, batch=9, qs=(1,)), T(2, kind='sinaq', pl=None, batch=9, qs=(2,), ids=[1]),
          T(3, kind='sinaq', pl=None, batch=10, qs=(1,)), T(4, ta=2), T(5, ta=1)]
    gs = group_tasks(ts)
    assert sorted(len(g['task_ids']) for g in gs) == [1, 1, 1, 2]     # batch 9 (2 göndəriş), batch 10, mövzu ta=2, mövzu ta=1
    # bank_id-siz suallar: mətnin sha1-i ilə eyni imza
    a, b = T(1, qs=()), T(2, qs=())
    a.questions = b.questions = [{'text': {'az': 'x'}}]
    assert len(group_tasks([a, b])) == 1


def _as_movzu(S, task_id, ta, seq):
    with S() as db:
        pl = db.query(PlanLesson).filter_by(assignment_id=ta, seq=seq).one()
        x = db.get(OnlineTask, task_id)
        x.kind, x.batch_id, x.plan_lesson_id = 'movzu', None, pl.id
        db.commit()


def test_sources_and_paper_for_group(world):
    admin, ta, cid, st, ids = setup(world)
    _, S = world
    t = mk_task(admin, ta, ids, title='Mövzu testi').json()
    _as_movzu(S, t['id'], ta, 5)
    body = {'target_ta_id': ta, 'opens_at': '2099-09-30T08:00:00Z', 'closes_at': '2099-09-30T09:00:00Z'}
    c1 = admin.post(f'/api/tasks/{ta}/{t["id"]}/copy', json={**body, 'student_ids': [st[0]['id']]}).json()
    c2 = admin.post(f'/api/tasks/{ta}/{t["id"]}/copy', json={**body, 'student_ids': [st[1]['id']]}).json()
    c3 = admin.post(f'/api/tasks/{ta}/{t["id"]}/copy', json={**body, 'student_ids': [st[0]['id'], st[2]['id']]}).json()
    assert c1['kind'] == 'movzu'
    sources = admin.get(f'/api/paper-exams/{ta}/sources').json()
    assert set(sources) == {'movzu', 'sinaq', 'extra'} and sources['sinaq'] == [] and sources['extra'] == []
    assert len(sources['movzu']) == 1
    g = sources['movzu'][0]
    assert g['sends'] == 4 and g['main_task_id'] == t['id'] and g['seq'] == 5 and g['students'] == 'all' and g['has_paper'] is False
    assert sorted(g['task_ids']) == sorted([t['id'], c1['id'], c2['id'], c3['id']]) and g['grade_mismatch'] is False
    # /api/tasks/mine – group_key / group_sends
    mine = [r for r in admin.get('/api/tasks/mine').json() if r['id'] in g['task_ids']]
    assert len(mine) == 4 and len({r['group_key'] for r in mine}) == 1 and all(r['group_sends'] == 4 for r in mine)
    # yazılı iş qrupun hər hansı üzvü ilə: bütün sinif (biri «hamı»), əsas tapşırığa bağlı
    r = admin.post(f'/api/paper-exams/{ta}', json={'task_id': c2['id'], 'date': '2026-10-05'})
    assert r.status_code == 200, r.text
    assert r.json()['exam']['online_task_id'] == t['id'] and r.json()['variants'] == 3
    for tid in (t['id'], c1['id'], c3['id']):                         # artıq var – qrupun bütün tapşırıqları üzrə
        assert admin.post(f'/api/paper-exams/{ta}', json={'task_id': tid}).status_code == 409
    assert admin.get(f'/api/paper-exams/{ta}/sources').json()['movzu'][0]['has_paper'] is True


def test_paper_only_union_of_subgroups(world):
    admin, ta, cid, st, ids = setup(world)
    _, S = world
    t = mk_task(admin, ta, ids, title='Alt-qrup testi', student_ids=[st[0]['id']]).json()
    _as_movzu(S, t['id'], ta, 6)
    body = {'target_ta_id': ta, 'opens_at': '2099-09-30T08:00:00Z', 'closes_at': '2099-09-30T09:00:00Z'}
    c = admin.post(f'/api/tasks/{ta}/{t["id"]}/copy', json={**body, 'student_ids': [st[2]['id']]}).json()
    g = admin.get(f'/api/paper-exams/{ta}/sources').json()['movzu'][0]
    assert g['sends'] == 2 and g['students'] == 2
    r = admin.post(f'/api/paper-exams/{ta}', json={'task_id': c['id']}).json()
    assert r['variants'] == 2 and sorted(r['exam']['extra_students']) == sorted([st[0]['id'], st[2]['id']])
