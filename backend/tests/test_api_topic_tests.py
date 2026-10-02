"""Mövzu testi: perspektiv plandan eyni mövzulu siniflərə onlayn test, bağlananda formativ jurnala yazılış."""
import datetime as dt

from app.domain.classes import grade_of
from app.models import Mark, PlanLesson, TeachingAssignment

from .test_api_portal import UTC, clock, setup, student_client  # noqa: F401 – clock fixture


def test_grade_of():
    assert grade_of('IX a') == 9 and grade_of('XI peşə') == 11 and grade_of('11 p') == 11
    assert grade_of('X b (riyaziyyat qrupu)') == 10 and grade_of('V-a') == 5
    assert grade_of('Olimpiada qrupu', '9 a') == 9 and grade_of('Olimpiada qrupu') is None


def _patch(monkeypatch, clock, day):
    for mod in ('app.api.topic_tests', 'app.task_journal'):
        monkeypatch.setattr(f'{mod}.now', clock)
    for mod in ('app.task_journal', 'app.api.journal'):
        monkeypatch.setattr(f'{mod}.today', lambda: day[0])


def _join(admin, S, name, slots, topics, subject='Riyaziyyat', n_students=0):
    cid = admin.post('/api/classes', json={'name': name}).json()['id']
    admin.post(f'/api/classes/{cid}/join', json={'subject': subject, 'weekly_hours': 1, 'slots': slots})
    st = [admin.post('/api/students', json={'full_name': f'{name} Şagird{i} oğlu', 'class_id': cid}).json()
          for i in range(n_students)]
    with S() as db:
        ta = db.query(TeachingAssignment).filter_by(class_id=cid, subject=subject).one()
        for i, t in enumerate(topics):
            db.add(PlanLesson(assignment_id=ta.id, seq=i + 1, semester=1, assessment_type='formativ', topic=t,
                              date=dt.date(2026, 9, 17)))
        db.commit()
        return ta.id, st, [p.id for p in db.query(PlanLesson).filter_by(assignment_id=ta.id).order_by(PlanLesson.seq)]


def test_topic_test_peers_create_and_journal(world, clock, monkeypatch):
    as_, S = world
    day = [dt.date(2026, 9, 29)]
    _patch(monkeypatch, clock, day)
    admin, ta, cid, st, ids = setup(world)                 # X e: Ç.a. 1, 5-ci saat; 29.09 1-ci saat = №5 «Kvadrat tənliklər»
    with S() as db:
        pl5 = db.query(PlanLesson).filter_by(assignment_id=ta, seq=5).one().id
    # X c – eyni mövzu №3-də (C.a. 2-ci saat: 17.09, 24.09, 01.10); IX a və X c fizika – siyahıda olmamalıdır
    ta2, xs, xids = _join(admin, S, 'X c', {'3': [2]}, ['Mövzu A', 'Mövzu B', 'KVADRAT TƏNLİKLƏR.', 'Mövzu D'], n_students=2)
    _join(admin, S, 'IX a', {'3': [3]}, ['Kvadrat tənliklər'])
    _join(admin, S, 'X d', {'3': [4]}, ['Mövzu 1'])        # eyni rəqəm, amma mövzu yoxdur – əl ilə seçim

    p = admin.get(f'/api/plan/{ta}/topics/{pl5}/peers').json()
    assert p['grade'] == 10 and [c['class_name'] for c in p['classes']] == ['X e', 'X c', 'X d']
    xe, xc, xd = p['classes']
    assert xe['current'] and xe['working_date'] == '2026-09-29' and xe['period'] == 1
    assert xe['opens_at'].startswith('2026-09-29T15:00') and xe['closes_at'].startswith('2026-09-30T22:00')
    assert xc['plan_lesson']['seq'] == 3 and xc['working_date'] == '2026-10-01'
    assert xd['plan_lesson'] is None and [l['topic'] for l in xd['lessons']] == ['Mövzu 1']
    assert as_('yad').get(f'/api/plan/{ta}/topics/{pl5}/peers').status_code == 404

    clock.t = dt.datetime(2026, 9, 29, 10, 0, tzinfo=UTC)
    base = {'title': 'Kvadrat tənliklər – mövzu testi', 'duration_min': 20, 'bank_ids': ids}
    tg = lambda c: {'ta_id': c['ta_id'], 'plan_lesson_id': c['plan_lesson']['id'],
                    'opens_at': c['opens_at'], 'closes_at': c['closes_at']}
    # biri səhvdirsə heç biri yaranmır
    bad = {**base, 'targets': [tg(xe), {**tg(xc), 'closes_at': '2026-09-28T10:00:00Z'}]}
    assert admin.post(f'/api/plan/{ta}/topics/{pl5}/test', json=bad).status_code == 400
    assert admin.get(f'/api/tasks/{ta}').json() == []
    assert admin.post(f'/api/plan/{ta}/topics/{pl5}/test', json={**base, 'targets': [tg(xe), tg(xe)]}).status_code == 422
    r = admin.post(f'/api/plan/{ta}/topics/{pl5}/test', json={**base, 'targets': [tg(xe), tg(xc)]})
    assert r.status_code == 200, r.text
    tasks = r.json()['tasks']
    assert len(tasks) == 2 and {t['kind'] for t in tasks} == {'movzu'} and tasks[0]['batch_id'] == tasks[1]['batch_id']
    t1, t2 = (next(t for t in tasks if t['ta_id'] == x) for x in (ta, ta2))
    assert admin.get(f'/api/tasks/{ta}').json()[0]['topic'] == {'seq': 5, 'topic': 'Kvadrat tənliklər'}
    assert admin.get(f'/api/plan/{ta}/topics/{pl5}/peers').json()['classes'][1]['already_has_test']

    # plan sətrində testin vəziyyəti
    lesson = lambda: next(i['lesson'] for i in admin.get(f'/api/plan/{ta}', params={'view': 'day', 'date': '2026-09-29'})
                          .json()['items'] if i['lesson']['seq'] == 5)
    assert lesson()['tests'][0]['state'] == 'gözlənilir' and lesson()['tests'][0]['questions'] == 3

    # X e: 1-ci şagird 2/3, 2-ci başlayıb cavabsız qalır (avtomatik təhvil), 3-cü yazmır
    clock.t = dt.datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
    s0 = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    q = s0.post(f'/api/portal/tasks/{t1["id"]}/start').json()
    by = {x['text']['az']: x['index'] for x in q['questions']}
    s0.post(f'/api/portal/tasks/{t1["id"]}/submit', json={'answers': {str(by['2+2=?']): 1, str(by['5·2=?']): 0}})
    student_client(st[1]['portal_code'], st[1]['initial_pin']).post(f'/api/portal/tasks/{t1["id"]}/start')

    # test bağlanandan sonra planlaşdırıcı jurnala yazır (29.09 1-ci saat – mövzunun dərsi)
    clock.t = dt.datetime(2026, 9, 30, 19, 0, tzinfo=UTC)
    day[0] = dt.date(2026, 9, 30)
    from app.task_journal import run_due
    with S() as db:
        assert run_due(db) == 1                              # X c testi hələ açılmayıb
    e = admin.get(f'/api/journal/{ta}/day', params={'date': '2026-09-29'}).json()['lessons'][0]['entry']
    assert [(m['student_id'], m['test_correct'], m['test_total'], m['grade'], m['task_id']) for m in e['marks']] == \
        [(st[0]['id'], 2, 3, 4, t1['id'])]
    lt = lesson()['tests'][0]
    assert (lt['state'], lt['submitted'], lt['total'], lt['journal']) == ('bitib', 2, 3, 'yazılıb')
    with S() as db:
        assert run_due(db) == 0                              # təkrar yazılmır

    # müəllim jurnalı yenidən saxlayır: şagird dərsdə qayıb, onlayn test qiyməti qalır və mənbəyini saxlayır
    entry = {'date': '2026-09-29', 'period': 1, 'attendance': {st[0]['id']: 'yox'},
             'marks': [{'student_id': st[0]['id'], 'kind': 'test', 'test_correct': 2, 'test_total': 3}]}
    assert admin.put(f'/api/journal/{ta}/entry', json=entry).status_code == 200
    with S() as db:
        assert db.query(Mark).filter_by(student_id=st[0]['id']).one().task_id == t1['id']
    entry['marks'][0]['test_correct'] = 3                    # dəyişdirilmiş qiymət – artıq əl ilə qiymətdir
    assert admin.put(f'/api/journal/{ta}/entry', json=entry).status_code == 400

    # X c: dərsdə əl ilə «test» qiyməti olan şagird ötürülür; «İndi yaz» test açıq ikən; cəhd sıfırlananda qiymət silinir
    day[0] = dt.date(2026, 10, 1)
    clock.t = dt.datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    admin.put(f'/api/journal/{ta2}/entry', json={'date': '2026-10-01', 'period': 2, 'marks': [
        {'student_id': xs[1]['id'], 'kind': 'test', 'test_correct': 1, 'test_total': 2}]})
    for stu in xs:
        c = student_client(stu['portal_code'], stu['initial_pin'])
        q = c.post(f'/api/portal/tasks/{t2["id"]}/start').json()
        by = {x['text']['az']: x['index'] for x in q['questions']}
        c.post(f'/api/portal/tasks/{t2["id"]}/submit', json={'answers': {str(by['2+2=?']): 1, str(by['5·2=?']): 0,
                                                                          str(by['x²=9, x>0']): '3'}})
    w = admin.post(f'/api/plan/{ta2}/tests/{t2["id"]}/journal').json()
    assert (w['date'], w['period'], w['copied']) == ('2026-10-01', 2, 1)
    assert w['skipped'] == [{'full_name': xs[1]['full_name'], 'reason': 'bu dərsdə əl ilə «test» qiyməti var'}]
    assert admin.get(f'/api/tasks/{ta2}').json()[0]['journal_done_at'] is None     # bağlananda yenidən yazılacaq
    assert admin.delete(f'/api/tasks/{ta2}/{t2["id"]}/attempts/{xs[0]["id"]}').status_code == 200
    with S() as db:
        assert db.query(Mark).filter_by(task_id=t2['id']).count() == 0
        assert db.query(Mark).filter_by(student_id=xs[1]['id']).one().task_id is None   # əl ilə qiymət toxunulmayıb


def test_topic_test_rules(world, clock, monkeypatch):
    as_, S = world
    _patch(monkeypatch, clock, [dt.date(2026, 9, 29)])
    admin, ta, cid, st, ids = setup(world)
    with S() as db:
        pl = db.query(PlanLesson).filter_by(assignment_id=ta, seq=6).one()
        pl.assessment_type, pl.exam_no = 'KSQ', 1
        db.commit()
        ksq, pl5 = pl.id, db.query(PlanLesson).filter_by(assignment_id=ta, seq=5).one().id
    clock.t = dt.datetime(2026, 9, 29, 10, 0, tzinfo=UTC)
    body = {'title': 'Test', 'duration_min': 20, 'bank_ids': ids,
            'targets': [{'ta_id': ta, 'plan_lesson_id': ksq, 'opens_at': '2026-09-29T12:00:00Z',
                         'closes_at': '2026-09-29T14:00:00Z'}]}
    assert admin.post(f'/api/plan/{ta}/topics/{ksq}/test', json=body).status_code == 400          # KSQ dərsi
    body['targets'][0]['plan_lesson_id'] = pl5
    assert admin.post(f'/api/plan/{ta}/topics/{pl5}/test', json={**body, 'duration_min': 200}).status_code == 400
    assert admin.post(f'/api/plan/{ta}/topics/{pl5}/test', json={**body, 'bank_ids': []}).status_code == 422
    assert as_('yad').post(f'/api/plan/{ta}/topics/{pl5}/test', json=body).status_code == 404
    other = {**body, 'targets': [{**body['targets'][0], 'plan_lesson_id': 999999}]}
    assert admin.post(f'/api/plan/{ta}/topics/{pl5}/test', json=other).status_code == 404       # başqa planın mövzusu
    # mövzu testi gələcək dərsə bağlıdırsa – «İndi yaz» gözləyir
    with S() as db:
        future = db.query(PlanLesson).filter_by(assignment_id=ta, seq=8).one().id            # 06.10
    body['targets'][0]['plan_lesson_id'] = future
    t = admin.post(f'/api/plan/{ta}/topics/{future}/test', json=body).json()['tasks'][0]
    r = admin.post(f'/api/plan/{ta}/tests/{t["id"]}/journal')
    assert r.status_code == 400 and 'hələ keçməyib' in r.json()['detail']
