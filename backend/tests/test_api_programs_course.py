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


def test_private_real_times(world):
    as_, _ = world
    t, admin = as_('ilqar'), as_('admin')
    sc = admin.post('/api/classes', json={'name': 'X t'}).json()['id']
    times = [{'weekday': 1, 'start': '17:00', 'end': '18:30'}, {'weekday': 5, 'start': '10:00', 'end': '11:00'}]
    assert admin.post(f'/api/classes/{sc}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 2, 'times': times}).status_code == 400
    a = t.post('/api/classes', json={'name': 'IX hazırlıq', 'kind': 'adi', 'private': True}).json()['id']
    b = t.post('/api/classes', json={'name': 'XI hazırlıq', 'kind': 'adi', 'private': True}).json()['id']
    bad = [{'weekday': 1, 'start': '17:00', 'end': '16:00'}]
    assert t.post(f'/api/classes/{a}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 1, 'times': bad}).status_code == 400
    over = [{'weekday': 1, 'start': '17:00', 'end': '18:30'}, {'weekday': 1, 'start': '18:00', 'end': '19:00'}]
    assert t.post(f'/api/classes/{a}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 2, 'times': over}).status_code == 400
    r = t.post(f'/api/classes/{a}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 1, 'times': times})
    assert r.status_code == 200, r.text
    m = r.json()['mine']
    assert m['weekly_hours'] == 2 and m['slots'] == {'1': [0], '5': [0]}
    assert [(x['weekday'], x['start'], x['end']) for x in m['times']] == [(1, '17:00', '18:30'), (5, '10:00', '11:00')]
    # başqa fərdi qrupla toqquşma
    r2 = t.post(f'/api/classes/{b}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 1, 'times': [{'weekday': 1, 'start': '18:00', 'end': '19:00'}]})
    assert r2.status_code == 409 and 'IX hazırlıq' in r2.json()['detail']
    # jurnal və həftəlik cədvəl real vaxtı göstərir
    ta = m['ta_id']
    day = t.get(f'/api/journal/{ta}/day', params={'date': '2026-10-06'}).json()
    assert [l['time'] for l in day['lessons']] == ['17:00–18:30']
    tt = t.get('/api/timetable', params={'date': '2026-10-06'}).json()
    sat = next(d for d in tt['days'] if d['weekday'] == 'Ş.')
    assert [c['time'] for cs in sat['periods'].values() for c in cs] == ['10:00–11:00']
    # vaxt əlavə olunanda köhnə dərs öz sırasını saxlayır
    more = [{'weekday': 1, 'start': '15:00', 'end': '16:00'}] + times
    m2 = t.post(f'/api/classes/{a}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 3, 'times': more}).json()['mine']
    assert {(x['weekday'], x['start']): x['period'] for x in m2['times']}[(1, '17:00')] == 0 and m2['weekly_hours'] == 3


def test_private_group_purpose_and_program_choice(world):
    as_, _ = world
    t, admin = as_('ilqar'), as_('admin')
    assert admin.post('/api/classes', json={'name': 'IX z', 'purpose': 'buraxilis9'}).status_code == 400   # məktəbdə məqsəd yox
    g = t.post('/api/classes', json={'name': 'Buraxılış qrupu', 'kind': 'qrup', 'private': True, 'grade': 9, 'purpose': 'buraxilis9'}).json()
    assert g['purpose'] == 'buraxilis9' and g['grade'] == 9
    lib = t.get('/api/programs', params={'class_id': g['id']}).json()
    assert lib[0]['purpose_fits'] and lib[0]['course'] and lib[0]['grade'] == 9
    q = t.post('/api/classes', json={'name': 'Qəbul qrupu', 'kind': 'qrup', 'private': True, 'grade': 11, 'purpose': 'qebul'}).json()
    assert t.get('/api/programs', params={'class_id': q['id']}).json()[0]['title'].startswith('Buraxılış və qəbul')
    r = t.patch(f"/api/classes/{q['id']}", json={'purpose': 'olimpiada'})
    assert r.status_code == 200 and r.json()['purpose'] == 'olimpiada'
    # məktəb sinfində (IX) DİM sinif proqramı öndə qalır
    sc = admin.post('/api/classes', json={'name': 'IX q'}).json()['id']
    top = admin.get('/api/programs', params={'class_id': sc}).json()[0]
    assert top['grade'] == 9 and not top['course']


def test_section_selection(world):
    import json
    as_, _ = world
    t = as_('ilqar')
    pid = t.post('/api/classes', json={'name': 'Həndəsə qrupu', 'kind': 'adi', 'private': True, 'grade': 9}).json()['id']
    ta = t.post(f'/api/classes/{pid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 2,
                                                  'times': [{'weekday': 1, 'start': '17:00', 'end': '18:00'},
                                                            {'weekday': 3, 'start': '17:00', 'end': '18:00'}]}).json()['mine']['ta_id']
    x9 = _builtin(t, 9)
    secs = t.get(f"/api/programs/{x9['id']}").json()['sections']
    geo = [s['name'] for s in secs if s['part'] == 'Həndəsə']
    assert geo and len(geo) < len(secs)
    pv = t.get(f"/api/programs/{x9['id']}/preview/{ta}", params={'sections': json.dumps(geo)}).json()
    assert pv['lessons'] == pv['sem1_slots'] + pv['sem2_slots']
    assert {l['section'] for l in pv['list']} <= set(geo) | {'Təkrar', 'Diaqnostik qiymətləndirmə', 'Böyük summativ qiymətləndirmə'}
    assert t.get(f"/api/programs/{x9['id']}/preview/{ta}", params={'sections': '[]'}).status_code == 400
    assert t.get(f"/api/programs/{x9['id']}/preview/{ta}", params={'sections': '["Yox"]'}).status_code == 400
    r = t.post(f"/api/programs/{x9['id']}/apply/{ta}", json={'sections': geo}).json()
    assert r['lessons'] == pv['lessons']
    f = t.get(f'/api/programs/for/{ta}').json()
    assert f['main_sections'] == geo
    # əlavə proqram – kursdan yalnız bir bölmə
    prep = next(p for p in t.get('/api/programs').json() if p['builtin'] and p['course'] and p['grade'] == 9)
    one = [t.get(f"/api/programs/{prep['id']}").json()['sections'][0]['name']]
    f2 = t.post(f"/api/programs/{prep['id']}/attach/{ta}", json={'sections': one}).json()
    aid = f2['extra'][0]['id']
    assert f2['extra'][0]['sections'] == one
    d = t.get(f'/api/programs/attached/{aid}').json()
    assert {l['section'] for l in d['lessons_list']} <= set(one) | {'Yekun'}


def test_word_plan_to_library(world):
    import glob
    import os

    import pytest
    from .test_importers import PLANS
    as_, _ = world
    t = as_('ilqar')
    assert t.post('/api/programs/import', files={'file': ('a.txt', b'x', 'text/plain')}).status_code == 400
    assert t.post('/api/programs/import', files={'file': ('a.docx', b'not a docx', 'application/octet-stream')}).status_code == 400
    files = sorted(glob.glob(os.path.join(PLANS, '*.docx')))
    if not files:
        pytest.skip('mənbə planlar yoxdur')
    f = files[0]
    r = t.post('/api/programs/import', files={'file': (os.path.basename(f), open(f, 'rb').read())}, data={'title': 'Köhnə plan', 'grade': '10'})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p['kind'] == 'fixed' and p['lessons'] > 20 and p['mine'] and p['title'] == 'Köhnə plan' and p['grade'] == 10
    assert p['source'].startswith('Word: ') and p['used_by'] == []
    assert any(x['id'] == p['id'] for x in t.get('/api/programs').json())


def test_estimate_before_join(world):
    as_, _ = world
    t = as_('ilqar')
    g = t.post('/api/classes', json={'name': 'Qısa kurs', 'kind': 'adi', 'private': True, 'grade': 9, 'purpose': 'buraxilis9'}).json()
    prep = t.get('/api/programs', params={'class_id': g['id']}).json()[0]
    body = {'class_id': g['id'], 'times': [{'weekday': 1, 'start': '17:00', 'end': '18:00'}], 'starts_on': '2026-11-02', 'ends_on': '2026-12-20',
            'has_summative': False}
    r = t.post(f"/api/programs/{prep['id']}/estimate", json=body).json()
    assert 0 < r['slots'] < 10 and r['warnings'] and 'sığmır' in r['warnings'][0]
    assert t.get('/api/classes').json()[-1]['mine'] is None                       # heç nə yazılmayıb
    bad = t.post(f"/api/programs/{prep['id']}/estimate", json={**body, 'times': [{'weekday': 1, 'start': '18:00', 'end': '17:00'}]}).json()
    assert bad['slots'] == 0 and bad['warnings']


def test_week_view_includes_weekend_for_private(world):
    as_, _ = world
    t = as_('ilqar')
    g = t.post('/api/classes', json={'name': 'Şənbə qrupu', 'kind': 'adi', 'private': True}).json()['id']
    ta = t.post(f'/api/classes/{g}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 1,
                                                'times': [{'weekday': 5, 'start': '10:00', 'end': '11:30'}]}).json()['mine']['ta_id']
    w = t.get(f'/api/plan/{ta}', params={'view': 'week', 'date': '2026-10-07'}).json()
    assert w['to'] == '2026-10-11' and [i['date'] for i in w['items']] == ['2026-10-10']
