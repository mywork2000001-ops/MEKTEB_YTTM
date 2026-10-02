"""Əlavə məşğələ: kurs (səviyyə qrupuna), məşğələ planı (tətil çıxılır), toqquşma xəbərdarlığı, mövzular, ləğv,
onlayn keçid (10 dəq əvvəl), davamiyyət, məşğələ testi, statistika, şagird portalı, icazələr."""
import datetime as dt

from app.models import AcademicYear, Holiday, OnlineTask, PlanLesson, SchoolClass, Student

from .test_api_portal import UTC, clock, setup, student_client  # noqa: F401 – clock fixture


def test_extra_course_flow(world, clock, monkeypatch):
    as_, S = world
    monkeypatch.setattr('app.api.extra.now', clock)
    admin, ta, cid, st, ids = setup(world)                      # X e: Ç.a. 1, 5-ci saat
    admin.patch(f'/api/classes/{cid}', json={'bells': {'1': '08:50–09:35'}})
    with S() as db:
        for s, sc in zip(st, (90, 30, 20)):
            db.get(Student, s['id']).score_math = sc
        y = db.query(AcademicYear).filter_by(school_id=db.get(SchoolClass, cid).school_id).one()
        db.add(Holiday(year_id=y.id, date=dt.date(2026, 10, 10), name='Bayram'))
        db.commit()
        pls = [p.id for p in db.query(PlanLesson).filter_by(assignment_id=ta).order_by(PlanLesson.seq)]
    admin.post(f'/api/levels/{ta}/apply', json={'student_ids': [s['id'] for s in st]})   # 1 güclü, 2 zəif
    clock.t = dt.datetime(2026, 10, 2, 8, 0, tzinfo=UTC)

    body = {'title': 'Zəif qrup – təkrar', 'format': 'qarışıq', 'ta_ids': [ta], 'levels': ['Zəif'],
            'schedule': [{'weekday': 5, 'start': '10:00', 'end': '11:00', 'link': 'https://meet.example/abc'},
                         {'weekday': 1, 'start': '09:00', 'end': '10:00', 'room': '12'}],
            'starts_on': '2026-10-03', 'ends_on': '2026-10-17'}
    bad = {**body, 'schedule': [{**body['schedule'][0], 'link': 'http://meet.example'}]}
    assert admin.post('/api/extra', json=bad).status_code == 422
    assert admin.post('/api/extra', json={**body, 'levels': ['Orta']}).status_code == 400        # boş qrup
    assert as_('ilqar').post('/api/extra', json=body).status_code == 404
    r = admin.post('/api/extra', json=body)
    assert r.status_code == 200, r.text
    c = r.json()
    assert c['students'] == 2 and c['sessions'] == 4                                       # 10.10 bayramdır
    assert len(c['warnings']) == 1 and 'Ç.a. 09:00–10:00' in c['warnings'][0]
    cid_ = c['id']
    full = admin.get(f'/api/extra/{cid_}').json()
    ses = full['session_list']
    assert [(s['date'], s['format']) for s in ses] == [('2026-10-03', 'onlayn'), ('2026-10-06', 'əyani'),
                                                       ('2026-10-13', 'əyani'), ('2026-10-17', 'onlayn')]
    assert {m['student_id'] for m in full['members']} == {st[1]['id'], st[2]['id']}
    assert as_('yad').get(f'/api/extra/{cid_}').status_code == 404

    # mövzular: perspektiv plandan + sərbəst mətn; başqa planın mövzusu olmaz; ləğv – səbəblə
    s1, s2, s3, s4 = (x['id'] for x in ses)
    u = admin.put(f'/api/extra/{cid_}/sessions/{s1}', json={'topics': [{'plan_lesson_id': pls[4]}, {'text': 'Kəsrlər – təkrar'}],
                                                             'homework': 'Səh. 34, №5'}).json()
    assert [t['text'] for t in u['topics']] == ['Kvadrat tənliklər', 'Kəsrlər – təkrar']
    assert admin.put(f'/api/extra/{cid_}/sessions/{s1}', json={'topics': [{'plan_lesson_id': 999999}]}).status_code == 400
    assert admin.put(f'/api/extra/{cid_}/sessions/{s3}', json={'status': 'cancelled'}).status_code == 400
    assert admin.put(f'/api/extra/{cid_}/sessions/{s3}', json={'status': 'cancelled', 'note': 'olimpiada'}).status_code == 200
    b = admin.post(f'/api/extra/{cid_}/topics/bulk', json={'plan_lesson_ids': pls[:3]}).json()
    assert b == {'sessions': 2, 'left': 1}                                                  # s2 və s4 (s3 ləğv olunub)
    sug = admin.get(f'/api/extra/{cid_}/suggest-topics').json()
    assert len(sug['plan']) == 8

    # şagird portalı: zəif qrupdakı şagird görür, güclü görmür; keçid 10 dəq əvvəl açılır
    z = student_client(st[1]['portal_code'], st[1]['initial_pin'])
    g = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    assert g.get('/api/portal/extra').json() == []
    mine = z.get('/api/portal/extra').json()
    assert len(mine) == 1 and mine[0]['next']['id'] == s1 and mine[0]['sessions'][0]['link'] is None
    clock.t = dt.datetime(2026, 10, 3, 5, 40, tzinfo=UTC)                                   # 09:40 Bakı
    assert z.post(f'/api/portal/extra/{s1}/join').status_code == 409
    clock.t = dt.datetime(2026, 10, 3, 5, 52, tzinfo=UTC)                                   # 09:52 Bakı
    assert z.get('/api/portal/extra').json()[0]['sessions'][0]['link'] == 'https://meet.example/abc'
    assert z.post(f'/api/portal/extra/{s1}/join').json()['link'] == 'https://meet.example/abc'
    assert z.post(f'/api/portal/extra/{s2}/join').status_code == 400                         # əyani
    att = admin.get(f'/api/extra/{cid_}/sessions/{s1}/attendance').json()
    assert next(a for a in att if a['student_id'] == st[1]['id'])['joined_at'] is not None

    # məşğələ testi – yalnız kursun şagirdlərinə, jurnala yazılmır
    t = admin.post(f'/api/extra/{cid_}/sessions/{s1}/test', json={'title': 'Məşğələ testi 1', 'bank_ids': ids,
                                                                   'opens_at': '2026-10-03T07:00:00Z', 'closes_at': '2026-10-03T12:00:00Z'})
    assert t.status_code == 200 and t.json()['tasks'] == 1
    with S() as db:
        task = db.query(OnlineTask).filter_by(batch_id=t.json()['batch_id']).one()
        assert sorted(task.student_ids) == sorted([st[1]['id'], st[2]['id']]) and task.kind == 'extra'
        tid = task.id
    assert admin.post(f'/api/tasks/{ta}/{tid}/to-journal', json={}).status_code == 400

    # keçirildi + davamiyyət; gələcək məşğələ «keçirildi» olmaz
    clock.t = dt.datetime(2026, 10, 3, 7, 10, tzinfo=UTC)
    assert admin.post(f'/api/extra/{cid_}/sessions/{s4}/held', json={}).status_code == 400
    h = admin.post(f'/api/extra/{cid_}/sessions/{s1}/held', json={'attendance': {st[1]['id']: 'var', st[2]['id']: 'yox'}})
    assert h.status_code == 200 and h.json()['present'] == 1
    assert admin.post(f'/api/extra/{cid_}/sessions/{s1}/held', json={'attendance': {st[0]['id']: 'var'}}).status_code == 400
    q = z.post(f'/api/portal/tasks/{tid}/start').json()
    idx = {x['text']['az']: x['index'] for x in q['questions']}
    z.post(f'/api/portal/tasks/{tid}/submit', json={'answers': {str(idx['2+2=?']): 1, str(idx['5·2=?']): 0, str(idx['x²=9, x>0']): '3'}})
    assert admin.delete(f'/api/extra/{cid_}/sessions/{s1}').status_code == 409
    clock.t = dt.datetime(2026, 10, 6, 7, 0, tzinfo=UTC)
    admin.post(f'/api/extra/{cid_}/sessions/{s2}/held', json={'attendance': {st[1]['id']: 'üzrlü', st[2]['id']: 'yox'}})

    stt = admin.get(f'/api/extra/{cid_}/stats').json()
    sm = stt['summary']
    assert (sm['held'], sm['cancelled'], sm['hours'], sm['at_risk']) == (2, 1, 2.0, 1)
    by = {s['student_id']: s for s in stt['students']}
    assert by[st[1]['id']]['attendance_pct'] == 100.0 and by[st[1]['id']]['extra_test_avg'] == 100.0   # üzrlü sayılmır
    assert by[st[2]['id']]['attendance_pct'] == 0.0 and by[st[2]['id']]['risk']
    assert stt['sessions'][0]['test_avg'] == 100.0 and stt['by_format']['onlayn']['held'] == 1
    assert stt['compare']['participants'] == 1 and stt['compare']['others'] == 2
    assert {'participants_delta', 'others_delta'} <= set(stt['compare'])          # irəliləyiş müqayisəsi
    me = z.get('/api/portal/extra').json()[0]
    assert (me['present'], me['held']) == (1, 1) and me['sessions'][0]['test']['pct'] == 100.0

    # bitmə tarixi uzadılır → yeni məşğələlər; qısaldılır → keçirilməmişlər silinir
    assert admin.patch(f'/api/extra/{cid_}', json={'ends_on': '2026-10-24'}).json()['added'] == 2
    assert admin.patch(f'/api/extra/{cid_}', json={'ends_on': '2026-10-06'}).json()['sessions'] == 2
    assert admin.post(f'/api/extra/{cid_}/archive').status_code == 200
    assert z.get('/api/portal/extra').json() == [] and admin.get('/api/extra').json() == []
