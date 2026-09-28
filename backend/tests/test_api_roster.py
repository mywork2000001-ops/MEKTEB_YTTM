"""Ortaq sinif/şagird siyahısı, məxfilik, arxiv, Tənzimləmələr kilidi, məktəb/UTİS."""
SLOTS_XC = {'0': [6], '1': [2, 4], '2': [1, 2], '3': [6, 7], '4': [1]}


def mk_class(c, name='X c', **kw):
    return c.post('/api/classes', json={'name': name, 'kind': 'TOM', **kw})


def join(c, cid, hours=8, slots=SLOTS_XC, subject='Riyaziyyat'):
    return c.post(f'/api/classes/{cid}/join', json={'subject': subject, 'weekly_hours': hours, 'slots': slots})


def mk_student(c, cid, name='Abbasova Sevinc Vüsal qızı', birth='2011-05-01', **kw):
    return c.post('/api/students', json={'full_name': name, 'class_id': cid, 'birth_date': birth, **kw})


def test_shared_roster_and_join(world):
    as_, _ = world
    admin, ilqar = as_('admin'), as_('ilqar')
    r = mk_class(admin)
    assert r.status_code == 200 and r.json()['code'] == 'XC'
    cid = r.json()['id']
    assert join(admin, cid).status_code == 200
    st = mk_student(admin, cid).json()
    assert st['portal_code'] == 'XC-001' and len(st['initial_pin']) == 4

    # İlqar sinfin adını görür, amma şagirdləri yox (hələ qoşulmayıb)
    lst = ilqar.get('/api/classes').json()
    assert [(x['name'], x['can_open']) for x in lst] == [('X c', False)]
    assert lst[0]['teachers'][0]['name'] == 'Həsənov Fərid'
    assert ilqar.get('/api/students', params={'class_id': cid}).status_code == 403
    assert ilqar.get('/api/students').json() == []

    # təkrar sinif yaratmaq əvəzinə mövcud sinfə yönləndirilir
    dup = mk_class(ilqar, 'x  C')
    assert dup.status_code == 409 and dup.json()['detail']['class_id'] == cid

    # qoşulur -> eyni şagirdlər, eyni portal kodu
    assert join(ilqar, cid, subject='Fizika', hours=2, slots={'0': [1], '2': [3]}).status_code == 200
    s = ilqar.get('/api/students', params={'class_id': cid}).json()
    assert [x['portal_code'] for x in s] == ['XC-001']
    assert len(ilqar.get('/api/classes').json()[0]['teachers']) == 2


def test_duplicate_student_blocked_across_teachers(world):
    as_, _ = world
    admin, ilqar = as_('admin'), as_('ilqar')
    cid = mk_class(admin).json()['id']
    join(admin, cid)
    join(ilqar, cid, subject='Fizika', hours=2, slots={})
    mk_student(admin, cid)
    r = mk_student(ilqar, cid, name='abbasova  sevinc vüsal qızı')
    assert r.status_code == 409 and 'artıq var' in r.json()['detail']['message']
    # eyni ad, fərqli doğum tarixi – adaş, icazə verilir
    assert mk_student(ilqar, cid, birth='2010-01-01').status_code == 200


def test_official_ids_rejected(world):
    as_, _ = world
    admin = as_('admin')
    cid = mk_class(admin).json()['id']
    r = admin.post('/api/students', json={'full_name': 'Test Şagird oğlu', 'class_id': cid, 'pinkod': '6abc12'})
    assert r.status_code == 422


def test_other_school_cannot_see(world):
    as_, _ = world
    admin, yad = as_('admin'), as_('yad')
    cid = mk_class(admin).json()['id']
    sid = mk_student(admin, cid).json()['id']
    assert yad.get('/api/classes').json() == []
    assert join(yad, cid).status_code == 404
    assert yad.patch(f'/api/students/{sid}', json={'score_math': 99}).status_code == 403


def test_archive_restore_delete(world):
    as_, _ = world
    admin = as_('admin')
    cid = mk_class(admin).json()['id']
    join(admin, cid)
    sid = mk_student(admin, cid).json()['id']
    assert admin.post(f'/api/students/{sid}/archive', json={'confirm': 'yanlış ad'}).status_code == 400
    assert admin.request('DELETE', f'/api/students/{sid}', json={'confirm': 'Abbasova Sevinc Vüsal qızı'}).status_code == 409
    assert admin.post(f'/api/students/{sid}/archive', json={'confirm': 'abbasova sevinc vüsal qızı'}).status_code == 200
    assert admin.get('/api/students', params={'class_id': cid}).json() == []
    assert len(admin.get('/api/students', params={'archived': True}).json()) == 1
    # arxivdəki şagird portala daxil ola bilmir
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as st:
        assert st.post('/api/auth/login', json={'login': 'XC-001', 'password': '0000'}).status_code == 401
    assert admin.post(f'/api/students/{sid}/restore').status_code == 200
    admin.post(f'/api/students/{sid}/archive', json={'confirm': 'Abbasova Sevinc Vüsal qızı'})
    assert admin.request('DELETE', f'/api/students/{sid}', json={'confirm': 'Abbasova Sevinc Vüsal qızı'}).status_code == 200
    # sinif: şagird yoxdursa arxivdən silinir
    assert admin.post(f'/api/classes/{cid}/archive', json={'confirm': 'X c'}).status_code == 200
    assert admin.get('/api/classes').json() == []
    assert admin.request('DELETE', f'/api/classes/{cid}', json={'confirm': 'X c'}).status_code == 200


def test_student_pin_reset_and_portal_login(world):
    as_, _ = world
    admin = as_('admin')
    cid = mk_class(admin).json()['id']
    join(admin, cid)
    sid = mk_student(admin, cid).json()['id']
    pin = admin.post(f'/api/students/{sid}/reset-pin').json()['pin']
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as st:
        r = st.post('/api/auth/login', json={'login': 'xc-001', 'password': pin})
        assert r.status_code == 200 and r.json()['role'] == 'student'
        assert st.get('/api/classes').status_code == 403            # şagird müəllim bölmələrini görmür


def test_group_members_only_from_parent(world):
    as_, _ = world
    admin = as_('admin')
    xb = mk_class(admin, 'X b').json()['id']
    xc = mk_class(admin, 'X c').json()['id']
    join(admin, xb, hours=5, slots={})
    join(admin, xc)
    q = mk_class(admin, 'X b (riyaziyyat qrupu)', kind='qrup', parent_id=xb).json()['id']
    join(admin, q, hours=5, slots={})
    a = mk_student(admin, xb, name='Birinci Şagird oğlu').json()['id']
    b = mk_student(admin, xc, name='İkinci Şagird qızı').json()['id']
    assert admin.put(f'/api/classes/{q}/members', json={'student_ids': [a, b]}).status_code == 400
    assert admin.put(f'/api/classes/{q}/members', json={'student_ids': [a]}).json() == [a]
    assert [s['id'] for s in admin.get('/api/students', params={'class_id': q}).json()] == [a]


def test_join_slots_must_match_hours(world):
    as_, _ = world
    admin = as_('admin')
    cid = mk_class(admin).json()['id']
    assert join(admin, cid, hours=7).status_code == 400                 # cədvəldə 8 saat var


def test_settings_lock(world):
    as_, _ = world
    ilqar = as_('ilqar')
    assert ilqar.get('/api/settings/lock').json()['has_password'] is False
    assert mk_class(ilqar, 'X d').status_code == 200                    # parol boşdur – sərbəst
    assert ilqar.put('/api/settings/password', json={'new': 'gizli'}).status_code == 200
    assert mk_class(ilqar, 'X f').status_code == 423                    # kilidli
    assert ilqar.post('/api/settings/unlock', json={'password': 'yox'}).status_code == 401
    tok = ilqar.post('/api/settings/unlock', json={'password': 'gizli'}).json()['token']
    assert ilqar.post('/api/classes', json={'name': 'X f'}, headers={'X-Settings-Token': tok}).status_code == 200
    assert ilqar.get('/api/classes').status_code == 200                 # baxmaq üçün kilid lazım deyil


def test_school_utis_and_teacher_join(world):
    as_, _ = world
    admin, yeni = as_('admin'), as_('yeni')
    assert admin.post('/api/schools', json={'name': 'Test məktəbi', 'utis': '12a'}).status_code == 400
    assert admin.post('/api/schools', json={'name': 'Test məktəbi', 'utis': '111'}).status_code == 409
    assert yeni.post('/api/schools', json={'name': 'Mənim məktəbim'}).status_code == 403   # UTİS-i admin yazır
    assert yeni.get('/api/schools', params={'q': 'T'}).json() == []                         # ən azı 2 hərf
    found = yeni.get('/api/schools', params={'q': 'rafiq nuriyev'}).json()
    assert len(found) == 1 and 'utis' not in found[0]                                       # müəllim UTİS-i görmür
    assert yeni.get('/api/classes').status_code == 409                                      # məktəb seçilməyib
    assert yeni.post('/api/me/school', json={'school_id': found[0]['id']}).status_code == 200
    assert yeni.get('/api/classes').status_code == 200


def test_teacher_accounts_admin_only(world):
    as_, _ = world
    admin, ilqar = as_('admin'), as_('ilqar')
    assert ilqar.get('/api/teachers').status_code == 403
    r = admin.post('/api/teachers', json={'full_name': 'Səmədzadə Gülay', 'subjects': ['Az. dili']})
    assert r.status_code == 200 and len(r.json()['initial_password']) >= 10 and r.json()['login'] == 'M-001'
    assert admin.post('/api/teachers', json={'full_name': 'Başqa Müəllim'}).json()['login'] == 'M-002'


def test_roster_import_from_utis(world):
    import os
    from app.seed import UTIS_XLSX, DIM_XLSX
    import pytest
    if not UTIS_XLSX.exists():
        pytest.skip('UTİS faylı yoxdur')
    as_, _ = world
    admin = as_('admin')
    cid = mk_class(admin, 'X e', utis_class='10 e').json()['id']
    with open(UTIS_XLSX, 'rb') as u, open(DIM_XLSX, 'rb') as d:
        r = admin.post('/api/import/roster', files={'utis': ('u.xlsx', u.read()), 'dim': ('d.xlsx', d.read())})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j['matched_classes'] == ['X e'] and len(j['added']) == 18 and len(j['added'][0]['pin']) == 4
    with open(UTIS_XLSX, 'rb') as u:
        again = admin.post('/api/import/roster', files={'utis': ('u.xlsx', u.read())}).json()
    assert again['added'] == []                                     # təkrar import şagird təkrarlamır
    assert as_('ilqar').post('/api/import/roster', files={'utis': ('u.xlsx', b'x')}).status_code == 403


def test_class_pin_sheet(world):
    as_, _ = world
    admin = as_('admin')
    cid = mk_class(admin).json()['id']
    join(admin, cid)
    mk_student(admin, cid)
    mk_student(admin, cid, name='İkinci Şagird Test qızı', birth='2011-06-06')
    r = admin.post(f'/api/students/by-class/{cid}/reset-pins').json()
    assert r['class_name'] == 'X c' and len(r['students']) == 2 and all(len(x['pin']) == 4 for x in r['students'])
    from fastapi.testclient import TestClient
    from app.main import app
    x = r['students'][0]
    with TestClient(app) as st:
        assert st.post('/api/auth/login', json={'login': x['portal_code'], 'password': x['pin']}).status_code == 200
    assert as_('ilqar').post(f'/api/students/by-class/{cid}/reset-pins').status_code == 403
