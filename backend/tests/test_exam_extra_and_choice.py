"""Əlavə KSQ/BSQ (docs/tasks/ksq-bsq-elave-ve-iki-netice.md, mərhələ 1)."""
from app.models import ExamVariant
from .test_ksq_scan import ksq


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
