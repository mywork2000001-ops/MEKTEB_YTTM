"""Fərdi hazırlıq: görüş = N akademik saat (45 dəq., fasilə 5), kurs planı görüşlərə görə, skript (docs/ferdi-perspektiv-plan-promtu.md)."""
import datetime as dt
import re


def test_a_meeting_units_and_parts():
    from app.api.classes import meeting_end, meeting_parts, meeting_units
    assert meeting_units('17:00', '18:30') == 2 and meeting_units('17:00', '18:35') == 2 and meeting_units('17:00', '18:35') == 2
    assert meeting_units('17:00', '17:20') == 1 and meeting_units('17:00', '18:00') == 1 and meeting_units('17:00', '19:15') == 3
    assert meeting_parts('17:00', '18:30') == [('17:00', '17:45'), ('17:50', '18:35')]
    assert meeting_end('17:00', '18:30') == '18:35' and meeting_end('10:00', '11:00') == '10:45'


def _build(times, start, end, off=None, sections=None, program='buraxilis9'):
    from scripts import ferdi_plan as fp
    tpl = fp.filter_sections(fp.builtin_template(program), sections)
    tmap = fp.times_map([fp.parse_time(t) for t in times])
    lessons, slots, rep = fp.build(tpl, tmap, start, end, off or {})
    return fp, tpl, tmap, lessons, slots, rep


def test_b_two_meetings_one_holiday():
    start, end = dt.date(2026, 10, 20), dt.date(2026, 11, 30)
    _, _, _, _, slots, _ = _build(['1 17:00-18:30', '4 10:00-11:30'], start, end)
    days = {d for d, _ in slots}
    tue = [d for d in days if d.weekday() == 1]
    assert len(slots) == 2 * 2 * len(days) // 2 * 1 and len(slots) == 2 * len(days)          # hər gün 2 saat
    _, _, _, _, slots2, _ = _build(['1 17:00-18:30', '4 10:00-11:30'], start, end, off={tue[1]: 'Bayram'})
    assert len(slots2) == len(slots) - 2


def test_c_topics_in_book_order_even_hours():
    fp, tpl, tmap, lessons, slots, rep = _build(['1 17:00-18:30', '3 17:00-18:30', '4 10:00-11:30'], dt.date(2026, 10, 20), dt.date(2027, 5, 31))
    assert len(lessons) == len(slots) and rep['budget']['meetings'] * 2 == rep['budget']['hours']
    topics = [t for s in tpl['sections'] for t in s['topics']]
    assert topics[0].startswith('V sinif') and topics[-1].startswith('IX sinif')
    order = {t: i for i, t in enumerate(topics)}
    seen, counts = [], {}
    for l in lessons:
        m = next((t for t in topics if l['topic'].startswith(t + '.') or l['topic'].startswith(t + ' (')), None)
        if m:
            counts[m] = counts.get(m, 0) + 1
            if not seen or seen[-1] != m:
                seen.append(m)
    assert [order[t] for t in seen] == sorted(order[t] for t in seen)         # kitab ardıcıllığı
    assert counts and all(n % 2 == 0 for n in counts.values())                  # saat sayı cüt (görüş bölünmür)
    first = next(l for l in lessons if l['topic'].startswith(topics[0]))
    assert first['topic'] == f'{topics[0]}. Nəzəri xülasə və nümunə məsələlər'
    assert any(l['topic'] == f'{topics[0]}. Sinif testi və təhlil' for l in lessons)
    assert all('variant' not in (l['resources'] or '').lower() for l in lessons)


def test_mock_is_whole_meeting():
    _, _, _, lessons, _, _ = _build(['0 17:00-18:30', '1 17:00-18:30', '3 17:00-18:30', '4 17:00-18:30', '5 10:00-11:30'], dt.date(2026, 10, 20), dt.date(2027, 5, 31))
    idx = [i for i, l in enumerate(lessons) if l['topic'].startswith('Aralıq sınaq')]
    assert idx and len(idx) % 2 == 0 and all(i % 2 == 0 for i in idx[::2]) and all(b == a + 1 for a, b in zip(idx[::2], idx[1::2]))


def test_one_hour_meetings_keep_old_behaviour():
    from app.programs import expand_course
    tpl = {'format': 'course', 'sections': [{'section': 'S', 'topics': ['A', 'B']}], 'mock_after_section': False,
           'mock_every': 0, 'final_mock': False}
    days = [dt.date(2026, 11, 2) + dt.timedelta(days=i) for i in range(4)]
    assert expand_course(tpl, days, dt.date(2026, 12, 27), [1, 1, 1, 1]) == expand_course(tpl, days, dt.date(2026, 12, 27))


def _private_ta(t, name='Fərdi IX'):
    g = t.post('/api/classes', json={'name': name, 'kind': 'adi', 'private': True}).json()['id']
    prep = next(p for p in t.get('/api/programs').json() if p['builtin'] and p['course'] and p['grade'] == 9)
    return g, prep


def test_d_time_change_replans_future_only_and_budget(world):
    as_, S = world
    t = as_('ilqar')
    g, prep = _private_ta(t)
    body = {'subject': 'Riyaziyyat', 'weekly_hours': 1, 'program_id': prep['id'], 'starts_on': '2026-10-20', 'ends_on': '2027-05-31',
            'times': [{'weekday': 1, 'start': '17:00', 'end': '18:30'}]}
    r = t.post(f'/api/classes/{g}/join', json=body).json()
    ta = r['mine']['ta_id']
    assert r['budget']['hours'] == 2 * r['budget']['meetings'] and r['budget']['status'] in ('ok', 'tight', 'short')
    before = t.get(f'/api/plan/{ta}').json()
    # vaxt əlavə olunur – proqram avtomatik yenidən açılır, cavabda büdcə var
    body2 = {**body, 'times': body['times'] + [{'weekday': 4, 'start': '10:00', 'end': '11:30'}]}
    r2 = t.post(f'/api/classes/{g}/join', json=body2).json()
    assert r2['budget']['hours'] > r['budget']['hours']
    after = t.get(f'/api/plan/{ta}').json()
    n_b = len(before.get('lessons') or before.get('items') or [])
    n_a = len(after.get('lessons') or after.get('items') or [])
    assert n_a > n_b


def test_journal_meeting_attendance_written_once(world):
    as_, S = world
    t = as_('ilqar')
    g, prep = _private_ta(t, 'Fərdi jurnal')
    r = t.post(f'/api/classes/{g}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 1, 'program_id': prep['id'],
                                               'starts_on': '2026-10-01', 'ends_on': '2027-05-31',
                                               'times': [{'weekday': 1, 'start': '17:00', 'end': '18:30'}]})
    assert r.status_code == 200, r.text
    ta = r.json()['mine']['ta_id']
    st = t.post('/api/students', json={'full_name': 'Şagird Bir oğlu', 'class_id': g})
    assert st.status_code in (200, 201), st.text
    sid = st.json()['id']
    day = t.get(f'/api/journal/{ta}/day', params={'date': '2026-10-06'}).json()['lessons']
    assert [l['period'] for l in day] == [0, 1]
    t.put(f'/api/journal/{ta}/entry', json={'date': '2026-10-06', 'period': 0, 'attendance': {sid: 'yox'}})
    day = t.get(f'/api/journal/{ta}/day', params={'date': '2026-10-06'}).json()['lessons']
    assert [l['entry']['attendance'] for l in day] == [{str(sid): 'yox'}, {str(sid): 'yox'}] or \
        [l['entry']['attendance'] for l in day] == [{sid: 'yox'}, {sid: 'yox'}]


def test_e_script_matches_api(world, tmp_path):
    as_, S = world
    t = as_('ilqar')
    g, prep = _private_ta(t, 'Fərdi skript')
    times = [{'weekday': 1, 'start': '17:00', 'end': '18:30'}, {'weekday': 4, 'start': '10:00', 'end': '11:30'}]
    r = t.post(f'/api/classes/{g}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 1, 'program_id': prep['id'],
                                               'starts_on': '2026-10-20', 'ends_on': '2027-05-31', 'times': times}).json()
    ta = r['mine']['ta_id']
    pv = t.get(f"/api/programs/{prep['id']}/preview/{ta}").json()
    api_topics = [x['topic'] for x in pv['lessons_list']] if 'lessons_list' in pv else None
    from app.db import get_db  # noqa: F401
    from app.main import app
    db = next(app.dependency_overrides[get_db]())
    from app.models import TeachingAssignment
    from scripts import ferdi_plan as fp
    obj = db.get(TeachingAssignment, ta)
    holidays = {h.date: h.name for h in db.query(__import__('app.models', fromlist=['Holiday']).Holiday).all()}
    holidays.update({dt.date(2027, 1, 27) + dt.timedelta(days=i): 'Yarımil fasiləsi' for i in range(5)})      # capacity() I–II yarımil arası günləri sayır
    tpl = fp.builtin_template('buraxilis9')
    tmap = fp.times_map([(1, '17:00', '18:30'), (4, '10:00', '11:30')])
    assert tmap == obj.times
    lessons, slots, rep = fp.build(tpl, tmap, dt.date(2026, 10, 20), dt.date(2027, 5, 31), holidays)
    assert len(lessons) == pv['lessons']
    out = tmp_path / 'p.csv'
    fp.write_out(str(out), fp.rows_of(lessons, slots, tmap), rep, 'x')
    assert re.search(r'görüş', out.read_text(encoding='utf-8-sig'))
    from app.programs import lessons_for
    p = db.get(__import__('app.models', fromlist=['PlanProgram']).PlanProgram, prep['id'])
    ls, rep2 = lessons_for(db, p, obj)
    assert [l['topic'] for l in ls] == [l['topic'] for l in lessons] and rep2['budget'] == rep['budget'] | {}


def test_migrate_plan_ta_keeps_old_period():
    from scripts.ferdi_units_migrate import plan_ta
    nt, ns, added = plan_ta({'1:3': '17:00–18:30', '5:0': '10:00–10:45'}, {'1': [3], '5': [0]})
    assert nt['1:3'] == '17:00–17:45' and added == 1 and nt['1:0'] == '17:50–18:35' and nt['5:0'] == '10:00–10:45'
    assert ns == {'1': [0, 3], '5': [0]}
    assert plan_ta(nt, ns)[2] == 0                                   # təkrar işlətmək dəyişmir