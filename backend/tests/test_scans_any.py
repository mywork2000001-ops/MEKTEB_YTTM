"""Daimi «📷 Skan» (docs/yazili-sinaq-ve-skan-duymesi-promtu.md §C): POST /api/scans/any – QR → imtahan + şagird, 403, əl ilə seçim."""
import datetime as dt
import io

from PIL import Image

from app.models import ExamVariant

from .test_ksq_scan import ksq, photo


def test_any_finds_exam_by_qr_and_foreign_is_403(world):
    as_, S = world
    admin, ta, e, pr = ksq(world)
    a, b = pr['sheets'][0], pr['sheets'][1]
    r = admin.post('/api/scans/any', files=[('files', ('p.jpg', photo([a['qr'], b['qr']], 5), 'image/jpeg'))])
    assert r.status_code == 200, r.text
    d = r.json()
    assert {x['student_id'] for x in d['found']} == {a['student_id'], b['student_id']}
    assert d['found'][0]['exam_id'] == e['id'] and d['found'][0]['list'] == f'/api/exam-scans/{ta}/{e["id"]}' and d['found'][0]['full_name']
    lst = admin.get(f'/api/exam-scans/{ta}/{e["id"]}').json()
    assert lst['counts']['scanned'] == 2 and lst['counts']['pending'] == 2
    # təkrar – «artıq skan olunub»
    d2 = admin.post('/api/scans/any', files=[('files', ('p.jpg', photo([a['qr']], 2), 'image/jpeg'))]).json()
    assert d2['found'] == [] and d2['already'][0]['student_id'] == a['student_id']
    # başqa müəllim: 403
    r3 = as_('ilqar').post('/api/scans/any', files=[('files', ('p.jpg', photo([a['qr']]), 'image/jpeg'))])
    assert r3.status_code == 403
    assert admin.get(f'/api/exam-scans/{ta}/{e["id"]}').json()['counts']['scanned'] == 2


def test_any_no_qr_then_manual_pick(world):
    admin, ta, e, pr = ksq(world)
    a = pr['sheets'][0]
    r = admin.post('/api/scans/any', files=[('files', ('x.jpg', photo(['MK1|1|2|X|BAD']), 'image/jpeg'))])
    assert r.status_code == 200 and r.json()['found'] == [] and r.json()['unmatched'] == 1
    opts = admin.get('/api/scans/any/options').json()
    o = next(x for x in opts if x['exam_id'] == e['id'])
    assert o['recent'] in (True, False) and a['student_id'] in {s['id'] for s in o['students']}
    # imzasız QR-lı şəkil: əl ilə seçim (kəsik QR künclərinə görə)
    m = admin.post('/api/scans/any/manual', data={'exam_id': e['id'], 'student_id': a['student_id']},
                   files={'file': ('x.jpg', photo(['MK1|1|2|X|BAD']), 'image/jpeg')})
    assert m.status_code == 200, m.text
    assert m.json()['found'][0]['student_id'] == a['student_id']
    assert admin.get(f'/api/exam-scans/{ta}/{e["id"]}').json()['counts']['scanned'] == 1
    # QR heç yoxdur → 422
    buf = io.BytesIO()
    Image.new('L', (400, 400), 255).save(buf, 'JPEG')
    assert admin.post('/api/scans/any/manual', data={'exam_id': e['id'], 'student_id': a['student_id']},
                      files={'file': ('w.jpg', buf.getvalue(), 'image/jpeg')}).status_code == 422
    # başqa müəllim: 403
    assert world[0]('ilqar').post('/api/scans/any/manual', data={'exam_id': e['id'], 'student_id': a['student_id']},
                                  files={'file': ('x.jpg', photo(['MK1|1|2|X|BAD']), 'image/jpeg')}).status_code == 403


def test_summary_badge_counts_printed_ungraded(world):
    _, S = world
    admin, ta, e, pr = ksq(world)                       # variants/print variantları «çap olunub» edir
    s = admin.get('/api/scans/any/summary').json()
    assert s['waiting'] == 1 and s['exams'][0]['exam_id'] == e['id']
    with S() as db:                                     # çap olunmayıb → nişan yoxdur
        for v in db.query(ExamVariant).filter_by(exam_id=e['id']):
            v.printed_at = None
        db.commit()
    assert admin.get('/api/scans/any/summary').json()['waiting'] == 0
    with S() as db:
        for v in db.query(ExamVariant).filter_by(exam_id=e['id']):
            v.printed_at = dt.datetime.now(dt.timezone.utc)
        db.commit()
    # bir kart oxunub qiymətləndirilir → imtahan «nəticəsiz» deyil
    a = pr['sheets'][0]
    keys = {k['code']: k['answers'] for k in pr['key']}
    admin.post('/api/scans/any', files=[('files', ('p.jpg', photo([a['qr']]), 'image/jpeg'))])
    body = [{'scan_id': p['scan_id'], 'answers': [{'slot': x['slot'], 'value': x['value'], 'confidence': 0.97} for x in keys[p['code']]]}
            for p in admin.get('/api/exam-scans/pending').json()]
    admin.post('/api/exam-scans/import', json=body)
    assert admin.get('/api/scans/any/summary').json()['waiting'] == 0
