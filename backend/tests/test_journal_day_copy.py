"""Jurnal «Gündəlik»: bir gündə iki dərs – davamiyyət 1-ci yazılmış dərsdən 2-ciyə təklif olunur (docs/jurnal-gundelik-promtu.md)."""
from .test_api_portal import setup


def test_prev_attendance_and_day_nav(world):
    admin, ta, cid, st, _ = setup(world)                     # Ç.a. 1-ci və 5-ci saat
    a, b, c = (str(s['id']) for s in st)
    D = '2026-09-29'
    day = admin.get(f'/api/journal/{ta}/day', params={'date': D}).json()
    assert [l['period'] for l in day['lessons']] == [1, 5] and all(l['prev_attendance'] is None for l in day['lessons'])
    assert day['prev_day'] == '2026-09-22' and day['next_day'] == '2026-10-06'      # yalnız dərs günləri
    r = admin.put(f'/api/journal/{ta}/entry', json={'date': D, 'period': 1, 'attendance': {a: 'yox', b: 'gecikdi', c: 'var'},
                                                     'marks': [{'student_id': int(c), 'kind': 'şifahi', 'grade': 5}]})
    assert r.status_code == 200, r.text
    l1, l5 = admin.get(f'/api/journal/{ta}/day', params={'date': D}).json()['lessons']
    assert l1['prev_attendance'] is None
    assert l5['prev_attendance'] == {'period': 1, 'attendance': {a: 'yox', b: 'gecikdi', c: 'var'}}
    assert l5['entry']['exists'] is False                    # heç nə avtomatik YAZILMIR – yalnız təklif
    # 2-ci dərs yazılandan sonra təklif yoxdur; 1-ci dərsi dəyişmək 2-ciyə toxunmur
    admin.put(f'/api/journal/{ta}/entry', json={'date': D, 'period': 5, 'attendance': {a: 'var', b: 'var', c: 'var'}})
    admin.put(f'/api/journal/{ta}/entry', json={'date': D, 'period': 1, 'attendance': {a: 'üzrlü', b: 'var', c: 'var'}})
    l1, l5 = admin.get(f'/api/journal/{ta}/day', params={'date': D}).json()['lessons']
    assert l5['prev_attendance'] is None and l5['entry']['attendance'] == {a: 'var', b: 'var', c: 'var'}
    assert l5['entry']['marks'] == []                        # qiymət köçmür
