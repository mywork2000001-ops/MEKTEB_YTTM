"""Jurnal auditi (19.10.2026): şərti yarımil qiyməti (J1), çıxmış şagirdlər (J2), diaqnostik gün (J3), illik qiymət (J4),
plan testləri və standartlar (J5/J7), yarımil bağlanması + admin açması + audit fərqi (J6), davamiyyət xəbərdarlığı (J9),
14 gün qiymətsizlər (J10)."""
import datetime as dt
from types import SimpleNamespace

from app.api.journal import is_closed
from app.domain.rules import year_grade
from app.models import AuditLog, Mark, PlanLesson

from .test_api_portal import as_topic, mk_task, setup, student_client

D = dt.date(2026, 9, 29)


def _now(monkeypatch, d=D):
    monkeypatch.setattr('app.services.today', lambda: d)
    monkeypatch.setattr('app.api.journal.today', lambda: d)
    monkeypatch.setattr('app.api.exams.today', lambda: d)


def _put(c, ta, body):
    return c.put(f'/api/journal/{ta}/entry', json=body)


def test_year_grade_rounding():
    """J4: iki yarımilin ortası, 2,5 → 3; biri yoxdursa – yoxdur."""
    assert year_grade(2, 3) == 3 and year_grade(4, 5) == 5 and year_grade(3, 3) == 3 and year_grade(2, 2) == 2
    assert year_grade(5, None) is None and year_grade(None, None) is None


def test_semester_conditional_and_year(world, monkeypatch):
    """J1: buraxılmış KSQ qiyməti yox etmir, «şərti» edir; J4: illik qiymət hər iki yarımil olanda."""
    _now(monkeypatch, dt.date(2026, 10, 20))
    c, ta, cid, st, ids = setup(world)
    mk = lambda kind, no, sem, date: c.post(f'/api/exams/{ta}', json={'kind': kind, 'no': no, 'semester': sem, 'date': date, 'max_points': 10}).json()
    k1, k2, b1 = mk('KSQ', 1, 1, '2026-09-25'), mk('KSQ', 2, 1, '2026-10-05'), mk('BSQ', 1, 1, '2026-10-10')
    fut = mk('KSQ', 3, 1, '2026-12-20')                         # hələ keçirilməyib – buraxılış sayılmır
    score = lambda e, rows: c.put(f'/api/exams/{ta}/{e["id"]}/scores', json=rows)
    a, b, d = st[0]['id'], st[1]['id'], st[2]['id']
    assert score(k1, [{'student_id': a, 'points': 9}, {'student_id': b, 'points': 9}, {'student_id': d, 'points': 9}]).status_code == 200
    assert score(k2, [{'student_id': a, 'points': 9}, {'student_id': b, 'absent': True}, {'student_id': d, 'points': 9}]).status_code == 200
    assert score(b1, [{'student_id': a, 'points': 9}, {'student_id': b, 'points': 8}, {'student_id': d, 'points': 9}]).status_code == 200
    rows = {r['student_id']: r for r in c.get(f'/api/exams/{ta}/semester/1').json()['students']}
    assert rows[a]['conditional'] is False and rows[a]['missed_ksq'] == []
    assert rows[b]['conditional'] is True and rows[b]['missed_ksq'] == [2]
    assert rows[b]['semester_grade'] == 4 and rows[b]['year_grade'] is None      # KSQ-1=5 (KSQ-2 yoxdur), BSQ=4 → 4,4 → 4
    assert fut['no'] == 3 and 3 not in rows[a]['missed_ksq']
    # 2-ci yarımil: illik qiymət yalnız hər iki yarımil qiyməti olanda çıxır
    k21, b2 = mk('KSQ', 1, 2, '2027-03-01'), mk('BSQ', 2, 2, '2027-05-20')
    _now(monkeypatch, dt.date(2027, 6, 1))
    score(k21, [{'student_id': a, 'points': 5}])
    score(b2, [{'student_id': a, 'points': 5}])
    r1 = {r['student_id']: r for r in c.get(f'/api/exams/{ta}/semester/1').json()['students']}
    r2 = {r['student_id']: r for r in c.get(f'/api/exams/{ta}/semester/2').json()['students']}
    assert r1[a]['semester_grade'] == 5 and r2[a]['semester_grade'] == 3        # KSQ 50%, BSQ 50% → 3
    assert r1[a]['year_grade'] == r2[a]['year_grade'] == 4                       # (5+3)/2
    assert r2[b]['year_grade'] is None


def test_portal_missed_ksq_flag(world, monkeypatch):
    """J1: şagirdin portalında da şərti qiymət işarəsi (buraxılmış KSQ nömrəsi) və illik qiymət sahəsi."""
    c, ta, cid, st, ids = setup(world)
    k = c.post(f'/api/exams/{ta}', json={'kind': 'KSQ', 'no': 1, 'semester': 1, 'date': '2026-09-25', 'max_points': 10}).json()
    c.put(f'/api/exams/{ta}/{k["id"]}/scores', json=[{'student_id': st[0]['id'], 'points': 9}, {'student_id': st[1]['id'], 'absent': True}])
    r = student_client(st[1]['portal_code'], st[1]['initial_pin']).get('/api/portal/results').json()
    sub = r['subjects'][0]
    assert sub['semester_missed_ksq'] == {'1': [1], '2': []} and 'year_grade' in sub and sub['year_grade'] is None
    ok = student_client(st[0]['portal_code'], st[0]['initial_pin']).get('/api/portal/results').json()['subjects'][0]
    assert ok['semester_missed_ksq'] == {'1': [], '2': []}


def test_left_students_in_period(world, monkeypatch):
    """J2: çıxmış şagird öz dövrünün jurnalında qalır (left_on ilə); ona yeni məlumat yazılmır, köhnə yazı qorunur;
    birləşdirilmiş dublikat heç vaxt göstərilmir."""
    _now(monkeypatch)
    c, ta, cid, st, ids = setup(world)
    a, b, d = (x['id'] for x in st)
    allv = {a: 'var', b: 'var', d: 'yox'}
    assert _put(c, ta, {'date': '2026-09-22', 'period': 1, 'attendance': allv}).status_code == 200
    assert c.post(f'/api/students/{d}/archive', json={'confirm': st[2]['full_name'], 'reason': 'köçdü', 'left_on': '2026-09-25'}).status_code == 200
    g = c.get(f'/api/journal/{ta}/grid', params={'month': '2026-09'}).json()
    row = next(r for r in g['rows'] if r['student_id'] == d)
    assert row['left_on'] == '2026-09-25' and any(x['att'] == 'q' for x in row['cells'])
    assert d not in [r['student_id'] for r in c.get(f'/api/journal/{ta}/grid', params={'month': '2026-10'}).json()['rows']]
    day = c.get(f'/api/journal/{ta}/day', params={'date': '2026-09-22'}).json()
    assert {s['id']: s['left_on'] for s in day['students']} == {a: None, b: None, d: '2026-09-25'}
    assert d not in [s['id'] for s in c.get(f'/api/journal/{ta}/day', params={'date': '2026-09-29'}).json()['students']]
    assert d in [s['student_id'] for s in c.get(f'/api/journal/{ta}/summary', params={'semester': 1}).json()['students']]
    # çıxmışa yazmaq olmaz; digərlərini yenidən saxlayanda onun köhnə davamiyyəti silinmir
    assert _put(c, ta, {'date': '2026-09-22', 'period': 1, 'attendance': allv}).status_code == 400
    assert _put(c, ta, {'date': '2026-09-22', 'period': 1, 'attendance': {a: 'gecikdi', b: 'var'}}).status_code == 200
    got = c.get(f'/api/journal/{ta}/day', params={'date': '2026-09-22'}).json()['lessons'][0]['entry']['attendance']
    assert got[str(d)] == 'yox' and got[str(a)] == 'gecikdi'
    # birləşdirilmiş dublikat görünmür
    with world[1]() as db:
        from app.models import Student
        db.get(Student, d).left_reason = 'Birləşdirildi → XE-001 (Ad)'
        db.commit()
    g = c.get(f'/api/journal/{ta}/grid', params={'month': '2026-09'}).json()
    assert d not in [r['student_id'] for r in g['rows']]
    assert d not in [s['id'] for s in c.get(f'/api/journal/{ta}/day', params={'date': '2026-09-22'}).json()['students']]


def test_diagnostic_day_no_grades(world, monkeypatch):
    """J3: diaqnostik gündə bal yazılmır (400), davamiyyət və qeyd yazılır."""
    _now(monkeypatch)
    c, ta, cid, st, ids = setup(world)
    with world[1]() as db:
        db.query(PlanLesson).filter_by(assignment_id=ta, seq=6).one().assessment_type = 'diaqnostik'
        db.commit()
    body = {'date': '2026-09-29', 'period': 5, 'attendance': {st[0]['id']: 'var'}, 'note': 'ilkin yoxlama'}
    r = _put(c, ta, {**body, 'marks': [{'student_id': st[0]['id'], 'kind': 'şifahi', 'grade': 5}]})
    assert r.status_code == 400 and 'Diaqnostik' in r.json()['detail']
    assert _put(c, ta, body).status_code == 200


def test_plan_tests_split_and_standards(world, monkeypatch):
    """J5/J7: plan testləri (task_id) sinifdə yazılan qiymətlərdən ayrı sayılır; standart/mövzu üzrə mənimsəmə;
    sinif ortası 5-dən az şagirddə gizlənir."""
    _now(monkeypatch)
    c, ta, cid, st, ids = setup(world)
    a, b = st[0]['id'], st[1]['id']
    with world[1]() as db:
        db.query(PlanLesson).filter_by(assignment_id=ta, seq=5).one().standards = ['2.1.1', '2.1.2']
        db.commit()
    t = mk_task(c, ta, ids, opens_at='2026-09-29T05:00:00Z', closes_at='2026-09-29T06:00:00Z').json()
    as_topic(world[1], t['id'])
    assert _put(c, ta, {'date': '2026-09-29', 'period': 1, 'attendance': {st[0]['id']: 'var', st[1]['id']: 'var', st[2]['id']: 'var'},
                        'marks': [{'student_id': a, 'kind': 'test', 'test_correct': 8, 'test_total': 10},
                                  {'student_id': b, 'kind': 'test', 'test_correct': 4, 'test_total': 10},
                                  {'student_id': a, 'kind': 'şifahi', 'grade': 5}]}).status_code == 200
    with world[1]() as db:                              # bu testlər onlayn plan testidir
        for m in db.query(Mark).filter_by(kind='test'):
            m.task_id = t['id']
        db.commit()
    rows = {r['student_id']: r for r in c.get(f'/api/journal/{ta}/summary', params={'semester': 1}).json()['students']}
    assert rows[a]['avg_plan_tests'] == 4 and rows[a]['plan_tests'] == 1 and rows[a]['avg_class'] == 5 and rows[a]['class_marks'] == 1
    assert rows[a]['avg_grade'] == 4.5 and rows[b]['avg_class'] is None and rows[b]['avg_plan_tests'] == 3
    s = c.get(f'/api/journal/{ta}/standards', params={'semester': 1}).json()
    std = {x['standard']: x for x in s['standards']}
    assert set(std) == {'2.1.1', '2.1.2'} and std['2.1.1']['tests'] == 1 and std['2.1.1']['results'] == 2
    assert s['class_avg_hidden'] is True and std['2.1.1']['class_pct'] is None
    assert [x['pct'] for x in std['2.1.1']['students']] == [40.0, 80.0]
    assert s['topics'][0]['topic'] == 'Kvadrat tənliklər'
    for i in range(2):                                  # 5 şagird – sinif ortası görünür
        c.post('/api/students', json={'full_name': f'Əlavə Şagird{i} oğlu', 'class_id': cid, 'force': True})
    s = c.get(f'/api/journal/{ta}/standards', params={'semester': 1}).json()
    assert s['class_avg_hidden'] is False and next(x for x in s['standards'] if x['standard'] == '2.1.1')['class_pct'] == 60.0


def test_closed_semester_lock_and_admin_unlock(world, monkeypatch):
    """J6: yarımil bitəndən sonra ləğv/dəyişiklik 409; yalnız admin səbəblə (≥5 simvol) və audit-də «köhnə → yeni» fərqi."""
    _now(monkeypatch)
    c, ta, cid, st, ids = setup(world)
    a = st[0]['id']
    base = {'date': '2026-09-29', 'period': 1, 'attendance': {a: 'var'}, 'marks': [{'student_id': a, 'kind': 'şifahi', 'grade': 3}]}
    assert _put(c, ta, base).status_code == 200                    # yarımil açıqdır
    monkeypatch.setattr('app.api.journal.lock_today', lambda: dt.date(2027, 2, 10))
    new = {**base, 'marks': [{'student_id': a, 'kind': 'şifahi', 'grade': 5}], 'attendance': {a: 'gecikdi'}}
    r = _put(c, ta, new)
    assert r.status_code == 409 and 'Yarımil bağlanıb' in r.json()['detail']
    assert _put(c, ta, {**new, 'unlock_reason': 'yox'}).status_code == 409                 # səbəb qısadır
    assert _put(c, ta, {**new, 'unlock_reason': 'Qiymət səhvən yazılmışdı'}).status_code == 200
    with world[1]() as db:
        log = [x for x in db.query(AuditLog).filter_by(entity='journal', action='update').order_by(AuditLog.id)][-1]
        assert log.details['unlock_reason'] == 'Qiymət səhvən yazılmışdı' and log.details['attendance_changed'] == 1
        assert log.details['marks_diff'] == [{'student_id': a, 'kind': 'şifahi', 'old': 3, 'new': 5}]
    # sistem/avto yol: onlayn testin jurnala köçürülməsi (əl ilə tarix) da bloklanır, admin səbəbsiz keçə bilmir
    t = mk_task(c, ta, ids, opens_at='2026-09-29T05:00:00Z', closes_at='2026-09-29T06:00:00Z').json()
    as_topic(world[1], t['id'])
    r = c.post(f'/api/tasks/{ta}/{t["id"]}/to-journal', json={'date': '2026-09-29', 'period': 1})
    assert r.status_code == 409


def test_closed_semester_teacher_blocked(world, monkeypatch):
    """J6: adi müəllim bağlanmış yarımildə heç vaxt dəyişə bilməz (səbəb göndərsə də)."""
    _now(monkeypatch)
    t = world[0]('ilqar')
    cid = t.post('/api/classes', json={'name': 'X l'}).json()['id']
    t.post(f'/api/classes/{cid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 2, 'slots': {'1': [1, 5]}})
    sid = t.post('/api/students', json={'full_name': 'Test Şagird oğlu', 'class_id': cid, 'force': True}).json()['id']
    from app.models import TeachingAssignment
    with world[1]() as db:
        ta = db.query(TeachingAssignment).filter_by(class_id=cid).one().id
        for i in range(6):
            db.add(PlanLesson(assignment_id=ta, seq=i + 1, semester=1, topic=f'M{i}', assessment_type='formativ', date=dt.date(2026, 9, 15)))
        db.commit()
    body = {'date': '2026-09-22', 'period': 1, 'attendance': {sid: 'var'}}
    assert _put(t, ta, body).status_code == 200
    monkeypatch.setattr('app.api.journal.lock_today', lambda: dt.date(2027, 2, 10))
    r = _put(t, ta, {**body, 'unlock_reason': 'Çox vacib səbəb'})
    assert r.status_code == 409 and t.get(f'/api/journal/{ta}/day', params={'date': '2026-09-22'}).json()['locked'] is True


def test_is_closed_boundaries():
    y = SimpleNamespace(sem1_end=dt.date(2027, 1, 26), sem2_start=dt.date(2027, 2, 1), end=dt.date(2027, 6, 14))
    assert not is_closed(y, dt.date(2026, 10, 1), dt.date(2027, 1, 26))          # yarımil son günü hələ açıq
    assert is_closed(y, dt.date(2026, 10, 1), dt.date(2027, 1, 27))
    assert not is_closed(y, dt.date(2027, 3, 1), dt.date(2027, 6, 14)) and is_closed(y, dt.date(2027, 3, 1), dt.date(2027, 6, 15))
    assert not is_closed(y, dt.date(2027, 3, 1), dt.date(2027, 2, 10))           # 2-ci yarımil gedir


def test_attendance_warning(world, monkeypatch):
    """J9: davamiyyət yazılmayan şagird sayı xəbərdarlıq kimi qayıdır (bloklanmır)."""
    _now(monkeypatch)
    c, ta, cid, st, ids = setup(world)
    r = _put(c, ta, {'date': '2026-09-22', 'period': 1, 'attendance': {st[0]['id']: 'var', st[1]['id']: 'yox'}})
    w = r.json()['warnings']
    assert r.status_code == 200 and w[0]['params'] == {'n': 1} and w[0]['key'] == '{n} şagirdin davamiyyəti yazılmayıb'
    assert _put(c, ta, {'date': '2026-09-22', 'period': 1, 'attendance': {x['id']: 'var' for x in st}}).json()['warnings'] == []
    assert _put(c, ta, {'date': '2026-09-22', 'period': 5, 'homework': 'S 1'}).json()['warnings'] == []     # davamiyyət göndərilməyib


def test_no_marks_14_days(world, monkeypatch):
    """J10: son 14 gündə qiyməti olmayan aktiv şagirdlər (dövrdə ≥ 3 yazılmış dərs); əvvəl – boş."""
    _now(monkeypatch)
    c, ta, cid, st, ids = setup(world)
    a = st[0]['id']
    full = {x['id']: 'var' for x in st}
    _put(c, ta, {'date': '2026-09-22', 'period': 1, 'attendance': full, 'marks': [{'student_id': a, 'kind': 'şifahi', 'grade': 4}]})
    _put(c, ta, {'date': '2026-09-22', 'period': 5, 'attendance': full})
    assert c.get(f'/api/journal/{ta}/day', params={'date': '2026-09-29'}).json()['no_marks_14d'] == []     # cəmi 2 dərs
    _put(c, ta, {'date': '2026-09-29', 'period': 1, 'attendance': full})
    day = c.get(f'/api/journal/{ta}/day', params={'date': '2026-09-29'}).json()
    assert sorted(day['no_marks_14d']) == sorted(x['id'] for x in st[1:])
    assert sorted(c.get(f'/api/journal/{ta}/grid', params={'month': '2026-09'}).json()['no_marks_14d']) == sorted(x['id'] for x in st[1:])
    wk = c.get('/api/my/weekly').json()['items']
    assert wk and sorted(wk[0]['no_marks']) == sorted(x['full_name'] for x in st[1:])
