"""Fərdi (repetitor) məkan: məktəbdən tam ayrılıq (docs/ferdi-sinif-promtu.md §6)."""
from .test_api_portal import student_client


def test_private_class_isolated_from_school(world):
    as_, S = world
    admin, ilqar = as_('admin'), as_('ilqar')
    school_classes = {c['name'] for c in admin.get('/api/classes').json()}
    # müəllim fərdi sinif yaradır – fərdi məkan avtomatik yaranır və aktiv olur
    r = ilqar.post('/api/classes', json={'name': 'IX hazırlıq', 'kind': 'adi', 'private': True})
    assert r.status_code == 200, r.text
    cid = r.json()['id']
    me = ilqar.get('/api/auth/me').json()
    assert me['workspace'] == 'private' and me['has_private'] and 'fərdi hazırlıq' in me['school_name']
    ws = ilqar.get('/api/workspaces').json()
    main = next(w for w in ws if w['kind'] == 'school'); priv = next(w for w in ws if w['kind'] == 'private')
    assert priv['active'] and [c['name'] for c in ilqar.get('/api/classes').json()] == ['IX hazırlıq']
    ilqar.post(f'/api/classes/{cid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 2, 'has_summative': False,
                                                 'slots': {'0': [7], '2': [7]}})
    st = ilqar.post('/api/students', json={'full_name': 'Fərdi Şagird oğlu', 'class_id': cid}).json()
    assert st['portal_code'] and st['initial_pin']
    # məktəb tərəfi: admin, siyahılar, məktəb axtarışı, hesabat, audit – heç birində yoxdur
    assert {c['name'] for c in admin.get('/api/classes').json()} == school_classes
    assert admin.get('/api/students', params={'class_id': cid}).status_code in (403, 404)
    assert not any(s['id'] == priv['id'] for s in admin.get('/api/schools').json())
    assert all(c['class_name'] != 'IX hazırlıq' for c in admin.get('/api/school/performance').json()['classes'])
    assert not any(x['entity'] == 'class' and x['details'] and x['details'].get('name') == 'IX hazırlıq' for x in admin.get('/api/audit').json())
    assert admin.put('/api/workspaces/active', json={'school_id': priv['id']}).status_code == 404     # başqasının məkanı
    assert admin.patch(f"/api/schools/{priv['id']}", json={'name': 'oğurlanmış ad'}).status_code in (403, 404)
    # fərdi şagird: yalnız öz sinfi və öz müəllimi
    s = student_client(st['portal_code'], st['initial_pin'])
    contacts = s.get('/api/chat/contacts').json()
    assert {c['full_name'] for c in contacts} <= {'Nəcəfov İlqar'} and any(c['full_name'] == 'Nəcəfov İlqar' for c in contacts)
    assert all(r['kind'] != 'staff' for r in ilqar.get('/api/chat/rooms').json())
    # məktəbə qayıdış – fərdi sinif görünmür, məktəb sinifləri yerindədir
    assert ilqar.put('/api/workspaces/active', json={'school_id': main['id']}).status_code == 200
    assert ilqar.get('/api/auth/me').json()['workspace'] == 'school'
    assert 'IX hazırlıq' not in {c['name'] for c in ilqar.get('/api/classes').json()}
    assert any(r['kind'] == 'staff' for r in ilqar.get('/api/chat/rooms').json())
    # yenidən fərdi məkana, adını dəyişmək
    ilqar.put('/api/workspaces/active', json={'school_id': priv['id']})
    w = ilqar.patch('/api/workspaces/private', json={'name': 'İlqar müəllim – olimpiada hazırlığı'}).json()
    assert next(x for x in w if x['kind'] == 'private')['name'] == 'İlqar müəllim – olimpiada hazırlığı'


def test_my_lists_follow_workspace(world):
    as_, S = world
    c = as_('admin')
    cid = c.post('/api/classes', json={'name': 'X q'}).json()['id']
    c.post(f'/api/classes/{cid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 1, 'slots': {'0': [1]}})
    pid = c.post('/api/classes', json={'name': 'Olimpiada', 'kind': 'adi', 'private': True}).json()['id']
    c.post(f'/api/classes/{pid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 1, 'slots': {'1': [8]}, 'has_summative': False})
    names = lambda: {x['class_name'] for x in c.get('/api/my/lessons').json()}
    assert names() == {'Olimpiada'}                                   # fərdi məkan aktivdir
    assert {x['class_name'] for x in c.get('/api/overview').json()} == {'Olimpiada'}
    assert {x['class_name'] for x in c.get('/api/my/weekly').json()['items']} <= {'Olimpiada'}
    ws = {w['kind']: w['id'] for w in c.get('/api/workspaces').json()}
    c.put('/api/workspaces/active', json={'school_id': ws['school']})
    assert 'Olimpiada' not in names() and 'X q' in names()
    assert all(x['class_name'] != 'Olimpiada' for x in c.get('/api/overview').json())


def test_private_calendar_edit(world):
    as_, S = world
    ilqar, admin = as_('ilqar'), as_('admin')
    cid = ilqar.post('/api/classes', json={'name': 'Yay hazırlığı', 'kind': 'adi', 'private': True}).json()['id']
    ta = ilqar.post(f'/api/classes/{cid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 2, 'has_summative': False,
                                                      'slots': {'0': [1], '2': [1]}}).json()['mine']['ta_id']
    cal = ilqar.get('/api/workspaces/private/calendar').json()
    school_start = cal['year']['start']
    # yay hazırlığı: öz tarixləri
    bad = ilqar.put('/api/workspaces/private/year', json={'name': 'Yay 2027', 'start': '2027-06-21', 'sem1_end': '2027-06-20',
                                                          'sem2_start': '2027-07-21', 'end': '2027-08-27'})
    assert bad.status_code == 422
    r = ilqar.put('/api/workspaces/private/year', json={'name': 'Yay 2027', 'start': '2027-06-21', 'sem1_end': '2027-07-20',
                                                        'sem2_start': '2027-07-21', 'end': '2027-08-27'}).json()
    assert r['year']['start'] == '2027-06-21' and r['year']['name'] == 'Yay 2027'
    lc = ilqar.get(f'/api/analytics/{ta}/lessons').json()
    assert lc['semesters'][0]['from'] == '2027-06-21' and lc['semesters'][1]['to'] == '2027-08-27'
    before = lc['year']['timetable_total']
    # tətil aralığı (həftəsonları sayılmır) – dərs yuvaları azalır
    r = ilqar.post('/api/workspaces/private/holidays', json={'date': '2027-07-05', 'to': '2027-07-11', 'name': 'Qısa tətil'}).json()
    assert len([h for h in r['holidays'] if h['name'] == 'Qısa tətil']) == 5
    assert ilqar.get(f'/api/analytics/{ta}/lessons').json()['year']['timetable_total'] == before - 2
    assert ilqar.post('/api/workspaces/private/holidays', json={'date': '2027-07-10', 'name': 'Şənbə'}).status_code == 400
    hid = r['holidays'][0]['id']
    r = ilqar.delete(f'/api/workspaces/private/holidays/{hid}').json()
    assert all(h['id'] != hid for h in r['holidays'])
    # məktəbin təqviminə qayıt
    assert ilqar.post('/api/workspaces/private/calendar/reset').json()['year']['start'] == school_start
    # başqası: fərdi məkanı yoxdur – 404
    assert admin.get('/api/workspaces/private/calendar').status_code == 404
    assert admin.post('/api/workspaces/private/holidays', json={'date': '2027-07-05', 'name': 'x x'}).status_code == 404
