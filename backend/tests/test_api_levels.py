"""Səviyyə qrupları: bölgü (sabit həddlər / üçdəbir), önizləmə → təsdiq, kilid, histerezisli təkliflər, tarixçə,
paralel siniflərdən səviyyə qrupu, IX sinifdə buraxılış balı nəzərə alınmır."""
from app.models import Student, TeachingAssignment

from .test_api_portal import setup


def _class(admin, S, name, scores):
    cid = admin.post('/api/classes', json={'name': name}).json()['id']
    admin.post(f'/api/classes/{cid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 1, 'slots': {}})
    ids = []
    for i, sc in enumerate(scores):
        sid = admin.post('/api/students', json={'full_name': f'{name} Şagird{i:02d} oğlu', 'class_id': cid}).json()['id']
        ids.append(sid)
    with S() as db:
        for sid, sc in zip(ids, scores):
            db.get(Student, sid).score_math = sc
        db.commit()
        ta = db.query(TeachingAssignment).filter_by(class_id=cid).one().id
    return ta, ids


def _math(S, sid, v):
    with S() as db:
        db.get(Student, sid).score_math = v
        db.commit()


def test_levels_preview_apply_lock_suggest(world):
    as_, S = world
    admin = setup(world)[0]
    ta, ids = _class(admin, S, 'X k', [95, 88, 80, 72, 65, 55, 45, 30, 20, None])
    p = admin.post(f'/api/levels/{ta}/preview').json()
    assert p['counts'] == {'Zəif': 2, 'Orta': 3, 'Güclü': 4} and p['used']['buraxilis'] == 9
    row = {r['student_id']: r for r in p['rows']}
    assert row[ids[9]]['proposed'] is None and row[ids[0]]['components']['buraxilis'] == 95
    t = admin.post(f'/api/levels/{ta}/preview', params={'mode': 'tercile'}).json()
    assert t['counts'] == {'Zəif': 3, 'Orta': 3, 'Güclü': 3}
    assert as_('yad').post(f'/api/levels/{ta}/preview').status_code == 404

    assert admin.post(f'/api/levels/{ta}/apply', json={'student_ids': ids}).json()['applied'] == 9
    g = admin.get(f'/api/levels/{ta}').json()['groups']
    assert [len(g[k]) for k in ('Zəif', 'Orta', 'Güclü', 'Təyin edilməyib')] == [2, 3, 4, 1]
    assert g['Güclü'][0]['source'] == 'auto' and not g['Güclü'][0]['locked']
    # analitikada mənbə «bölgü»
    a = admin.get(f'/api/analytics/{ta}').json()['students']
    assert next(r for r in a if r['student_id'] == ids[0])['level_source'] == 'bölgü'

    # müəllim köçürür – kilidli; üçdəbir bölgü kilidliyə toxunmur
    assert admin.put(f'/api/levels/{ta}/{ids[6]}', json={'level': 'Zəif'}).status_code == 200
    admin.post(f'/api/levels/{ta}/apply', json={'student_ids': ids, 'mode': 'tercile'})
    g = admin.get(f'/api/levels/{ta}').json()['groups']
    lk = next(x for x in g['Zəif'] if x['student_id'] == ids[6])
    assert lk['locked'] and lk['source'] == 'manual'
    admin.post(f'/api/levels/{ta}/apply', json={'student_ids': ids})                     # yenidən sabit həddlər

    # təkliflər (histerezis 5 bal): 72 → 60 (Güclü → Orta), 65 → 76 (Orta → Güclü), 65 → 72 olsaydı – təklif yox
    _math(S, ids[3], 60)
    _math(S, ids[4], 76)
    _math(S, ids[5], 68)                                       # Orta, 68 < 75 – təklif yoxdur
    _math(S, ids[6], 99)                                       # kilidli – təklif yoxdur
    sug = admin.get(f'/api/levels/{ta}/suggestions').json()
    assert {(s['student_id'], s['current'], s['proposed']) for s in sug} == {(ids[3], 'Güclü', 'Orta'), (ids[4], 'Orta', 'Güclü')}
    assert admin.get(f'/api/levels/{ta}').json()['suggestions'] == 2
    assert admin.post(f'/api/levels/{ta}/suggestions/accept', json={'student_ids': [ids[4]]}).json()['accepted'] == 1
    assert len(admin.get(f'/api/levels/{ta}/suggestions').json()) == 1
    h = admin.get(f'/api/levels/{ta}/history').json()
    assert h[0]['student_id'] == ids[4] and (h[0]['old'], h[0]['new']) == ('Orta', 'Güclü')
    # səviyyəni götürmək
    admin.put(f'/api/levels/{ta}/{ids[0]}', json={'level': None})
    assert ids[0] in [x['student_id'] for x in admin.get(f'/api/levels/{ta}').json()['groups']['Təyin edilməyib']]


def test_cross_class_group_and_grade9(world):
    as_, S = world
    admin = setup(world)[0]
    ta1, a = _class(admin, S, 'X k', [90, 85, 40])
    ta2, b = _class(admin, S, 'X m', [95, 30])
    body = {'ta_ids': [ta1, ta2], 'level': 'Güclü', 'name': 'X – riyaziyyat, güclü qrup'}
    assert admin.post('/api/levels/cross-class', json=body).status_code == 400            # hələ bölgü yoxdur
    admin.post(f'/api/levels/{ta1}/apply', json={'student_ids': a})
    admin.post(f'/api/levels/{ta2}/apply', json={'student_ids': b})
    r = admin.post('/api/levels/cross-class', json=body)
    assert r.status_code == 200 and r.json()['members'] == 3
    assert admin.post('/api/levels/cross-class', json=body).status_code == 409
    les = {x['class_name']: x for x in admin.get('/api/my/lessons').json()}
    assert les['X – riyaziyyat, güclü qrup']['kind'] == 'qrup'
    assert next(c for c in admin.get('/api/classes').json() if c['name'] == 'X – riyaziyyat, güclü qrup')['grade'] == 10
    # IX sinif: buraxılış balı (IX-un özü) bölgüdə istifadə olunmur
    ta9, _ = _class(admin, S, 'IX k', [90, 20])
    assert admin.post(f'/api/levels/{ta9}/preview').json()['used']['buraxilis'] == 0
