"""Məşğələ qruplarına proqram (docs/meshgele-proqram-ve-video-beledci-promtu.md §A): tip tanınması, inkişaf (V/IX) və tərəqqi proqramı,
idempotentlik, keçirilmiş/əl ilə mövzulara toxunmama, dry-run, şagird portalında tip yoxdur, held və session_test düzəlişləri."""
import datetime as dt

from app import programs
from app.extra_programs import course_kind, detect_kind, leaks
from app.models import ExtraCourse, ExtraSession, PlanLesson, PlanProgram, TeachingAssignment

from .test_api_portal import UTC, clock, setup, student_client  # noqa: F401 – clock fixture

SAT = [{'weekday': 5, 'start': '10:00', 'end': '11:00', 'room': '5'}]


def mk_class(admin, S, name, n=2, plan=0):
    cid = admin.post('/api/classes', json={'name': name}).json()['id']
    admin.post(f'/api/classes/{cid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 2, 'slots': {'1': [1, 5]}})
    st = [admin.post('/api/students', json={'full_name': f'{name} Şagird{i} oğlu', 'class_id': cid, 'force': True}).json() for i in range(n)]
    with S() as db:
        ta = db.query(TeachingAssignment).filter_by(class_id=cid).one().id
        for i in range(plan):
            db.add(PlanLesson(assignment_id=ta, seq=i + 1, semester=1, assessment_type='formativ', section='1. Bölmə',
                              topic=f'Plan mövzusu {i + 1}', date=dt.date(2026, 9, 15) + dt.timedelta(days=7 * i)))
        db.commit()
    return ta, cid, st


def mk_course(admin, ta, title, **kw):
    body = {'title': title, 'format': 'əyani', 'ta_ids': [ta], 'schedule': SAT, 'starts_on': '2026-10-03', 'ends_on': '2026-11-07', **kw}
    r = admin.post('/api/extra', json=body)
    assert r.status_code == 200, r.text
    return r.json()


def setup_programs(S):
    with S() as db:
        programs.ensure_builtin(db)
        db.commit()


def test_kind_detection():
    mk = lambda **k: ExtraCourse(title=k.pop('title', 'Qrup'), goal=k.pop('goal', None), audience={'levels': k.pop('levels', None)}, **k)
    assert detect_kind(mk(levels=['Zəif'])) == 'inkisaf'
    assert detect_kind(mk(levels=['Güclü'])) == 'tereqqi'
    assert detect_kind(mk(levels=['Zəif', 'Güclü'])) == 'diger'
    assert detect_kind(mk(title='İnkişaf qrupu')) == 'inkisaf'
    assert detect_kind(mk(title='Riyaziyyat', goal='tərəqqi üçün')) == 'tereqqi'
    assert detect_kind(mk(title='Olimpiada')) == 'diger'
    assert course_kind(mk(title='Zəif', kind='tereqqi')) == 'tereqqi'          # əl ilə seçim üstündür


def test_inkisaf_vii_and_ix(world, clock, monkeypatch):
    as_, S = world
    monkeypatch.setattr('app.api.extra.now', clock)
    clock.t = dt.datetime(2026, 10, 2, 8, 0, tzinfo=UTC)
    admin = as_('admin')
    setup_programs(S)
    ta7, _, _ = mk_class(admin, S, 'VII a')
    ta9, _, _ = mk_class(admin, S, 'IX a')
    c7, c9 = mk_course(admin, ta7, 'İnkişaf qrupu VII'), mk_course(admin, ta9, 'Riyaziyyat', kind='inkisaf')
    assert c7['kind'] == 'inkisaf' and c7['kind_set'] and c7['sessions'] == 6

    r7 = admin.post(f"/api/extra/{c7['id']}/program", json={}).json()
    r9 = admin.post(f"/api/extra/{c9['id']}/program", json={}).json()
    assert r7['program']['key'] == 'dim-sinif-testleri-7' and r9['program']['key'] == 'dim-sinif-testleri-9'
    refs = [x['ref'] for x in r7['rows']]
    mid = [r for r in refs[1:-1] if not r.startswith('pre:')]                 # VI sinfin «Təkrar» bölməsi prerekvizit kimi öndə
    assert refs[0] == 'diag-in' and refs[-1] == 'diag-out' and mid[:2] == ['1.1', '1.2'] and len(mid) >= 2
    assert refs[1].startswith('pre:6')
    assert r7['rows'][1]['variants'] == 'A+B' and r9['rows'][1]['variants'] == 'A+B'
    assert r7['rows'][1]['test']['status'] == 'pending'                       # V–VIII testləri hələ yoxdur
    assert any('hazırlanır' in w['key'] for w in r7['warnings'])
    full = admin.get(f"/api/extra/{c7['id']}").json()
    ses = full['session_list']
    assert 'Giriş diaqnostikası' in ses[0]['topics'][0]['text'] and ses[-1]['topics'][0]['text'] == 'Çıxış testi'
    assert full['program']['key'] == 'dim-sinif-testleri-7' and full['program_applied']
    with S() as db:
        assert db.query(ExtraSession).filter(ExtraSession.course_id == c7['id'], ExtraSession.topic_ref == '1.1').count() == 1
        assert db.get(ExtraCourse, c9['id']).program_id == db.query(PlanProgram).filter_by(key='dim-sinif-testleri-9').one().id

    # idempotent: təkrar eyni nəticə, dublikat yoxdur
    again = admin.post(f"/api/extra/{c7['id']}/program", json={}).json()
    assert [x['ref'] for x in again['rows']] == refs
    after = admin.get(f"/api/extra/{c7['id']}").json()['session_list']
    assert [s['topics'] for s in after] == [s['topics'] for s in ses]

    # cədvəl dəyişir: yeni tarixlər, mövzular yenidən paylanır, dublikat yoxdur
    p = admin.patch(f"/api/extra/{c7['id']}", json={'schedule': [{'weekday': 0, 'start': '15:00', 'end': '16:00'}]}).json()
    assert p['rebuilt'] == 6 and p['refilled'] == p['sessions']
    news = admin.get(f"/api/extra/{c7['id']}").json()['session_list']
    assert all(dt.date.fromisoformat(s['date']).weekday() == 0 for s in news)
    with S() as db:
        refs2 = [s.topic_ref for s in db.query(ExtraSession).filter_by(course_id=c7['id']).order_by(ExtraSession.date)]
    assert refs2[0] == 'diag-in' and refs2[-1] == 'diag-out' and len(set(refs2)) == len(refs2)


def test_held_and_manual_topics_untouched(world, clock, monkeypatch):
    as_, S = world
    monkeypatch.setattr('app.api.extra.now', clock)
    clock.t = dt.datetime(2026, 10, 2, 8, 0, tzinfo=UTC)
    admin = as_('admin')
    setup_programs(S)
    ta, _, _ = mk_class(admin, S, 'IX b')
    c = mk_course(admin, ta, 'İnkişaf', kind='inkisaf')
    cid = c['id']
    sid = [s['id'] for s in admin.get(f'/api/extra/{cid}').json()['session_list']]
    admin.put(f'/api/extra/{cid}/sessions/{sid[2]}', json={'topics': [{'text': 'Mənim mövzum'}]})
    assert admin.post(f'/api/extra/{cid}/program', json={}).json()['kept_manual'] == 1
    ses = admin.get(f'/api/extra/{cid}').json()['session_list']
    assert ses[2]['topics'][0]['text'] == 'Mənim mövzum' and len(ses[1]['topics']) == 1

    # birinci məşğələ keçirilir: sonradan yenidən hesablama ona toxunmur və giriş testi təkrarlanmır
    clock.t = dt.datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
    assert admin.post(f'/api/extra/{cid}/sessions/{sid[0]}/held', json={}).status_code == 200
    before = admin.get(f'/api/extra/{cid}').json()['session_list'][0]['topics']
    r = admin.post(f'/api/extra/{cid}/program', json={}).json()
    assert r['held'] == 1 and 'diag-in' not in [x['ref'] for x in r['rows']]
    ses = admin.get(f'/api/extra/{cid}').json()['session_list']
    assert ses[0]['topics'] == before and ses[2]['topics'][0]['text'] == 'Mənim mövzum'
    with S() as db:
        refs = [s.topic_ref for s in db.query(ExtraSession).filter_by(course_id=cid) if s.topic_ref]
    assert len(refs) == len(set(refs))

    # PUT ilə «held» qoymaq olmaz; session_test təkrarı 409, «replace» ilə əvəz olunur
    assert admin.put(f'/api/extra/{cid}/sessions/{sid[3]}', json={'status': 'held'}).status_code == 400
    assert admin.put(f'/api/extra/{cid}/sessions/{sid[0]}', json={'homework': 'x', 'status': 'held'}).status_code == 200


def test_session_test_idempotent(world, clock, monkeypatch):
    as_, S = world
    monkeypatch.setattr('app.api.extra.now', clock)
    clock.t = dt.datetime(2026, 10, 2, 8, 0, tzinfo=UTC)
    admin, ta, _, st, ids = setup(world)
    c = mk_course(admin, ta, 'Olimpiada')
    sid = admin.get(f"/api/extra/{c['id']}").json()['session_list'][0]['id']
    body = {'title': 'Test 1','bank_ids': ids, 'opens_at': '2026-10-03T07:00:00Z', 'closes_at': '2026-10-03T12:00:00Z'}
    first = admin.post(f"/api/extra/{c['id']}/sessions/{sid}/test", json=body)
    assert first.status_code == 200, first.text
    assert admin.post(f"/api/extra/{c['id']}/sessions/{sid}/test", json=body).status_code == 409
    second = admin.post(f"/api/extra/{c['id']}/sessions/{sid}/test", json={**body, 'replace': True})
    assert second.status_code == 200 and second.json()['batch_id'] != first.json()['batch_id']


def test_tereqqi_follows_class_plan(world, clock, monkeypatch):
    as_, S = world
    monkeypatch.setattr('app.api.extra.now', clock)
    clock.t = dt.datetime(2026, 10, 2, 8, 0, tzinfo=UTC)
    admin = as_('admin')
    setup_programs(S)
    with S() as db:                                                   # «Güclü» proqram yoxdur -> sinfin planı
        db.query(PlanProgram).filter(PlanProgram.key.like('tereqqi-%')).delete(synchronize_session=False)
        db.commit()
    ta, _, _ = mk_class(admin, S, 'VIII a', plan=20)
    c = mk_course(admin, ta, 'Tərəqqi qrupu', min_score=0)
    assert c['kind'] == 'tereqqi'
    r = admin.post(f"/api/extra/{c['id']}/program", json={})
    assert r.status_code == 200, r.text
    r = r.json()
    assert r['mode'] == 'plan' and r['rows'][0]['ref'] == 'diag-in' and r['rows'][-1]['ref'] == 'diag-out'
    mid = [x for x in r['rows'] if x['ref'].startswith('plan:')]
    assert mid and all(x['variants'] == 'B+C' or x['variants'] == 'B' for x in mid)
    assert admin.delete(f"/api/extra/{c['id']}/program").json()['cleared'] == r['to_fill']


def test_dry_run_writes_nothing_and_bulk_apply(world, clock, monkeypatch):
    as_, S = world
    monkeypatch.setattr('app.api.extra.now', clock)
    clock.t = dt.datetime(2026, 10, 2, 8, 0, tzinfo=UTC)
    admin = as_('admin')
    setup_programs(S)
    ta, _, _ = mk_class(admin, S, 'VI a')
    ta2, _, _ = mk_class(admin, S, 'IX c')
    c1 = mk_course(admin, ta, 'Zəif qrup')
    c2 = mk_course(admin, ta2, 'Olimpiada')                                   # tip tanınmır – toxunulmur
    r = admin.post('/api/extra/assign-programs?dry=1').json()
    assert not r['applied'] and r['applicable'] == 1
    assert {x['course_id']: x['kind'] for x in r['rows']} == {c1['id']: 'inkisaf', c2['id']: 'diger'}
    with S() as db:
        assert db.query(ExtraSession).filter(ExtraSession.topic_ref.is_not(None)).count() == 0
        assert db.get(ExtraCourse, c1['id']).program_id is None
    one = admin.post(f"/api/extra/{c1['id']}/program", json={'dry': True}).json()
    assert one['to_fill'] > 0
    with S() as db:
        assert db.query(ExtraSession).filter(ExtraSession.topic_ref.is_not(None)).count() == 0
    r = admin.post('/api/extra/assign-programs?dry=0').json()
    assert r['applied'] and r['to_fill'] > 0
    with S() as db:
        assert db.query(ExtraSession).filter_by(course_id=c1['id']).filter(ExtraSession.topic_ref.is_not(None)).count() > 0
        assert db.query(ExtraSession).filter_by(course_id=c2['id']).filter(ExtraSession.topic_ref.is_not(None)).count() == 0
    n = admin.post('/api/extra/assign-programs?dry=0').json()                  # təkrar – dəyişiklik yoxdur
    assert n['to_fill'] == r['to_fill']
    assert as_('ilqar').post('/api/extra/assign-programs?dry=1').json()['rows'] == []      # müəllim yalnız öz qrupları


def test_kind_survives_member_changes_and_student_sees_no_level(world, clock, monkeypatch):
    as_, S = world
    monkeypatch.setattr('app.api.extra.now', clock)
    clock.t = dt.datetime(2026, 10, 2, 8, 0, tzinfo=UTC)
    admin = as_('admin')
    ta, _, st = mk_class(admin, S, 'VII c', n=3)
    with S() as db:
        from app.models import LevelOverride
        for s in st[:2]:
            db.add(LevelOverride(assignment_id=ta, student_id=s['id'], level='Zəif'))
        db.commit()
    c = mk_course(admin, ta, 'Zəif qrup – təkrar', levels=['Zəif'], goal='zəif şagirdlər üçün')
    assert c['kind'] == 'inkisaf'
    admin.post(f"/api/extra/{c['id']}/members", json={'student_ids': [st[2]['id']]})        # levels sıfırlanır
    full = admin.get(f"/api/extra/{c['id']}").json()
    assert full['audience']['levels'] is None and full['kind'] == 'inkisaf' and full['kind_set']
    me = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    mine = me.get('/api/portal/extra').json()
    assert len(mine) == 1 and mine[0]['neutral'] is True and mine[0]['title'] == '' and mine[0]['goal'] is None
    assert 'kind' not in mine[0] and 'levels' not in mine[0] and 'audience' not in mine[0]


def test_builtin_tereqqi_programs_idempotent(world):
    as_, S = world
    setup_programs(S)
    with S() as db:
        ps = db.query(PlanProgram).filter(PlanProgram.key.like('tereqqi-%')).all()
        assert {p.key for p in ps} == {f'tereqqi-{g}' for g in range(5, 12)}
        assert all(p.level == 'Güclü' and p.school_id is None for p in ps)
        p9 = next(p for p in ps if p.grade == 9)
        assert p9.data['template']['mock_every'] == 8 and p9.data['template']['final_mock']
        assert 'mock_every' not in next(p for p in ps if p.grade == 7).data['template']
        topics = [t for s in p9.data['template']['sections'] for t in s['topics']]
        assert not any(s['section'].startswith('Təkrar') for s in p9.data['template']['sections'])
        assert topics.count(programs.EXTRA_TOPIC) == len(p9.data['template']['sections'])
        assert not any(leaks(t) for t in topics) and not leaks(programs.EXTRA_TOPIC)
        before = db.query(PlanProgram).count()
        assert programs.ensure_builtin(db) is False
        assert db.query(PlanProgram).count() == before


def test_tereqqi_uses_builtin_program_and_scheduler_idempotent(world, clock, monkeypatch):
    as_, S = world
    monkeypatch.setattr('app.api.extra.now', clock)
    clock.t = dt.datetime(2026, 10, 2, 8, 0, tzinfo=UTC)
    monkeypatch.setattr('app.models.now', clock)
    monkeypatch.setattr('app.scheduler.SessionLocal', S)
    admin = as_('admin')
    setup_programs(S)
    ta, _, _ = mk_class(admin, S, 'IX a', plan=20)
    c = mk_course(admin, ta, 'Tərəqqi qrupu', min_score=0)
    assert c['kind'] == 'tereqqi'
    r = admin.post(f"/api/extra/{c['id']}/program", json={})
    assert r.status_code == 200, r.text
    r = r.json()
    assert r['mode'] == 'program' and r['to_fill'] > 0
    shown = [x['text'] for x in r['rows'] if x.get('text')]
    assert not any(leaks(t) for t in shown if programs.EXTRA_TOPIC in t)
    admin.delete(f"/api/extra/{c['id']}/program")
    from app import scheduler
    scheduler._extra_programs_job()
    with S() as db:
        snap = sorted((s.id, s.topic_ref, str(s.topics)) for s in db.query(ExtraSession).filter_by(course_id=c['id']))
    assert any(x[1] for x in snap)
    scheduler._extra_programs_job()
    with S() as db:
        assert sorted((s.id, s.topic_ref, str(s.topics)) for s in db.query(ExtraSession).filter_by(course_id=c['id'])) == snap


def test_tereqqi_members_by_math_score(world, clock, monkeypatch):
    """Tərəqqi qrupu: Riyaziyyat balı >= 50 (default); inkişaf/digər qrupda bal süzgəci yoxdur."""
    as_, S = world
    monkeypatch.setattr('app.api.extra.now', clock)
    clock.t = dt.datetime(2026, 10, 2, 8, 0, tzinfo=UTC)
    admin = as_('admin')
    setup_programs(S)
    ta, _, st = mk_class(admin, S, 'IX b', n=3)
    # a: riyaziyyat 55 (digər fənlər aşağı olsa da hesaba girmir), b: 45, c: bal yoxdur
    marks = {st[0]['id']: {'reytinq': 55.0}, st[1]['id']: {'reytinq': 45.0}, st[2]['id']: {}}
    monkeypatch.setattr('app.levels.components', lambda db, ctx: {i: {'buraxilis': None, 'sinaq': None, 'diaqnostik': None,
                                                                    'reytinq': None, **m} for i, m in marks.items()})
    c = mk_course(admin, ta, 'Tərəqqi qrupu')
    assert c['kind'] == 'tereqqi' and c['audience']['min_score'] == 50 and c['students'] == 1
    with S() as db:
        from app.api.extra import members
        assert [s.id for s, _ in members(db, db.get(ExtraCourse, c['id']))] == [st[0]['id']]
    c2 = mk_course(admin, ta, 'Tərəqqi 2', kind='tereqqi', min_score=40)
    assert c2['students'] == 2
    c3 = mk_course(admin, ta, 'Zəif qrup', kind='inkisaf')                     # inkişaf – davranış əvvəlki kimi, min_score yoxdur
    assert 'min_score' not in c3['audience'] or c3['audience']['min_score'] is None