"""Köhnə fərdi vaxtları görüşə çevirmək: GET/POST /api/workspaces/ferdi-units (quru hesabat, idempotent tətbiq, məxfilik)."""
import datetime as dt


def _old_format_group(as_, S, with_program=True):
    t = as_('ilqar')
    g = t.post('/api/classes', json={'name': 'Köhnə vaxtlı qrup', 'kind': 'adi', 'private': True}).json()['id']
    body = {'subject': 'Riyaziyyat', 'weekly_hours': 1, 'starts_on': '2026-10-01', 'ends_on': '2027-05-31',
            'times': [{'weekday': 1, 'start': '17:00', 'end': '17:45'}]}
    if with_program:
        prep = next(p for p in t.get('/api/programs').json() if p['builtin'] and p['course'] and p['grade'] == 9)
        body['program_id'] = prep['id']
    r = t.post(f'/api/classes/{g}/join', json=body)
    assert r.status_code == 200, r.text
    ta = r.json()['mine']['ta_id']
    from app.models import JournalEntry, TeachingAssignment
    with S() as db:                                              # köhnə format: bir yuva = 17:00–18:30
        row = db.get(TeachingAssignment, ta)
        row.times, row.slots, row.weekly_hours = {'1:0': '17:00–18:30'}, {'1': [0]}, 1
        db.add(JournalEntry(assignment_id=ta, date=dt.date(2026, 10, 6), period=0, note='köhnə qeyd'))
        db.commit()
    return t, ta


def test_preview_writes_nothing(world):
    as_, S = world
    t, ta = _old_format_group(as_, S)
    r = t.get('/api/workspaces/ferdi-units')
    assert r.status_code == 200, r.text
    d = r.json()
    g = next(x for x in d['groups'] if x['ta_id'] == ta)
    assert g['class'] == 'Köhnə vaxtlı qrup' and g['changed'] and g['has_program']
    assert g['old_slots'] == 1 and g['new_slots'] == 2 and d['pending'] == 1 and d['changed'] == []
    assert g['new_meetings'] == [{'weekday': 1, 'day': 'Ç.a.', 'start': '17:00', 'end': '18:35', 'units': 2,
                                  'parts': ['17:00–17:45', '17:50–18:35']}]
    from app.models import TeachingAssignment
    with S() as db:
        assert db.get(TeachingAssignment, ta).times == {'1:0': '17:00–18:30'}


def test_apply_splits_keeps_journal_and_is_idempotent(world):
    as_, S = world
    t, ta = _old_format_group(as_, S)
    r = t.post('/api/workspaces/ferdi-units')
    assert r.status_code == 200, r.text
    assert r.json()['changed'] == [ta]
    from app.models import AuditLog, JournalEntry, TeachingAssignment
    with S() as db:
        row = db.get(TeachingAssignment, ta)
        assert row.times == {'1:0': '17:00–17:45', '1:1': '17:50–18:35'} and row.weekly_hours == 2
        assert row.slots == {'1': [0, 1]}
        je = db.query(JournalEntry).filter_by(assignment_id=ta).all()
        assert [(j.period, j.note) for j in je] == [(0, 'köhnə qeyd')]        # jurnal yazısı birinci hissədə
        assert db.query(AuditLog).filter(AuditLog.entity == 'workspace', AuditLog.action == 'update').count() >= 1
    r2 = t.post('/api/workspaces/ferdi-units')
    assert r2.status_code == 200 and r2.json()['changed'] == []
    assert t.get('/api/workspaces/ferdi-units').json()['pending'] == 0
    with S() as db:
        assert db.get(TeachingAssignment, ta).times == {'1:0': '17:00–17:45', '1:1': '17:50–18:35'}
    plan = t.get(f'/api/plan/{ta}')
    assert plan.status_code == 200


def test_no_program_group(world):
    as_, S = world
    t, ta = _old_format_group(as_, S, with_program=False)
    g = next(x for x in t.get('/api/workspaces/ferdi-units').json()['groups'] if x['ta_id'] == ta)
    assert g['has_program'] is False and g['changed']
    assert t.post('/api/workspaces/ferdi-units').json()['changed'] == [ta]


def test_other_teacher_and_admin_get_404(world):
    as_, S = world
    _old_format_group(as_, S, with_program=False)
    for who in ('admin', 'yad'):
        c = as_(who)
        assert c.get('/api/workspaces/ferdi-units').status_code == 404
        assert c.post('/api/workspaces/ferdi-units').status_code == 404
