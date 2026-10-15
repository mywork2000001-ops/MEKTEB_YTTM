"""Əlavə KSQ/BSQ + onlayn və kağız nəticə yanaşı + jurnala gedən seçim (docs/tasks/ksq-bsq-elave-ve-iki-netice.md, mərhələ 1–2)."""
import datetime as dt

from app.api.exam_scans import apply
from app.models import ExamScan, ExamScore, ExamVariant, OnlineTask, TaskAttempt, now
from app.domain.ksq_card import key_value
from .test_ksq_scan import _graded, ksq


def _ids(S, exam_id):
    with S() as db:
        return [v.student_id for v in db.query(ExamVariant).filter_by(exam_id=exam_id).order_by(ExamVariant.student_id)]


def _extra(admin, ta, e, ids, date='2026-10-27', **kw):
    return admin.post(f'/api/exams/{ta}', json={'kind': e['kind'], 'no': e['no'], 'semester': e['semester'], 'date': date,
                                                'max_points': 20, 'extra_of': e['id'], 'extra_students': ids, **kw})


def test_extra_exam_rules_and_roster(world):
    admin, ta, e, _ = ksq(world)
    _, S = world
    ids = _ids(S, e['id'])
    assert len(ids) == 3
    # tarix əsasdan sonra olmalıdır; şagird sinifdən olmalıdır; növ/nömrə əsasla eyni
    assert _extra(admin, ta, e, ids[:2], date='2026-10-20').status_code == 400
    assert _extra(admin, ta, e, [ids[0], 999999]).status_code == 400
    assert _extra(admin, ta, e, []).status_code == 400
    r = _extra(admin, ta, e, ids[:2])
    assert r.status_code == 200, r.text
    x1 = r.json()
    assert (x1['extra_seq'], x1['extra_of'], x1['no'], x1['label']) == (1, e['id'], 1, 'KSQ-1 · əlavə 1')
    x2 = _extra(admin, ta, e, ids[2:], date='2026-10-30').json()
    assert x2['extra_seq'] == 2
    # əlavə imtahanın əsası olmayan KSQ-ya «əlavə» – 404; əlavəyə əlavə – 404
    assert _extra(admin, ta, x1, ids[:1]).status_code == 404
    # siyahı: əlavələr də göstərilir, plan sətri «created» yalnız əsasa görə
    lst = admin.get(f'/api/exams/{ta}').json()
    assert [x['label'] for x in lst['exams']] == ['KSQ-1', 'KSQ-1 · əlavə 1', 'KSQ-1 · əlavə 2']
    # variantlar yalnız seçilən 2 şagirdə
    assert admin.post(f'/api/exams/{ta}/{x1["id"]}/variants').status_code == 200
    assert sorted(_ids(S, x1['id'])) == sorted(ids[:2])
    v = admin.get(f'/api/exams/{ta}/{x1["id"]}/variants').json()
    assert len(v['variants']) == 2
    # nəticə cədvəli də yalnız onlar
    assert len(admin.get(f'/api/exams/{ta}/{x1["id"]}').json()['rows']) == 2
    # nəticəsi olan əsas silinmir (əlavələri var)
    assert admin.delete(f'/api/exams/{ta}/{e["id"]}').status_code == 409
    assert admin.delete(f'/api/exams/{ta}/{x2["id"]}').status_code == 200


def test_bsq_one_main_plus_extra(world):
    admin, ta, e, _ = ksq(world)
    body = {'kind': 'BSQ', 'no': 1, 'semester': 1, 'date': '2026-12-20', 'max_points': 40}
    b = admin.post(f'/api/exams/{ta}', json=body)
    assert b.status_code == 200
    assert admin.post(f'/api/exams/{ta}', json={**body, 'date': '2026-12-22'}).status_code == 409       # ikinci ƏSAS BSQ
    ids = [s['student_id'] for s in admin.get(f'/api/exams/{ta}/{b.json()["id"]}').json()['rows']]
    r = admin.post(f'/api/exams/{ta}', json={**body, 'date': '2026-12-25', 'extra_of': b.json()['id'], 'extra_students': ids[:1]})
    assert r.status_code == 200 and r.json()['extra_seq'] == 1


def _put(admin, ta, exam, sid, points):
    return admin.put(f'/api/exams/{ta}/{exam}/scores', json=[{'student_id': sid, 'points': points}])


def test_extra_not_counted_as_ksq_in_semester(world):
    admin, ta, e, _ = ksq(world)
    _, S = world
    ids = _ids(S, e['id'])
    x = _extra(admin, ta, e, ids[:2]).json()
    a, b = ids[0], ids[1]
    assert _put(admin, ta, e['id'], a, 8).status_code == 200            # 40 % -> 3
    assert _put(admin, ta, x['id'], a, 18).status_code == 200           # 90 % -> 5
    assert _put(admin, ta, x['id'], b, 12).status_code == 200           # buraxıb, əlavədə yazıb: 60 % -> 3
    sem = {s['student_id']: s for s in admin.get(f'/api/exams/{ta}/semester/1').json()['students']}
    assert len(sem[a]['ksq']) == 1                                      # əlavə ayrıca KSQ kimi sayılmır
    assert sem[a]['ksq'][0][1] == 5 and sem[b]['ksq'][0][1] == 3
    assert sem[ids[2]]['ksq'][0][1] is None                             # əlavəyə düşməyən şagirdin qiyməti dəyişmir


def test_two_sources_choice_and_manual(world, monkeypatch):
    admin, ta, e, pr, st, keys = _graded(world, monkeypatch)
    _, S = world
    with S() as db:
        paper = {s.student_id: s for s in db.query(ExamScan).filter_by(exam_id=e['id'], source='paper')}
    sid = next(iter(paper))
    assert paper[sid].points == 0
    # kağız 0; onlayn tam bal – hər ikisi yanaşı
    with S() as db:
        from app.models import Exam
        sc_on = ExamScan(exam_id=e['id'], student_id=sid, code=paper[sid].code, history=[], source='online', read_by='online',
                         reading=[{'slot': q['slot'], 'value': key_value(q), 'confidence': 1.0}
                                  for q in db.get(ExamVariant, (e['id'], sid)).questions])
        db.add(sc_on)
        apply(db, db.get(Exam, e['id']), sc_on)
        db.commit()
        on_pts = sc_on.points
    assert on_pts and on_pts > 0
    row = lambda: next(r for r in admin.get(f'/api/exams/{ta}/{e["id"]}').json()['rows'] if r['student_id'] == sid)
    r = row()
    assert r['online']['points'] == on_pts and r['paper']['points'] == 0 and r['differs'] is True
    assert r['points'] == on_pts and r['chosen'] == 'max'                 # ən yüksək
    # «Yazılı» seçilir -> jurnala 0
    assert admin.put(f'/api/exams/{ta}/{e["id"]}/choice/{sid}', json={'chosen': 'paper'}).status_code == 200
    assert row()['points'] == 0
    assert admin.put(f'/api/exams/{ta}/{e["id"]}/choice/{sid}', json={'chosen': 'online'}).status_code == 200
    assert row()['points'] == on_pts
    # kağızı yenidən skan etmək onlayn nəticəni silmir, onlayn təhvil kağızı silmir
    assert admin.delete(f'/api/exam-scans/{ta}/{e["id"]}').json()['deleted'] == len(paper)
    with S() as db:
        assert db.query(ExamScan).filter_by(exam_id=e['id'], source='online').count() == 1
        assert db.query(ExamScan).filter_by(exam_id=e['id'], source='paper').count() == 0
        assert db.get(ExamScore, (e['id'], sid)).points == on_pts       # bal onlayn nəticədən qaldı
    # əl ilə: üstələnmir
    assert admin.put(f'/api/exams/{ta}/{e["id"]}/choice/{sid}', json={'chosen': 'manual', 'points': 7}).status_code == 200
    assert row()['points'] == 7 and row()['chosen'] == 'manual'
    with S() as db:
        from app.models import Exam
        apply(db, db.get(Exam, e['id']), db.query(ExamScan).filter_by(exam_id=e['id'], student_id=sid, source='online').one())
        db.commit()
    assert row()['points'] == 7                                          # skan/təhvil «əl ilə» balı üstələmədi
    assert admin.put(f'/api/exams/{ta}/{e["id"]}/choice/{sid}', json={'chosen': 'online', 'points': 3}).status_code == 400
    assert admin.put(f'/api/exams/{ta}/{e["id"]}/choice/{sid}', json={'chosen': 'manual', 'points': 999}).status_code == 400
    # başqa müəllimin imtahanı
    assert world[0]('yad').put(f'/api/exams/{ta}/{e["id"]}/choice/{sid}', json={'chosen': 'max'}).status_code == 404
    # hamı üçün: «əl ilə» olan atlanır
    r = admin.put(f'/api/exams/{ta}/{e["id"]}/choice', json={'chosen': 'max'})
    assert r.status_code == 200 and r.json()['skipped_manual'] == 1
    assert row()['points'] == 7
    # audit
    from app.models import AuditLog
    with S() as db:
        assert db.query(AuditLog).filter_by(entity='exam_choice').count() >= 4


def test_online_resend_keeps_history_and_paper(world, monkeypatch):
    """Onlayn təkrar təhvil: köhnə onlayn oxunuş history-də, kağız sətrə toxunulmur."""
    from app.api.ksq_online import record
    from app.models import Exam
    admin, ta, e, pr, st, keys = _graded(world, monkeypatch)
    _, S = world
    with S() as db:
        sid = db.query(ExamScan).filter_by(exam_id=e['id'], source='paper').first().student_id
        v = db.get(ExamVariant, (e['id'], sid))
        t = OnlineTask(assignment_id=ta, title='KSQ-1', opens_at=now(), closes_at=now() + dt.timedelta(hours=1), duration_min=45,
                       questions=[{k: q[k] for k in ('slot', 'kind') if k in q} for q in sorted(v.questions, key=lambda q: q['slot'])],
                       shuffle=False, show_answers='never', student_ids=[sid], kind='ksq', exam_id=e['id'])
        db.add(t)
        db.flush()
        a = TaskAttempt(task_id=t.id, student_id=sid, deadline=now() + dt.timedelta(hours=1), order=[], answers={}, submitted_at=now())
        db.add(a)
        db.flush()
        paper_before = db.query(ExamScan).filter_by(exam_id=e['id'], student_id=sid, source='paper').one().updated_at
        record(db, t, a)
        a.answers = {'0': 1}
        record(db, t, a)                                                  # ikinci təhvil
        db.commit()
        on = db.query(ExamScan).filter_by(exam_id=e['id'], student_id=sid, source='online').one()
        assert on.read_by == 'online' and len(on.history) == 1
        pp = db.query(ExamScan).filter_by(exam_id=e['id'], student_id=sid, source='paper').one()
        assert pp.updated_at == paper_before and pp.crop_key
