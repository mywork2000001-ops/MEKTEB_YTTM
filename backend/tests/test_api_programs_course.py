"""Proqram seçiminin genişləndirilməsi (docs/repetitor-proqramlar-promtu.md): səssiz imtina, sinif rəqəmi, mənbə məkan,
kurs müddəti, kurs formatlı proqramlar, bölmə seçimi, Word planının kitabxanaya yüklənməsi."""


def _builtin(c, grade):
    return next(p for p in c.get('/api/programs').json() if p['builtin'] and p['grade'] == grade and p['kind'] == 'adaptive'
                and 'Sinif testləri' in p['title'])


def test_join_program_without_slots_and_grade_hint(world):
    as_, _ = world
    t = as_('ilqar')
    g = t.post('/api/classes', json={'name': 'Həftəsonu qrupu', 'kind': 'qrup'}).json()
    assert g['grade'] is None
    x9 = _builtin(t, 9)
    r = t.post(f"/api/classes/{g['id']}/join", json={'subject': 'Riyaziyyat', 'weekly_hours': 2, 'program_id': x9['id']})
    assert r.status_code == 400 and 'dərs saatlarını' in r.json()['detail']
    lib = t.get('/api/programs', params={'class_id': g['id'], 'grade_hint': 9}).json()
    assert lib[0]['grade'] == 9 and lib[0]['fits']
    r = t.post(f"/api/classes/{g['id']}/join", json={'subject': 'Riyaziyyat', 'weekly_hours': 2, 'slots': {'0': [1, 2]},
                                                     'program_id': x9['id'], 'grade': 9})
    assert r.status_code == 200 and r.json()['grade'] == 9


def test_program_workspace_label(world):
    as_, _ = world
    t = as_('ilqar')
    pid = t.post('/api/classes', json={'name': 'Fərdi IX', 'kind': 'adi', 'private': True}).json()['id']
    ta = t.post(f'/api/classes/{pid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 1, 'slots': {'0': [1]},
                                                  'program_id': _builtin(t, 9)['id']}).json()['mine']['ta_id']
    assert t.post(f'/api/programs/save/{ta}', json={}).status_code == 200
    lib = t.get('/api/programs').json()
    assert {p['workspace'] for p in lib if p['builtin']} == {None}
    assert any(p['workspace'] == 'private' for p in lib if p['mine'])
