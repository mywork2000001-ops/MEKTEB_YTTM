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


def test_course_dates_limit_slots(world):
    as_, _ = world
    t = as_('ilqar')
    pid = t.post('/api/classes', json={'name': 'Qış kursu', 'kind': 'adi', 'private': True}).json()['id']
    base = {'subject': 'Riyaziyyat', 'weekly_hours': 2, 'slots': {'1': [1], '3': [1]}}
    assert t.post(f'/api/classes/{pid}/join', json={**base, 'starts_on': '2027-02-01', 'ends_on': '2026-11-01'}).status_code == 400
    assert t.post(f'/api/classes/{pid}/join', json={**base, 'starts_on': '2025-01-01'}).status_code == 400
    r = t.post(f'/api/classes/{pid}/join', json={**base, 'starts_on': '2026-11-02', 'ends_on': '2027-01-31'}).json()
    ta = r['mine']['ta_id']
    assert r['mine']['starts_on'] == '2026-11-02'
    pv = t.get(f"/api/programs/{_builtin(t, 9)['id']}/preview/{ta}").json()
    total = pv['sem1_slots'] + pv['sem2_slots']
    assert 15 <= total <= 26                                             # ~13 həftə × 2 dərs, bayramlar çıxılır
    assert t.get(f'/api/journal/{ta}/day', params={'date': '2026-10-06'}).json()['lessons'] == []       # kursdan əvvəl
    assert len(t.get(f'/api/journal/{ta}/day', params={'date': '2026-11-03'}).json()['lessons']) == 1


def test_expand_course_rules():
    import datetime as dt
    from app.programs import expand_course
    tpl = {'format': 'course', 'sections': [{'section': 'Cəbr', 'topics': ['A', 'B']}, {'section': 'Həndəsə', 'topics': ['C']}],
           'mock_after_section': True, 'mock_every': 0, 'final_mock': True}
    days = [dt.date(2026, 11, 2) + dt.timedelta(days=i) for i in range(12)]
    les, warn = expand_course(tpl, days, dt.date(2026, 12, 27))
    assert len(les) == 12 and not warn
    assert not any(l['assessment_type'] in ('KSQ', 'BSQ', 'diaqnostik') for l in les)
    assert [l['topic'] for l in les if 'Sınaq' in l['topic'] or 'sınaq' in l['topic']] == ['Sınaq: Cəbr', 'Sınaq: Həndəsə', 'Yekun sınaq imtahanı']
    assert {l['semester'] for l in les} == {1}
    les2, warn2 = expand_course(tpl, days[:3], dt.date(2026, 12, 27))       # yuva az – sınaqlar çıxır
    assert len(les2) == 3 and warn2 and not any('ınaq' in l['topic'] for l in les2)
    les3, _ = expand_course({**tpl, 'mock_after_section': False, 'mock_every': 2, 'final_mock': False}, days[:9], dt.date(2026, 12, 27))
    assert len(les3) == 9 and sum('Aralıq sınaq' in l['topic'] for l in les3) == 2


def test_prep_builtins_and_custom_course(world):
    as_, _ = world
    t = as_('ilqar')
    lib = t.get('/api/programs').json()
    prep = {p['grade']: p for p in lib if p['builtin'] and p['course']}
    assert set(prep) == {9, 11} and 'buraxilis9' in prep[9]['purposes'] and 'qebul' in prep[11]['purposes']
    d = t.get(f"/api/programs/{prep[9]['id']}").json()
    secs = d['outline'][0]['sections']
    assert secs[0]['section'].startswith('V sinif') and secs[-1]['section'].startswith('IX sinif')
    r = t.post('/api/programs/course', json={'title': 'Olimpiada hazırlığı', 'grade': 8, 'purposes': ['olimpiada'],
                                             'outline': '# Ədədlər nəzəriyyəsi\n1. Bölünmə\n- Qalıqlar\n\n# Kombinatorika\nDirixle prinsipi',
                                             'mock_after_section': True})
    assert r.status_code == 200, r.text
    c = r.json()
    assert c['course'] and c['topics'] == 3 and c['mine'] and c['purposes'] == ['olimpiada']
    assert t.post('/api/programs/course', json={'title': 'Boş', 'outline': '# Yalnız bölmə'}).status_code == 400
    pid = t.post('/api/classes', json={'name': 'Olimpiada', 'kind': 'adi', 'private': True}).json()['id']
    ta = t.post(f'/api/classes/{pid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 1, 'slots': {'5': [1]},
                                                  'starts_on': '2026-11-07', 'ends_on': '2026-12-26'}).json()['mine']['ta_id']
    pv = t.get(f"/api/programs/{c['id']}/preview/{ta}").json()
    assert pv['ksq'] == pv['bsq'] == 0 and pv['lessons'] == pv['sem1_slots'] + pv['sem2_slots']
    ap = t.post(f"/api/programs/{c['id']}/apply/{ta}").json()
    assert ap['lessons'] == pv['lessons']
    u = t.put(f"/api/programs/{c['id']}/course", json={'title': 'Olimpiada hazırlığı', 'outline': '# A\nx\ny', 'grade': 8})
    assert u.status_code == 200 and u.json()['topics'] == 2
    assert t.put(f"/api/programs/{prep[9]['id']}/course", json={'title': 'Xxx', 'outline': 'a'}).status_code == 403
