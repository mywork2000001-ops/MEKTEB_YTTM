"""Sinif rəhbərinin davamiyyəti: dərs cədvəli (sistem + rəhbər), gündəlik qeyd (jurnal əsasdır), aylıq cədvəl."""
import datetime as dt

from .test_api_analytics import setup


def _hr(c, cid):
    me = c.get('/api/auth/me').json()['id']
    assert c.put(f'/api/classes/{cid}/homeroom', json={'teacher_id': me}).status_code == 200


def test_timetable_day_and_journal_priority(world, monkeypatch):
    monkeypatch.setattr('app.api.homeroom_att.today', lambda: dt.date(2026, 9, 30))
    c, ta, good, weak, new = setup(world)
    cid = c.get('/api/classes').json()[0]['id']
    _hr(c, cid)
    tt = c.get(f'/api/homeroom/{cid}/timetable').json()
    assert sum(x['locked'] for x in tt['cells']) == 5 and [p['period'] for p in tt['periods']] == list(range(1, 9))
    # sistemdəki dərsin yerinə yazmaq olmaz; boş saatlara – olar
    assert c.put(f'/api/homeroom/{cid}/timetable', json=[{'weekday': 0, 'period': 1, 'subject': 'Kimya'}]).status_code == 400
    r = c.put(f'/api/homeroom/{cid}/timetable', json=[{'weekday': 0, 'period': 2, 'subject': ' Fizika ', 'teacher': 'Əliyev R.'},
                                                      {'weekday': 1, 'period': 3, 'subject': 'Tarix'}])
    manual = [x for x in r.json()['cells'] if not x['locked']]
    assert [(x['weekday'], x['period'], x['subject']) for x in manual] == [(0, 2, 'Fizika'), (1, 3, 'Tarix')]

    # 21.09 (B.e.): 1-ci saat – riyaziyyat (jurnal yazılıb, zəif şagird qayıb), 2-ci saat – fizika (rəhbər qeyd edir)
    d = c.get(f'/api/homeroom/{cid}/attendance/day', params={'date': '2026-09-21'}).json()
    assert [p['period'] for p in d['periods']] == [1, 2] and d['periods'][0]['lessons'][0]['written']
    w = next(s for s in d['students'] if s['id'] == weak)
    assert w['cells']['1'] == {'status': 'yox', 'source': 'jurnal', 'reason': None} and w['cells']['2'] is None
    r = c.put(f'/api/homeroom/{cid}/attendance/day', json={'date': '2026-09-21', 'marks': [
        {'period': 1, 'student_id': weak, 'status': 'var'},                     # jurnal əsasdır – dəyişmir
        {'period': 2, 'student_id': weak, 'status': 'üzrlü', 'reason': 'arayış'},
        {'period': 2, 'student_id': good, 'status': 'var'}]}).json()
    assert r['saved'] == 2 and r['locked'] == 1
    w = next(s for s in r['students'] if s['id'] == weak)
    assert w['cells']['1']['status'] == 'yox' and w['cells']['2'] == {'status': 'üzrlü', 'source': 'rəhbər', 'reason': 'arayış'}
    # silmə, yanlış saat, gələcək, həftəsonu
    assert c.put(f'/api/homeroom/{cid}/attendance/day', json={'date': '2026-09-21', 'marks': [
        {'period': 2, 'student_id': good, 'status': None}]}).json()['saved'] == 1
    assert c.put(f'/api/homeroom/{cid}/attendance/day', json={'date': '2026-09-21', 'marks': [
        {'period': 5, 'student_id': good, 'status': 'var'}]}).status_code == 400
    assert c.put(f'/api/homeroom/{cid}/attendance/day', json={'date': '2026-10-05', 'marks': []}).status_code == 400
    assert c.put(f'/api/homeroom/{cid}/attendance/day', json={'date': '2026-09-20', 'marks': []}).status_code == 400
    assert c.get(f'/api/homeroom/{cid}/attendance/day', params={'date': '2026-09-20'}).json()['off_reason'] == 'Həftəsonu'

    m = c.get(f'/api/homeroom/{cid}/attendance/month', params={'month': '2026-09'}).json()
    rw = next(x for x in m['rows'] if x['student_id'] == weak)
    assert rw['missed'] == 6 and rw['excused'] == 1 and rw['unexcused'] == 5 and rw['absence_warning']
    assert len(m['days']) == 12 and m['unmarked'] > 0                          # 29–30.09 jurnalı yazılmayıb
    # icmal da birləşmiş mənbədən
    h = c.get(f'/api/homeroom/{cid}').json()
    assert next(x for x in h['students'] if x['student_id'] == weak)['missed'] == 6


def test_consecutive_absence_warning_and_access(world, monkeypatch):
    monkeypatch.setattr('app.api.homeroom_att.today', lambda: dt.date(2026, 9, 30))
    as_, _ = world
    c = as_('admin')
    cid = c.post('/api/classes', json={'name': 'X c'}).json()['id']
    sid = c.post('/api/students', json={'full_name': 'Bir Şagird oğlu', 'class_id': cid}).json()['id']
    _hr(c, cid)
    c.put(f'/api/homeroom/{cid}/timetable', json=[{'weekday': w, 'period': 1, 'subject': 'Ədəbiyyat'} for w in range(5)])
    for d in ('2026-09-22', '2026-09-23', '2026-09-24'):
        assert c.put(f'/api/homeroom/{cid}/attendance/day', json={'date': d, 'marks': [
            {'period': 1, 'student_id': sid, 'status': 'yox'}]}).status_code == 200
    r = c.get(f'/api/homeroom/{cid}/attendance/month', params={'month': '2026-09'}).json()['rows'][0]
    assert r['max_absent_days'] == 3 and r['consecutive_warning'] and r['lessons'] == 3
    assert as_('ilqar').get(f'/api/homeroom/{cid}/attendance/day').status_code == 403     # rəhbər deyil
