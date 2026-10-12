"""Testlər, sınaqlar və nəticələr auditi (docs/test-sinaq-audit-promtu.md): cavab açarının siniflər arası sızmaması,
cərimənin hər yerdə eyni faizi, sınaqda qiymətin göstərilməməsi, sınaq sualının bir sinifdə ayrıca dəyişməməsi."""
import datetime as dt

from app.models import OnlineTask, TeachingAssignment

from .test_api_exams_online import ALL_OK, _answer
from .test_api_portal import UTC, clock, setup, student_client  # noqa: F401 – clock fixture

W1 = {'opens_at': '2026-09-29T11:00:00Z', 'closes_at': '2026-09-29T12:00:00Z'}
W2 = {'opens_at': '2026-09-29T13:00:00Z', 'closes_at': '2026-09-29T15:00:00Z'}


def _two_classes(world, clock, monkeypatch, **kw):
    as_, S = world
    for mod in ('app.api.exams_online', 'app.certificates'):
        monkeypatch.setattr(f'{mod}.now', clock, raising=False)
    admin, ta, cid, st, ids = setup(world)
    xc = admin.post('/api/classes', json={'name': 'X c'}).json()['id']
    admin.post(f'/api/classes/{xc}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 1, 'slots': {}})
    xs = [admin.post('/api/students', json={'full_name': f'X c Şagird{i} oğlu', 'class_id': xc}).json() for i in range(2)]
    with S() as db:
        ta_c = db.query(TeachingAssignment).filter_by(class_id=xc).one().id
    clock.t = dt.datetime(2026, 9, 29, 10, 0, tzinfo=UTC)
    body = {'title': 'Sınaq A', 'bank_ids': ids, 'targets': [{'ta_id': ta, **W1}, {'ta_id': ta_c, **W2}], **kw}
    r = admin.post('/api/exams-online', json=body)
    assert r.status_code == 200, r.text
    bid = r.json()['id']
    with S() as db:
        tid = {t.assignment_id: t.id for t in db.query(OnlineTask).filter_by(batch_id=bid)}
    return admin, ta, ta_c, st, xs, bid, tid


def test_answers_hidden_until_whole_exam_closes(world, clock, monkeypatch):
    """«Sınaq bağlandıqdan sonra»: X e 12:00-da bağlanır, X c 13:00–15:00 yazır – X e şagirdi cavabları 15:00-a qədər görmür."""
    admin, ta, ta_c, st, xs, bid, tid = _two_classes(world, clock, monkeypatch)
    clock.t = dt.datetime(2026, 9, 29, 11, 30, tzinfo=UTC)
    c = _answer(st[0], tid[ta], {**ALL_OK, 'x²=9, x>0': '4'})
    clock.t = dt.datetime(2026, 9, 29, 13, 30, tzinfo=UTC)                     # X e bağlanıb, X c yazır
    assert c.get(f'/api/portal/tasks/{tid[ta]}/review').status_code == 403
    tasks = {x['id']: x for x in c.get('/api/portal/tasks').json()}
    assert tasks[tid[ta]]['can_review'] is False
    res = c.get('/api/portal/results').json()
    assert res['mistakes'] == [] and not res['tasks'][0]['can_review']
    clock.t = dt.datetime(2026, 9, 29, 15, 1, tzinfo=UTC)                      # bütün sınaq bağlanıb
    assert c.get(f'/api/portal/tasks/{tid[ta]}/review').status_code == 200
    assert len(c.get('/api/portal/results').json()['mistakes']) == 1


def test_penalty_pct_same_everywhere_and_no_grade(world, clock, monkeypatch):
    """Cərimə (4 səhv = −1): 2 qapalı düz (47 bal), açıq səhv (53 ÷ 4) → 33,75 → 33,8. Şagird və müəllim hər yerdə eyni faizi görür; sınaqda qiymət yoxdur."""
    admin, ta, ta_c, st, xs, bid, tid = _two_classes(world, clock, monkeypatch, penalty=4)
    clock.t = dt.datetime(2026, 9, 29, 11, 30, tzinfo=UTC)
    c = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    q = c.post(f'/api/portal/tasks/{tid[ta]}/start').json()
    idx = {x['text']['az']: x['index'] for x in q['questions']}
    ans = {**ALL_OK, 'x²=9, x>0': '4'}
    sub = c.post(f'/api/portal/tasks/{tid[ta]}/submit', json={'answers': {str(idx[k]): v for k, v in ans.items()}}).json()
    assert sub['grade'] is None and sub['pct'] == 33.8
    assert next(x for x in c.get('/api/portal/tasks').json() if x['id'] == tid[ta])['result']['grade'] is None
    assert c.get('/api/portal/exams').json()['items'][0]['my_pct'] == 33.8            # hələ açıq – öz faizi
    row = c.get('/api/portal/results').json()['tasks'][0]
    assert (row['pct'], row['grade']) == (33.8, None)
    assert admin.get('/api/exams-online').json()[0]['avg_pct'] == 33.8
    rows = admin.get(f'/api/exams-online/{bid}').json()['rows']
    assert {r['status'] for r in rows if r['class_name'] == 'X c'} == {'gözlənilir'}     # X c hələ yaza bilər
    clock.t = dt.datetime(2026, 9, 29, 15, 1, tzinfo=UTC)
    assert c.get('/api/portal/exams').json()['items'][0]['pct'] == 33.8
    assert admin.get(f'/api/exams-online/{bid}').json()['summary']['avg_pct'] == 33.8


def test_exam_questions_change_in_all_classes_together(world, clock, monkeypatch):
    """Bir sinfin sınaq tapşırığında sualı ayrıca dəyişmək sınaq jurnalını pozurdu (sual sayı fərqli → 500).
    İndi dəyişiklik paketin bütün siniflərinə tətbiq olunur; kimsə başlayıbsa – 409."""
    admin, ta, ta_c, st, xs, bid, tid = _two_classes(world, clock, monkeypatch)
    full = admin.get(f'/api/tasks/{ta_c}/{tid[ta_c]}/full').json()['questions_full']
    extra = {'kind': 'mcq', 'text': '1+1=?', 'options': ['2', '3'], 'correct': 0}
    qs = [{'kind': 'mcq', 'text': 'x', 'options': ['a', 'b'], 'correct': 0, 'raw': q} for q in full] + [extra]
    assert admin.patch(f'/api/tasks/{ta_c}/{tid[ta_c]}', json={'questions': qs}).status_code == 200
    with world[1]() as db:
        assert {len(t.questions) for t in db.query(OnlineTask).filter_by(batch_id=bid)} == {4}
    clock.t = dt.datetime(2026, 9, 29, 11, 30, tzinfo=UTC)
    _answer(st[0], tid[ta], ALL_OK)
    clock.t = dt.datetime(2026, 9, 29, 15, 1, tzinfo=UTC)
    res = admin.get(f'/api/exams-online/{bid}')
    assert res.status_code == 200 and len(res.json()['questions']) == 4
    assert admin.patch(f'/api/tasks/{ta_c}/{tid[ta_c]}', json={'questions': qs[:3]}).status_code == 409


def test_manual_ok_on_blank_answer_is_not_negative_wrong(world, clock, monkeypatch):
    """Boş açıq suala müəllim «düz say» basanda səhv sayı −1 olmamalıdır."""
    admin, ta, ta_c, st, xs, bid, tid = _two_classes(world, clock, monkeypatch)
    clock.t = dt.datetime(2026, 9, 29, 11, 30, tzinfo=UTC)
    _answer(st[0], tid[ta], {'2+2=?': 1, '5·2=?': 0})                          # açıq sual boş
    full = admin.get(f'/api/tasks/{ta}/{tid[ta]}/full').json()['questions_full']
    oi = next(i for i, q in enumerate(full) if q['kind'] == 'open')
    admin.put(f'/api/exams-online/{bid}/attempt/{tid[ta]}/{st[0]["id"]}', json={'index': oi, 'ok': True})
    r = next(x for x in admin.get(f'/api/exams-online/{bid}').json()['rows'] if x['student_id'] == st[0]['id'])
    assert (r['correct'], r['wrong'], r['blank']) == (3, 0, 0)


def test_answer_size_limited_and_double_start_safe(world, clock, monkeypatch):
    admin, ta, ta_c, st, xs, bid, tid = _two_classes(world, clock, monkeypatch)
    clock.t = dt.datetime(2026, 9, 29, 11, 30, tzinfo=UTC)
    c = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    c.post(f'/api/portal/tasks/{tid[ta]}/start')
    assert c.post(f'/api/portal/tasks/{tid[ta]}/start').status_code == 200     # təkrar «başla» – eyni cəhd
    assert c.put(f'/api/portal/tasks/{tid[ta]}/answers', json={'answers': {'1': 'x' * 5000}}).status_code == 422


def test_closed_exam_cache_refreshes_after_manual_check(world, clock, monkeypatch):
    """Bağlanmış sınağın nəticəsi keşlənir (bildirişlər yüngül olsun), amma müəllimin əl ilə yoxlaması dərhal görünür."""
    admin, ta, ta_c, st, xs, bid, tid = _two_classes(world, clock, monkeypatch)
    clock.t = dt.datetime(2026, 9, 29, 11, 30, tzinfo=UTC)
    c = _answer(st[0], tid[ta], {**ALL_OK, 'x²=9, x>0': 'üç'})                  # 2/3
    clock.t = dt.datetime(2026, 9, 29, 15, 1, tzinfo=UTC)
    assert c.get('/api/portal/exams').json()['items'][0]['pct'] == 47.0
    assert c.get('/api/portal/exams').json()['items'][0]['pct'] == 47.0          # keşdən
    full = admin.get(f'/api/tasks/{ta}/{tid[ta]}/full').json()['questions_full']
    oi = next(i for i, q in enumerate(full) if q['kind'] == 'open')
    admin.put(f'/api/exams-online/{bid}/attempt/{tid[ta]}/{st[0]["id"]}', json={'index': oi, 'ok': True})
    assert c.get('/api/portal/exams').json()['items'][0]['pct'] == 100.0


def test_resend_joins_same_exam(world, clock, monkeypatch):
    """Yazmayana «Yenidən göndər» – eyni sınaq (yeni paket yox): siyahıda bir sətir, jurnalda şagird bir dəfə, son cəhdi ilə."""
    admin, ta, ta_c, st, xs, bid, tid = _two_classes(world, clock, monkeypatch)
    clock.t = dt.datetime(2026, 9, 29, 11, 30, tzinfo=UTC)
    _answer(st[0], tid[ta], ALL_OK)
    clock.t = dt.datetime(2026, 9, 29, 12, 30, tzinfo=UTC)                     # X e bağlanıb – st[1] yazmayıb
    r = admin.post(f'/api/tasks/{ta}/{tid[ta]}/copy', json={'target_ta_id': ta, 'student_ids': [st[1]['id']],
                                                           'opens_at': '2026-09-29T12:40:00Z', 'closes_at': '2026-09-29T13:40:00Z'})
    assert r.status_code == 200 and r.json()['batch_id'] == bid
    clock.t = dt.datetime(2026, 9, 29, 13, 0, tzinfo=UTC)
    _answer(st[1], r.json()['id'], ALL_OK)
    assert [x['id'] for x in admin.get('/api/exams-online').json()] == [bid]
    clock.t = dt.datetime(2026, 9, 29, 15, 1, tzinfo=UTC)
    res = admin.get(f'/api/exams-online/{bid}').json()
    mine = [x for x in res['rows'] if x['student_id'] == st[1]['id']]
    assert len(mine) == 1 and mine[0]['status'] == 'yazıb' and mine[0]['task_id'] == r.json()['id']
    assert len([c for c in res['classes'] if c['class_name'] == 'X e']) == 1
    assert res['summary']['students'] == 5                                      # 3 (X e) + 2 (X c), təkrar yox
