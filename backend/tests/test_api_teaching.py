"""Perspektiv plan (işçi plan, «Mövzunu saxla»), jurnal, KSQ/BSQ və yarımil qiyməti."""
import datetime as dt

import pytest

from app.domain.plan import working_plan
from app.models import Holiday, PlanLesson, SchoolClass, TeachingAssignment

# Sentyabr 2026: B.e. 28, Ç.a. 29, Ç. 30; Oktyabr: B.e. 5 ...
SLOTS = {'0': [2], '2': [3, 4]}                       # B.e. 2-ci saat; Ç. 3, 4-cü saat – həftədə 3 saat


def setup_class(world, login='admin', has_summative=True, n=6):
    as_, S = world
    c = as_(login)
    cid = c.post('/api/classes', json={'name': 'X e'}).json()['id']
    c.post(f'/api/classes/{cid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 3, 'slots': SLOTS,
                                               'has_summative': has_summative})
    studs = [c.post('/api/students', json={'full_name': f'Şagird Nömrə{i} oğlu', 'class_id': cid}).json()['id']
             for i in range(3)]
    with S() as db:
        ta = db.query(TeachingAssignment).filter_by(class_id=cid).one()
        for i in range(n):
            db.add(PlanLesson(assignment_id=ta.id, seq=i + 1, semester=1, topic=f'Mövzu {i + 1}',
                              assessment_type='KSQ' if i == 4 else 'formativ', exam_no=1 if i == 4 else None,
                              date=dt.date(2026, 9, 15)))
        db.commit()
        return c, ta.id, studs


def test_working_plan_pure_hold_shifts():
    slots = {0: [1], 2: [1]}
    start, end = dt.date(2026, 9, 28), dt.date(2026, 10, 9)
    plan, unfit = working_plan(slots, 3, {(dt.date(2026, 9, 30), 1)}, {}, start, end)
    assert [(s.date.day, s.index, s.held) for s in plan] == [(28, 0, False), (30, 1, True), (5, 1, False),
                                                             (7, 2, False)]
    assert unfit == []
    plan, unfit = working_plan(slots, 5, {(dt.date(2026, 9, 28), 1)}, {}, start, end)
    assert unfit == [3, 4]                                  # ilin sonuna sığmayanlar


def test_plan_view_and_hold(world):
    c, ta, _ = setup_class(world)
    week = c.get(f'/api/plan/{ta}', params={'view': 'week', 'date': '2026-09-15'}).json()
    # 15.09 Ç.a. – ilin ilk günü; həmin həftədə yalnız Ç. 16.09 (3, 4-cü saat)
    assert [(i['date'], i['period'], i['lesson']['topic']) for i in week['items']] == [
        ('2026-09-16', 3, 'Mövzu 1'), ('2026-09-16', 4, 'Mövzu 2')]
    assert c.post(f'/api/plan/{ta}/hold', json={'date': '2026-09-16', 'period': 4}).status_code == 200
    assert c.post(f'/api/plan/{ta}/hold', json={'date': '2026-09-17', 'period': 1}).status_code == 400   # dərs yoxdur
    nxt = c.get(f'/api/plan/{ta}', params={'view': 'week', 'date': '2026-09-21'}).json()['items']
    assert nxt[0]['lesson']['topic'] == 'Mövzu 2' and nxt[0]['shift'] == 1       # saxlanılan mövzu davam edir
    assert c.request('DELETE', f'/api/plan/{ta}/hold', params={'date': '2026-09-16', 'period': 4}).status_code == 200
    nxt = c.get(f'/api/plan/{ta}', params={'view': 'week', 'date': '2026-09-21'}).json()['items']
    assert nxt[0]['lesson']['topic'] == 'Mövzu 3'
    assert c.get(f'/api/plan/{ta}/official').json()[1]['topic'] == 'Mövzu 2'    # rəsmi plan dəyişmir


def test_holidays_skip_slots(world):
    as_, S = world
    c, ta, _ = setup_class(world)
    with S() as db:
        year_id = db.query(SchoolClass).first().year_id
        db.add(Holiday(year_id=year_id, date=dt.date(2026, 9, 16), name='Test bayramı'))
        db.commit()
    items = c.get(f'/api/plan/{ta}', params={'view': 'week', 'date': '2026-09-21'}).json()['items']
    assert items[0]['date'] == '2026-09-21' and items[0]['lesson']['topic'] == 'Mövzu 1'


def test_journal_entry_rules(world):
    c, ta, (a, b, d) = setup_class(world)
    day = c.get(f'/api/journal/{ta}/day', params={'date': '2026-09-16'}).json()
    assert [l['plan']['topic'] for l in day['lessons']] == ['Mövzu 1', 'Mövzu 2'] and len(day['students']) == 3
    body = {'date': '2026-09-16', 'period': 3, 'homework': 'S 1–10', 'attendance': {a: 'var', b: 'var', d: 'yox'},
            'marks': [{'student_id': a, 'kind': 'test', 'test_correct': 7, 'test_total': 10},
                      {'student_id': b, 'kind': 'şifahi', 'grade': 5}]}
    r = c.put(f'/api/journal/{ta}/entry', json=body)
    assert r.status_code == 200
    m = {x['student_id']: x['grade'] for x in r.json()['marks']}
    assert m == {a: 4, b: 5}                                         # 70% -> 4
    bad = dict(body, marks=[{'student_id': d, 'kind': 'şifahi', 'grade': 3}])
    assert c.put(f'/api/journal/{ta}/entry', json=bad).status_code == 400          # dərsdə olmayana qiymət
    assert c.put(f'/api/journal/{ta}/entry', json=dict(body, period=5)).status_code == 400   # cədvəldə yoxdur
    assert c.put(f'/api/journal/{ta}/entry', json=dict(body, attendance={999: 'var'}, marks=[])).status_code == 400
    # növbəti dərsdə ev tapşırığının yoxlanması
    nxt = c.get(f'/api/journal/{ta}/day', params={'date': '2026-09-16'}).json()['lessons'][1]
    assert nxt['homework_to_check'] == 'S 1–10'
    r = c.put(f'/api/journal/{ta}/entry', json={'date': '2026-09-16', 'period': 4,
                                                'homework_checks': {a: 'etdi', b: 'köçürüb'}})
    assert r.json()['homework_checks'] == {str(a): 'etdi', str(b): 'köçürüb'}
    summ = {s['student_id']: s for s in c.get(f'/api/journal/{ta}/summary').json()['students']}
    assert summ[a]['test_pct'] == 70.0 and summ[a]['homework_pct'] == 100.0 and summ[b]['homework_pct'] == 0.0
    assert summ[d]['attendance_pct'] == 0.0


def test_exams_items_analysis_and_semester(world):
    c, ta, (a, b, d) = setup_class(world)
    lst = c.get(f'/api/exams/{ta}').json()
    assert lst['planned'][0]['kind'] == 'KSQ' and lst['planned'][0]['created'] is False
    items = [{'n': 1, 'points': 2, 'standard': '1.1.1'}, {'n': 2, 'points': 3, 'standard': '1.1.2'},
             {'n': 3, 'points': 5, 'standard': '1.1.2'}]
    k1 = c.post(f'/api/exams/{ta}', json={'kind': 'KSQ', 'no': 1, 'semester': 1, 'date': '2026-10-05',
                                          'items': items}).json()
    assert k1['max_points'] == 10
    assert c.post(f'/api/exams/{ta}', json={'kind': 'KSQ', 'no': 1, 'semester': 1, 'date': '2026-10-05',
                                            'max_points': 10}).status_code == 409
    r = c.put(f'/api/exams/{ta}/{k1["id"]}/scores', json=[
        {'student_id': a, 'item_marks': [1, 1, 1]}, {'student_id': b, 'item_marks': [1, 0, 0]},
        {'student_id': d, 'absent': True}]).json()
    rows = {x['student_id']: x for x in r['rows']}
    assert (rows[a]['points'], rows[a]['grade']) == (10, 5) and (rows[b]['points'], rows[b]['grade']) == (2, 2)
    assert rows[d]['absent'] and r['summary']['written'] == 2
    assert [i['pct'] for i in r['items']] == [100.0, 50.0, 50.0]
    assert r['standards'] == [{'standard': '1.1.1', 'pct': 100.0}, {'standard': '1.1.2', 'pct': 50.0}]
    assert c.put(f'/api/exams/{ta}/{k1["id"]}/scores', json=[{'student_id': a, 'points': 11}]).status_code == 400
    k2 = c.post(f'/api/exams/{ta}', json={'kind': 'KSQ', 'no': 2, 'semester': 1, 'date': '2026-11-05',
                                          'max_points': 20}).json()
    c.put(f'/api/exams/{ta}/{k2["id"]}/scores', json=[{'student_id': a, 'points': 13}])       # 65% -> 4
    bsq = c.post(f'/api/exams/{ta}', json={'kind': 'BSQ', 'no': 1, 'semester': 1, 'date': '2027-01-26',
                                           'max_points': 30}).json()
    c.put(f'/api/exams/{ta}/{bsq["id"]}/scores', json=[{'student_id': a, 'points': 25}, {'student_id': b, 'points': 9}])
    sem = {s['student_id']: s for s in c.get(f'/api/exams/{ta}/semester/1').json()['students']}
    # a: KSQ (5+4)/2 = 4,5 -> 1,8 + BSQ 25/30=83% -> 5 -> 3,0 => 4,8 -> 5
    assert sem[a]['ksq_avg'] == 4.5 and sem[a]['bsq'] == 5 and sem[a]['semester_grade'] == 5
    # b: KSQ 2 -> 0,8 + BSQ 9/30=30% -> 2 -> 1,2 => 2
    assert sem[b]['semester_grade'] == 2
    assert sem[d]['semester_grade'] is None


def test_group_without_summative(world):
    c, ta, _ = setup_class(world, has_summative=False)
    assert c.post(f'/api/exams/{ta}', json={'kind': 'KSQ', 'no': 1, 'semester': 1, 'date': '2026-10-05',
                                            'max_points': 10}).status_code == 400


def test_journal_privacy(world):
    as_, _ = world
    c, ta, _ = setup_class(world)
    ilqar = as_('ilqar')
    assert ilqar.get(f'/api/journal/{ta}/day').status_code == 404
    assert ilqar.get(f'/api/plan/{ta}').status_code == 404
    assert ilqar.get(f'/api/exams/{ta}').status_code == 404


def test_timetable_grid(world):
    c, ta, _ = setup_class(world)
    g = c.get('/api/timetable', params={'date': '2026-09-17'}).json()
    wed = next(d for d in g['days'] if d['date'] == '2026-09-16')
    assert [x['topic'] for x in wed['periods']['3']] == ['Mövzu 1']
    assert g['days'][0]['periods'] == {}                     # 14.09 – il başlamayıb


def test_real_plans_on_real_dates(tmp_path):
    """Rəsmi planlar + UTİS: X e 29.09.2026 (Ç.a. 1, 5) mövzuları plandakı tarixlə üst-üstə düşür; BSQ-1 – 26.01."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.db import Base
    from app.seed import PLANS_DIR, UTIS_XLSX, seed
    from app.services import plan_ctx
    from app.domain.plan import slot_at
    if not (PLANS_DIR.exists() and UTIS_XLSX.exists()):
        pytest.skip('mənbə faylları yoxdur')
    eng = create_engine('sqlite://')
    Base.metadata.create_all(eng)
    with sessionmaker(eng)() as db:
        rep = seed(db, out_dir=tmp_path)
        assert sum('plan' in x for x in rep['created']) == 6
        for ta in db.query(TeachingAssignment):
            ctx = plan_ctx(db, ta)
            assert not ctx.unfit, ctx.cls.name
            for s in ctx.slots:                                       # hər yuvanın mövzusu plandakı tarixə düşür
                assert ctx.lesson_for(s).date == s.date, (ctx.cls.name, s)
        xe = next(ta for ta in db.query(TeachingAssignment) if db.get(SchoolClass, ta.class_id).name == 'X e')
        ctx = plan_ctx(db, xe)
        assert slot_at(ctx.slots, dt.date(2026, 9, 29), 1) and slot_at(ctx.slots, dt.date(2026, 9, 29), 5)
        day = [ctx.lesson_for(s) for s in ctx.slots if s.date == dt.date(2027, 1, 26)]
        assert [(l.assessment_type, l.exam_no) for l in day][-1] == ('BSQ', 1)     # günün son dərsi
