"""100 ballıq sistem (docs/yuz-balliq-sistem-promtu.md): bal paylanması (cəmi 100), çətinlik mənbəyi (müəllim → statistika
→ növ), gecəlik statistika, dondurulmuş ballar, sınaqda çəkili cərimə."""
import datetime as dt

from app.domain.scoring import assign_points, difficulty_of, from_stats, question_points
from app.models import BankQuestion, OnlineTask

from .test_api_portal import UTC, clock, mk_task, setup, student_client  # noqa: F401 – clock fixture


def test_points_sum_to_100_and_weights():
    qs = assign_points([{'kind': 'mcq'}, {'kind': 'mcq'}, {'kind': 'open'}])
    assert [q['points'] for q in qs] == [23.5, 23.5, 53.0] and sum(q['points'] for q in qs) == 100
    for n in (1, 3, 7, 25, 40, 100):                       # istənilən say – cəmi dəqiq 100, hər bal ≥ 0,5 və 0,5-ə bölünür
        qs = assign_points([{'kind': 'mcq' if i % 3 else 'open'} for i in range(n)])
        assert sum(q['points'] for q in qs) == 100 and all(q['points'] >= 0.5 and q['points'] * 2 == int(q['points'] * 2) for q in qs)
    hard = assign_points([{'kind': 'mcq', 'difficulty': 'çətin'}, {'kind': 'mcq', 'difficulty': 'asan'}])
    assert hard[0]['points'] > hard[1]['points'] and hard[0]['level_src'] == 'müəllim'
    assert question_points([{'kind': 'mcq'}] * 4) == [25.0] * 4               # köhnə test (bal yoxdur) – bərabər


def test_difficulty_sources():
    assert difficulty_of({'kind': 'open'}) == ('orta', 'növ') and difficulty_of({'kind': 'mcq'}) == ('asan', 'növ')
    assert difficulty_of({'kind': 'mcq', 'difficulty_auto': 'çətin'}) == ('çətin', 'statistika')
    assert difficulty_of({'kind': 'mcq', 'difficulty_auto': 'çətin', 'difficulty': 'asan'}) == ('asan', 'müəllim')
    assert from_stats(9, 0) is None and from_stats(10, 8) == 'asan' and from_stats(10, 5) == 'orta' and from_stats(10, 3) == 'çətin'


def test_task_points_frozen_teacher_override_and_stats(world, clock):
    from app.difficulty import update_difficulty
    admin, ta, cid, st, ids = setup(world)
    S = world[1]
    # müəllim birinci sualı «çətin» seçir (bankdan gələn sual – custom ilə)
    with S() as db:
        q0 = db.get(BankQuestion, ids[0])
        raw = {'bank_id': q0.id, 'source': 'p012', 'lesson': 'ÜSİ-1', 'kind': q0.kind, 'text': q0.text, 'options': q0.options,
               'correct': q0.correct, 'answer': q0.answer, 'image': None, 'explanation': q0.explanation}
    r = admin.post(f'/api/tasks/{ta}', json={'title': 'Çəkili', 'opens_at': '2026-09-29T15:00:00Z', 'closes_at': '2026-09-29T16:00:00Z',
                                            'duration_min': 45, 'bank_ids': ids[1:], 'custom': [
                                                {'kind': 'mcq', 'text': '2+2=?', 'options': ['3', '4'], 'correct': 1, 'raw': raw, 'difficulty': 'çətin'}]})
    assert r.status_code == 200, r.text
    full = admin.get(f'/api/tasks/{ta}/{r.json()["id"]}/full').json()['questions_full']
    pts = {q['text']['az']: (q['points'], q['level'], q['level_src']) for q in full}
    assert pts['2+2=?'][1:] == ('çətin', 'müəllim') and sum(p for p, _, _ in pts.values()) == 100
    # şagird həll edir: bal sualın çəkisinə görə; ekranda sualın balı görünür
    clock.t = dt.datetime(2026, 9, 29, 15, 10, tzinfo=UTC)
    s = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    q = s.post(f'/api/portal/tasks/{r.json()["id"]}/start').json()
    assert all('points' in x for x in q['questions'])
    idx = {x['text']['az']: x['index'] for x in q['questions']}
    sub = s.post(f'/api/portal/tasks/{r.json()["id"]}/submit', json={'answers': {str(idx['2+2=?']): 1}}).json()
    assert sub['pct'] == pts['2+2=?'][0] and sub['points'] == pts['2+2=?'][0]
    # statistika dəyişəndə verilmiş test DƏYİŞMİR (dondurulub), yeni test yeni balla
    with S() as db:
        before = [q['points'] for q in db.get(OnlineTask, r.json()['id']).questions]
        update_difficulty(db)                               # < 10 cavab – statistika hələ çətinlik vermir
        db.get(BankQuestion, ids[2]).diff_auto = 'çətin'    # (məs. 10+ cavabdan sonra gecə işi belə yazıb)
        db.commit()
        assert [q['points'] for q in db.get(OnlineTask, r.json()['id']).questions] == before        # verilmiş test dondurulub
    t2 = mk_task(admin, ta, ids).json()
    with S() as db:
        q3 = next(q for q in db.get(OnlineTask, t2['id']).questions if q['bank_id'] == ids[2])
        assert (q3['level'], q3['level_src']) == ('çətin', 'statistika')


def test_update_difficulty_from_answers(world, clock):
    from app.difficulty import update_difficulty
    admin, ta, cid, st, ids = setup(world)
    S = world[1]
    from app.models import TaskAttempt
    # 5 test × 3 şagird = 15 cavab: «2+2»-ni hamı düz, açıq sualı heç kim düz yazmayıb
    for _ in range(5):
        tt = mk_task(admin, ta, ids).json()
        with S() as db:
            task = db.get(OnlineTask, tt['id'])
            oi = next(i for i, q in enumerate(task.questions) if q['kind'] == 'open')
            mi = next(i for i, q in enumerate(task.questions) if q['bank_id'] == ids[0])
            for s_ in st:
                db.add(TaskAttempt(task_id=task.id, student_id=s_['id'], started_at=clock.t, deadline=clock.t, order=list(range(3)),
                                   answers={str(mi): 1, str(oi): 'yanlış'}, submitted_at=clock.t, correct=1, total=3))
            db.commit()
    with S() as db:
        assert update_difficulty(db) >= 2
        got = {q.id: (q.stat_n, q.stat_ok, q.diff_auto) for q in db.query(BankQuestion).filter(BankQuestion.id.in_(ids))}
        assert got[ids[0]] == (15, 15, 'asan') and got[ids[1]][2] == 'çətin' and got[ids[1]][1] == 0
