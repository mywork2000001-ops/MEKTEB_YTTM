"""Sinif/qrup növləri (bölünmə və tədris qrupu), növ redaktəsi və mövzu icrası (irəliləyiş / geriləmə)."""
import datetime as dt

from app.models import PlanLesson, TeachingAssignment

from .test_api_teaching import SLOTS, setup_class


def _studs(c, cid, n, tag):
    return [c.post('/api/students', json={'full_name': f'{tag} Şagird{i} oğlu', 'class_id': cid}).json()['id']
            for i in range(n)]


def test_split_and_study_groups(world):
    as_, _ = world
    c = as_('admin')
    xe = c.post('/api/classes', json={'name': 'X e'}).json()['id']
    xb = c.post('/api/classes', json={'name': 'X b', 'kind': 'adi'}).json()['id']
    a, b = _studs(c, xe, 2, 'Ee'), _studs(c, xb, 2, 'Bb')
    # bölünmə qrupu: üzvlər yalnız ana sinifdən
    sp = c.post('/api/classes', json={'name': 'X e (riyaziyyat qrupu)', 'kind': 'qrup', 'parent_id': xe}).json()
    assert sp['group_type'] == 'bölünmə'
    assert c.put(f"/api/classes/{sp['id']}/members", json={'student_ids': [a[0], b[0]]}).status_code == 400
    assert c.put(f"/api/classes/{sp['id']}/members", json={'student_ids': [a[0]]}).json() == [a[0]]
    # ana sinif qrup ola bilməz; ana sinif yalnız qrupa
    assert c.post('/api/classes', json={'name': 'Y', 'kind': 'qrup', 'parent_id': sp['id']}).status_code == 400
    assert c.post('/api/classes', json={'name': 'Z', 'kind': 'adi', 'parent_id': xe}).status_code == 400
    # tədris qrupu: ana sinifsiz, üzvlər müxtəlif siniflərdən
    g = c.post('/api/classes', json={'name': 'Olimpiada qrupu', 'kind': 'qrup'}).json()
    assert g['group_type'] == 'tədris'
    assert [x['id'] for x in c.get(f"/api/classes/{g['id']}/candidates", params={'class_id': xb}).json()] == sorted(b)
    assert c.get(f"/api/classes/{sp['id']}/candidates", params={'class_id': xb}).status_code == 400
    assert sorted(c.put(f"/api/classes/{g['id']}/members", json={'student_ids': [a[1], b[1]]}).json()) == sorted([a[1], b[1]])
    det = c.get(f"/api/classes/{g['id']}/members/detail").json()
    assert {x['class_name'] for x in det} == {'X e', 'X b'}
    assert c.get('/api/students', params={'class_id': g['id']}).json().__len__() == 2


def test_study_group_teacher_sees_member_card(world):
    as_, _ = world
    adm, t = as_('admin'), as_('ilqar')
    xb = adm.post('/api/classes', json={'name': 'X b', 'kind': 'adi'}).json()['id']
    sid = _studs(adm, xb, 1, 'Kk')[0]
    g = t.post('/api/classes', json={'name': 'Hazırlıq qrupu', 'kind': 'qrup'}).json()['id']
    t.post(f'/api/classes/{g}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 1, 'slots': {'0': [7]}})
    assert t.get(f'/api/students/{sid}/contacts').status_code == 403       # hələ üzv deyil
    assert t.put(f'/api/classes/{g}/members', json={'student_ids': [sid]}).status_code == 200
    assert t.get(f'/api/students/{sid}/contacts').status_code == 200


def test_class_kind_and_bells_edit(world):
    as_, _ = world
    c = as_('admin')
    cid = c.post('/api/classes', json={'name': 'XI peşə sinfi', 'kind': 'TOM'}).json()['id']
    r = c.patch(f'/api/classes/{cid}', json={'kind': 'adi', 'bells': {'0': '08:00–08:45', '1': ' ', 'x': 'y'}}).json()
    assert r['kind'] == 'adi' and r['bells'] == {'0': '08:00–08:45'}
    assert c.patch(f'/api/classes/{cid}', json={'kind': 'qrup'}).status_code == 400
    g = c.post('/api/classes', json={'name': 'G', 'kind': 'qrup'}).json()['id']
    assert c.patch(f'/api/classes/{g}', json={'kind': 'adi'}).status_code == 400


def _dated_plan(world, n=8):
    """Rəsmi tarixlər cədvələ uyğun: 16.09 (2), 21.09, 23.09 (2), 28.09, 30.09 (2)."""
    as_, S = world
    c, ta, studs = setup_class(world, n=0)
    dates = [dt.date(2026, 9, 16)] * 2 + [dt.date(2026, 9, 21)] + [dt.date(2026, 9, 23)] * 2 + \
            [dt.date(2026, 9, 28)] + [dt.date(2026, 9, 30)] * 2
    with S() as db:
        for i in range(n):
            db.add(PlanLesson(assignment_id=ta, seq=i + 1, semester=1, topic=f'Mövzu {i + 1}',
                              section='I bölmə' if i < 4 else 'II bölmə', assessment_type='formativ', date=dates[i]))
        db.commit()
        ids = [p.id for p in db.query(PlanLesson).filter_by(assignment_id=ta).order_by(PlanLesson.seq)]
    return c, ta, studs, ids


def test_progress_marks_journal_and_lag(world, monkeypatch):
    monkeypatch.setattr('app.api.plan.today', lambda: dt.date(2026, 9, 24))
    c, ta, (a, b, d), ids = _dated_plan(world)
    p = c.get(f'/api/plan/{ta}/progress').json()
    assert p['summary']['expected'] == 5 and p['summary']['done'] == 0 and p['summary']['delta'] == -5
    assert p['summary']['delta_weeks'] == round(-5 / 3, 1)
    assert p['topics'][0]['status'] == 'gecikir' and p['topics'][5]['status'] == 'gözlənilir'
    # jurnal: 16.09 3-cü saat – Mövzu 1 keçildi
    monkeypatch.setattr('app.api.journal.today', lambda: dt.date(2026, 9, 24))
    assert c.put(f'/api/journal/{ta}/entry', json={'date': '2026-09-16', 'period': 3}).status_code == 200
    # toplu qeyd: 2–3 keçildi; 4 – qismən (sayılmır); 5 – təkrar (sayılır)
    assert c.post(f'/api/plan/{ta}/topics/bulk', json={'ids': ids[1:3], 'status': 'keçildi', 'done_on': '2026-09-23'}).json()['count'] == 2
    c.put(f'/api/plan/{ta}/topics/{ids[3]}', json={'status': 'qismən'})
    c.put(f'/api/plan/{ta}/topics/{ids[4]}', json={'status': 'təkrar', 'note': 'kəsrlər zəifdir'})
    p = c.get(f'/api/plan/{ta}/progress').json()
    t = {x['seq']: x for x in p['topics']}
    assert t[1]['source'] == 'jurnal' and t[2]['source'] == 'qeyd' and t[2]['delay_days'] == 7
    assert t[3]['delay_days'] == 2                              # rəsmi 21.09, keçildi 23.09
    s = p['summary']
    assert (s['done'], s['partial'], s['review'], s['delta']) == (4, 1, 1, -1)
    assert [(x['section'], x['done'], x['expected']) for x in p['sections']] == [('I bölmə', 3, 4), ('II bölmə', 1, 1)]
    assert p['forecast']['remaining'] == 4
    wk = next(x for x in p['series'] if x['week'] == '2026-09-21')
    assert wk['planned'] == 5 and wk['done'] == 4
    # gələcək tarix olmaz; başqa planın mövzusu 404; qeydi silmək – jurnal yenə sayılır
    assert c.put(f'/api/plan/{ta}/topics/{ids[5]}', json={'status': 'keçildi', 'done_on': '2026-10-05'}).status_code == 400
    assert c.put(f'/api/plan/{ta}/topics/999999', json={'status': 'keçildi'}).status_code == 404
    c.put(f'/api/plan/{ta}/topics/{ids[0]}', json={'status': 'təkrar'})
    assert c.delete(f'/api/plan/{ta}/topics/{ids[0]}').status_code == 200
    p = c.get(f'/api/plan/{ta}/progress').json()
    assert p['topics'][0]['status'] == 'keçildi' and p['topics'][0]['source'] == 'jurnal'
    ov = c.get('/api/my/progress').json()
    assert ov[0]['ta_id'] == ta and ov[0]['done'] == 4 and ov[0]['next']['seq'] == 4


def test_progress_permissions_and_review_in_prompt(world, monkeypatch):
    monkeypatch.setattr('app.api.plan.today', lambda: dt.date(2026, 9, 24))
    as_, S = world
    c, ta, _, ids = _dated_plan(world)
    other = as_('ilqar')
    assert other.get(f'/api/plan/{ta}/progress').status_code == 404
    assert other.put(f'/api/plan/{ta}/topics/{ids[0]}', json={'status': 'keçildi'}).status_code == 404
    c.put(f'/api/plan/{ta}/topics/{ids[0]}', json={'status': 'təkrar'})
    from app.api.lessonplans import _review_topics
    from app.domain.daily_plan import user_prompt
    from app.services import plan_ctx
    with S() as db:
        ctx = plan_ctx(db, db.get(TeachingAssignment, ta))
        rv = _review_topics(db, ctx, 3)
        assert rv == ['№1 Mövzu 1 (mənimsəmə zəifdir)'] and _review_topics(db, ctx, 0) == []
    assert SLOTS  # cədvəl test_api_teaching ilə eynidir
    base = {'school': 'M', 'teacher': 'T', 'subject': 'R', 'class_name': 'X e', 'students': 3, 'date_text': '', 'weekday': '',
            'period': 1, 'minutes': 45, 'semester': 1, 'seq': 4, 'total': 8, 'section': None, 'topic': 'Mövzu 4',
            'standards': [], 'assessment_type': 'formativ', 'assessment': None, 'integration': None, 'resources': None,
            'tt_pages': None, 'tasks': None, 'prev_topic': None, 'prev_homework': None, 'next_topic': None}
    assert 'Təkrar tələb olunan' in user_prompt({**base, 'review_topics': rv})


def test_student_portal_progress(world, monkeypatch):
    from .test_api_portal import student_client
    monkeypatch.setattr('app.api.portal.today', lambda: dt.date(2026, 9, 24))
    monkeypatch.setattr('app.api.plan.today', lambda: dt.date(2026, 9, 24))
    as_, S = world
    c, ta, (a, _, _), ids = _dated_plan(world)
    c.post(f'/api/plan/{ta}/topics/bulk', json={'ids': ids[:2], 'status': 'keçildi', 'done_on': '2026-09-21'})
    c.put(f'/api/plan/{ta}/topics/{ids[2]}', json={'status': 'təkrar', 'note': 'müəllimin gizli qeydi'})
    pin = c.post(f'/api/students/{a}/reset-pin').json()
    s = student_client(pin['portal_code'], pin['pin'])
    r = s.get('/api/portal/progress').json()
    assert len(r) == 1 and r[0]['done'] == 3 and r[0]['expected'] == 5 and r[0]['delta'] == -2
    assert r[0]['review'] == [{'seq': 3, 'topic': 'Mövzu 3'}] and r[0]['next'][0]['seq'] == 4
    assert 'gizli' not in str(r)                                  # müəllimin qeydi şagirdə getmir
    assert c.get('/api/portal/progress').status_code == 403       # müəllim portal deyil
