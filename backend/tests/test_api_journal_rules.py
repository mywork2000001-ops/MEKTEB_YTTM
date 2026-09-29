"""Metodik qaydalar: KSQ/BSQ günü formativ qiymət yoxdur; onlayn test nəticəsi jurnala; summativi sonradan yazma."""
import datetime as dt

from app.models import PlanLesson

from .test_api_analytics import setup as setup_class
from .test_api_portal import UTC, clock, mk_task, setup, student_client  # noqa: F401 – clock fixture


def test_task_to_journal(world, clock, monkeypatch):
    """Onlayn testin nəticəsi bir düymə ilə jurnala (formativ «test»); qayıb ötürülür; KSQ dərsinə köçürülmür."""
    monkeypatch.setattr('app.services.today', lambda: dt.date(2026, 9, 29))
    monkeypatch.setattr('app.api.journal.today', lambda: dt.date(2026, 9, 29))
    as_, S = world
    admin, ta, cid, st, ids = setup(world)
    t = mk_task(admin, ta, ids, opens_at='2026-09-29T05:00:00Z', closes_at='2026-09-29T06:00:00Z').json()
    clock.t = dt.datetime(2026, 9, 29, 5, 10, tzinfo=UTC)
    for i, stu in enumerate(st[:2]):
        s = student_client(stu['portal_code'], stu['initial_pin'])
        r = s.post(f'/api/portal/tasks/{t["id"]}/start').json()
        by = {q['text']['az']: q['index'] for q in r['questions']}
        ans = {str(by['2+2=?']): 1, str(by['5·2=?']): 0 if i == 0 else 1}
        s.post(f'/api/portal/tasks/{t["id"]}/submit', json={'answers': ans})
    admin.put(f'/api/journal/{ta}/entry', json={'date': '2026-09-29', 'period': 1,
                                                'attendance': {st[0]['id']: 'var', st[1]['id']: 'yox'}})
    res = admin.post(f'/api/tasks/{ta}/{t["id"]}/to-journal', json={}).json()
    assert res['date'] == '2026-09-29' and res['period'] == 1 and res['copied'] == 1
    assert res['skipped'] == [{'full_name': st[1]['full_name'], 'reason': 'həmin dərsdə olmayıb'}]
    day = admin.get(f'/api/journal/{ta}/day', params={'date': '2026-09-29'}).json()['lessons'][0]['entry']
    m = day['marks'][0]
    assert (m['kind'], m['test_correct'], m['test_total'], m['grade']) == ('test', 2, 3, 4)
    assert m['comment'].startswith('Onlayn test')
    again = admin.post(f'/api/tasks/{ta}/{t["id"]}/to-journal', json={'date': '2026-09-29', 'period': 1}).json()
    assert again['copied'] == 0 and again['updated'] == 1                     # təkrar – yenilənir, dublikat yox
    assert admin.post(f'/api/tasks/{ta}/{t["id"]}/to-journal', json={'date': '2026-09-28'}).status_code == 400
    with S() as db:                                                            # 5-ci saat KSQ olsun
        pl = db.query(PlanLesson).filter_by(assignment_id=ta, seq=6).one()
        pl.assessment_type, pl.exam_no = 'KSQ', 1
        db.commit()
    assert admin.post(f'/api/tasks/{ta}/{t["id"]}/to-journal', json={'date': '2026-09-29', 'period': 5}).status_code == 400
    # KSQ günü jurnala formativ qiymət də yazılmır, davamiyyət isə yazılır
    r = admin.put(f'/api/journal/{ta}/entry', json={'date': '2026-09-29', 'period': 5, 'attendance': {st[0]['id']: 'var'},
                                                    'marks': [{'student_id': st[0]['id'], 'kind': 'şifahi', 'grade': 5}]})
    assert r.status_code == 400 and 'KSQ' in r.json()['detail']
    assert admin.put(f'/api/journal/{ta}/entry', json={'date': '2026-09-29', 'period': 5,
                                                       'attendance': {st[0]['id']: 'var'}}).status_code == 200


def test_exam_taken_later(world, monkeypatch):
    """Summativi üzrlü səbəbdən buraxıb sonradan yazan şagird: tarix imtahandan sonra, yarımil içində, bu günə qədər."""
    monkeypatch.setattr('app.api.exams.today', lambda: dt.date(2026, 10, 20))
    c, ta, good, weak, new = setup_class(world)
    k = c.post(f'/api/exams/{ta}', json={'kind': 'KSQ', 'no': 2, 'semester': 1, 'date': '2026-10-05', 'max_points': 10}).json()
    put = lambda body: c.put(f'/api/exams/{ta}/{k["id"]}/scores', json=body)
    assert put([{'student_id': new, 'absent': True}]).status_code == 200
    r = put([{'student_id': new, 'points': 9, 'taken_on': '2026-10-12'}])
    row = next(x for x in r.json()['rows'] if x['student_id'] == new)
    assert r.status_code == 200 and row['grade'] == 5 and row['taken_on'] == '2026-10-12'
    assert put([{'student_id': new, 'points': 9, 'taken_on': '2026-10-01'}]).status_code == 400   # imtahandan əvvəl
    assert put([{'student_id': new, 'points': 9, 'taken_on': '2026-10-25'}]).status_code == 400   # gələcək
    assert put([{'student_id': new, 'absent': True, 'taken_on': '2026-10-12'}]).status_code == 400
    sem = c.get(f'/api/exams/{ta}/semester/1').json()['students']
    assert next(s for s in sem if s['student_id'] == new)['ksq'] == [[1, None], [2, 5]]    # KSQ-1 setup-da var
