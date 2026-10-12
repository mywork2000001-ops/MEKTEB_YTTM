"""KSQ/BSQ mərhələ 3: kart şəkli → QR → cavab zonası → oxunuş idxalı → qiymətləndirmə → jurnal; təkrar yükləmə, düzəliş, «Yenilə»."""
import datetime as dt
import io

import zxingcpp
from PIL import Image

from app.domain.ksq_scan import PX_MM, ZONE, correct, grade
from app.models import BankFile, BankQuestion, BankSource, PlanLesson


def test_correct_normalization():
    q = {'kind': 'open', 'answer': '3/4|0,75'}
    assert all(correct(q, v) for v in ('3/4', '6/8', '0,75', '0.75', ' 3 / 4 '))
    assert not correct(q, '4/3') and not correct(q, '') and not correct(q, None)
    assert correct({'kind': 'open', 'answer': '-4'}, '−4') and correct({'kind': 'open', 'answer': '2;5'}, '5;2')
    assert correct({'kind': 'mcq', 'correct': 2}, 'c') and not correct({'kind': 'mcq', 'correct': 2}, 'D')
    g = grade([{'slot': 1, 'kind': 'mcq', 'correct': 0, 'points': 1.5}, {'slot': 2, 'kind': 'open', 'answer': '5', 'points': 4}],
              [{'slot': 1, 'value': 'A', 'confidence': 0.99}, {'slot': 2, 'value': '5', 'confidence': 0.5}])
    assert g == {'marks': [1, 1], 'points': 5.5, 'flagged': [2]}


def ksq(world):
    from .test_api_portal import setup
    _, S = world
    admin, ta, cid, st, _ = setup(world)
    with S() as db:
        db.add(BankSource(key='p003', label='P0010'))
        db.flush()
        f = BankFile(source_key='p003', lesson='t/faiz.html', label='Nisbət. Tənasüb. Faiz — Faiz', url='http://x', kind='movzu', question_count=80)
        db.add(f)
        db.flush()
        for i in range(80):
            kind = 'mcq' if i < 40 else 'open'
            db.add(BankQuestion(file_id=f.id, n=i + 1, kind=kind, text={'az': f'Faiz sualı {i}'}, content_hash=f'h{i}',
                                options=[{'az': '1'}, {'az': '2'}] if kind == 'mcq' else None, correct=0 if kind == 'mcq' else None,
                                answer=None if kind == 'mcq' else str(i), diff_auto=['asan', 'orta', 'çətin'][i % 3] if kind == 'open' else ['asan', 'orta'][i % 2]))
        db.query(PlanLesson).filter_by(assignment_id=ta, seq=3).one().topic = 'Faiz'
        db.add(PlanLesson(assignment_id=ta, seq=9, semester=1, assessment_type='KSQ', exam_no=1, topic='KSQ-1', date=dt.date(2026, 10, 20)))
        db.commit()
    e = admin.post(f'/api/exams/{ta}', json={'kind': 'KSQ', 'no': 1, 'semester': 1, 'date': '2026-10-20', 'max_points': 20}).json()
    assert admin.post(f'/api/exams/{ta}/{e["id"]}/variants').status_code == 200
    return admin, ta, e, admin.get(f'/api/exams/{ta}/{e["id"]}/variants/print').json()


def qr_img(text: str, px: int) -> Image.Image:
    z = zxingcpp.write_barcode_to_image(zxingcpp.create_barcode(text, zxingcpp.BarcodeFormat.QRCode), with_quiet_zones=False)
    h, w = z.shape[:2]                                                         # haşiyəsiz (QR kartda margin 0)
    q = Image.frombytes('L', (w, h), memoryview(z).tobytes())
    return q.resize((px, px), Image.NEAREST)


def photo(qrs: list[str], angle: float = 0) -> bytes:
    """«Telefon şəkli»: ağ vərəqdə kartlar (QR 22 mm = 132 px, 6 px/mm), cavab zonasında qara kvadrat, bir az fırladılmış."""
    img = Image.new('L', (1300, 900 * len(qrs)), 255)
    for k, text in enumerate(qrs):
        x0, y0 = 120, 120 + k * 900
        img.paste(qr_img(text, 132), (x0, y0))
        img.paste(0, (x0 + 60 * 6, y0 + 60 * 6, x0 + 70 * 6, y0 + 70 * 6))      # QR-ın sol üst küncünə görə (60..70, 60..70) mm
    img = img.rotate(angle, expand=True, fillcolor=255)
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=92)
    return buf.getvalue()


def test_scan_flow(world):
    admin, ta, e, pr = ksq(world)
    keys = {k['code']: k['answers'] for k in pr['key']}
    a, b = pr['sheets'][0], pr['sheets'][1]
    # bir şəkildə iki kart tapılır; imzasız QR rədd edilir
    r = admin.post(f'/api/exam-scans/{ta}/{e["id"]}/upload', files=[('files', ('p.jpg', photo([a['qr'], b['qr']], 7), 'image/jpeg')),
                                                                      ('files', ('x.jpg', photo(['MK1|1|2|X|BAD']), 'image/jpeg'))])
    assert r.status_code == 200, r.text
    d = r.json()
    assert {x['student_id'] for x in d['found']} == {a['student_id'], b['student_id']} and len(d['problems']) == 1
    lst = admin.get(f'/api/exam-scans/{ta}/{e["id"]}').json()
    assert lst['counts'] == {'variants': 3, 'scanned': 2, 'graded': 0, 'pending': 2, 'flagged': 0} and len(lst['missing']) == 1
    # kəsik: düzgün ölçü, qara kvadrat düzəldilmiş yerdə (fırlanma düzəlib)
    im = Image.open(io.BytesIO(admin.get(f'/api/exam-scans/image/{lst["scans"][0]["id"]}').content))
    assert im.size == (int((ZONE[2] - ZONE[0]) * PX_MM), int((ZONE[3] - ZONE[1]) * PX_MM))
    cx, cy = int((65 - ZONE[0]) * PX_MM), int((65 - ZONE[1]) * PX_MM)
    assert im.getpixel((cx, cy)) < 80 and im.getpixel((cx + 20 * PX_MM, cy)) > 200
    # ehtiyat yol: oxunmamışlar → idxal (hamısı düz) → 100 bal, qiymət 5 jurnalda
    pend = admin.get('/api/exam-scans/pending', params={'images': True}).json()
    assert len(pend) == 2 and len(pend[0]['slots']) == 30 and pend[0]['image_jpeg_b64']
    body = [{'scan_id': p['scan_id'], 'answers': [{'slot': x['slot'], 'value': x['value'], 'confidence': 0.97} for x in keys[p['code']]]}
            for p in pend]
    assert admin.post('/api/exam-scans/import', json=body).json()['graded'] == 2
    sc = admin.get(f'/api/exams/{ta}/{e["id"]}').json()
    row = next(x for x in sc['rows'] if x['student_id'] == a['student_id'])
    assert row['points'] == 100 and row['grade'] == 5
    # müəllim düzəlişi: 1-ci sual səhv → 98,5 bal; «Yenilə»
    mine = next(x for x in admin.get(f'/api/exam-scans/{ta}/{e["id"]}').json()['scans'] if x['student_id'] == a['student_id'])
    wrong = 'B' if keys[a['code']][0]['value'] != 'B' else 'C'
    assert admin.put(f'/api/exam-scans/{mine["id"]}/slot', json={'slot': 1, 'value': wrong}).json()['points'] == 98.5
    assert admin.post(f'/api/exam-scans/{ta}/{e["id"]}/regrade').json()['graded'] == 2
    # təkrar yükləmə: köhnə oxunuş arxivə, yenidən gözləyir
    admin.post(f'/api/exam-scans/{ta}/{e["id"]}/upload', files=[('files', ('p2.jpg', photo([a['qr']], -4), 'image/jpeg'))])
    again = next(x for x in admin.get(f'/api/exam-scans/{ta}/{e["id"]}').json()['scans'] if x['student_id'] == a['student_id'])
    assert again['status'] == 'pending' and again['rescans'] == 1
