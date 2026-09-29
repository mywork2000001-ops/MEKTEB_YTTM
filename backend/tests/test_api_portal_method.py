"""Şagird – metodik: müəllimin rəyi görünür, summativə hazırlıq (mövzular, standartlar), növbəti dərsin ev tapşırığı,
summativdə tapşırıq üzrə ✓/✗ və zəif standartlar; səviyyə/risk şagirdə göndərilmir."""
import datetime as dt

from app.models import PlanLesson

from .test_api_portal import clock, setup, student_client  # noqa: F401 – clock fixture


def test_student_feedback_and_preparation(world, clock, monkeypatch):
    d0 = dt.date(2026, 9, 29)
    for mod in ('app.api.portal', 'app.api.journal', 'app.api.exams'):
        monkeypatch.setattr(f'{mod}.today', lambda: d0)
    as_, S = world
    admin, ta, cid, st, ids = setup(world)
    with S() as db:                                         # 6-cı dərs (29.09, 5-ci saat) – KSQ-1
        for pl in db.query(PlanLesson).filter_by(assignment_id=ta):
            pl.standards = [f'1.{pl.seq}.1']
            if pl.seq == 6:
                pl.assessment_type, pl.exam_no = 'KSQ', 1
        db.commit()
    sid = st[0]['id']
    admin.put(f'/api/journal/{ta}/entry', json={'date': '2026-09-29', 'period': 1, 'homework': 'S 1–5',
                                                'attendance': {sid: 'var'},
                                                'marks': [{'student_id': sid, 'kind': 'şifahi', 'grade': 4,
                                                           'comment': 'Düsturu düz seçdin, hesablamanı yoxla'}]})
    # həmin gün 5-ci saat (KSQ) ev tapşırığı verilmədən yazılır – 1-ci saatın ev tapşırığı itməməlidir
    assert admin.put(f'/api/journal/{ta}/entry', json={'date': '2026-09-29', 'period': 5,
                                                       'attendance': {sid: 'var'}}).status_code == 200
    s = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    day = s.get('/api/portal/day', params={'date': '2026-09-29'}).json()['lessons']
    assert day[0]['marks'][0]['comment'] == 'Düsturu düz seçdin, hesablamanı yoxla'

    u = s.get('/api/portal/upcoming').json()
    ex = u['exams'][0]
    assert (ex['kind'], ex['no'], ex['date'], ex['days']) == ('KSQ', 1, '2026-09-29', 0)
    assert [x['seq'] for x in ex['topics']] == [1, 2, 3, 4, 5] and ex['standards'][0] == '1.1.1'
    assert u['homework'] == [{'subject': 'Riyaziyyat', 'class_name': 'X e', 'homework': 'S 1–5', 'given': '2026-09-29',
                              'due': '2026-10-06', 'due_period': 1, 'due_time': u['homework'][0]['due_time']}]

    k = admin.post(f'/api/exams/{ta}', json={'kind': 'KSQ', 'no': 1, 'semester': 1, 'date': '2026-09-29',
                                             'items': [{'n': 1, 'points': 5, 'standard': '1.2.1'},
                                                       {'n': 2, 'points': 5, 'standard': '1.3.1'}]}).json()
    admin.put(f'/api/exams/{ta}/{k["id"]}/scores', json=[{'student_id': sid, 'item_marks': [1, 0]}])
    r = s.get('/api/portal/results').json()['subjects'][0]['exams'][0]
    assert [i['ok'] for i in r['items']] == [True, False] and r['weak_standards'] == ['1.3.1'] and r['grade'] == 3
    # mənfi etiket yoxdur: səviyyə, risk, reytinq şagirdə göndərilmir
    blob = str(s.get('/api/portal/results').json()) + str(s.get('/api/portal/analytics').json())
    assert 'Zəif' not in blob and 'risk' not in blob and 'rating' not in blob
