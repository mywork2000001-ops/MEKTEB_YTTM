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


def test_claude_reader_flow(world, monkeypatch):
    """Mərhələ 4: yükləmə → fonda Claude oxuyur (saxta) → şübhəli xanalar güclü modellə ikinci dəfə → bal jurnalda."""
    from app.domain import ksq_reader as R
    admin, ta, e, pr = ksq(world)
    a = pr['sheets'][0]
    key = {x['slot']: x['value'] for x in next(k for k in pr['key'] if k['code'] == a['code'])['answers']}
    calls = []

    def fake_call(api_key, model, jpeg, slots, only=None):
        calls.append((model, only))
        assert api_key == 'sk-test' and jpeg[:2] == b'\xff\xd8'               # yalnız JPEG kəsik göndərilir
        if model == R.MODEL:                                                  # birinci: 5-ci xana şübhəli, 7-ci yoxdur
            return [{'slot': s, 'value': key[s] if s != 5 else '?', 'confidence': 0.4 if s == 5 else 0.95}
                    for s in key if s != 7]
        return [{'slot': s, 'value': key[s], 'confidence': 0.93} for s in only]
    monkeypatch.setattr(R, 'call', fake_call)
    monkeypatch.setattr(R, 'api_key_for', lambda db, tid: 'sk-test')
    r = admin.post(f'/api/exam-scans/{ta}/{e["id"]}/upload', files=[('files', ('p.jpg', photo([a['qr']], 3), 'image/jpeg'))])
    assert r.status_code == 200 and len(r.json()['found']) == 1
    assert calls == [(R.MODEL, None), (R.MODEL_2, [5, 7])]
    sc = admin.get(f'/api/exam-scans/{ta}/{e["id"]}').json()
    s = sc['scans'][0]
    assert s['status'] == 'graded' and s['points'] == 100 and s['flagged'] == [] and s['read_by'] == 'claude+2' and sc['claude'] is True
    # «Yenidən oxu» – hamısı yenidən Claude-a
    calls.clear()
    assert admin.post(f'/api/exam-scans/{ta}/{e["id"]}/reread').json()['pending'] == 1
    assert calls and admin.get(f'/api/exam-scans/{ta}/{e["id"]}').json()['scans'][0]['status'] == 'graded'


def test_claude_call_parsing(monkeypatch):
    """API cavabının təhlili: alət çağırışı, yad slotlar atılır, etibar 0–1 aralığına salınır; xəta mesajı."""
    import httpx
    from app.domain import ksq_reader as R
    sent = {}

    class Resp:
        def __init__(self, code, js):
            self.status_code, self._js, self.text = code, js, str(js)

        def json(self):
            return self._js
    out = {'content': [{'type': 'text', 'text': 'x'}, {'type': 'tool_use', 'name': 'submit_card', 'input': {'answers': [
        {'slot': 1, 'value': 'B', 'confidence': 1.4}, {'slot': 99, 'value': '1', 'confidence': 0.9}, {'slot': 2, 'value': '3/7', 'confidence': 0.8}]}}]}

    def post(self, url, json=None, headers=None):
        sent.update(url=url, body=json, headers=headers)
        return Resp(200, out)
    monkeypatch.setattr(httpx.Client, 'post', post)
    got = R.call('sk-x', R.MODEL, b'\xff\xd8jpeg', [{'slot': 1, 'kind': 'mcq'}, {'slot': 2, 'kind': 'open'}])
    assert got == [{'slot': 1, 'value': 'B', 'confidence': 1.0}, {'slot': 2, 'value': '3/7', 'confidence': 0.8}]
    b = sent['body']
    assert b['model'] == 'claude-sonnet-5-5' and b['tool_choice'] == {'type': 'tool', 'name': 'submit_card'}
    assert b['messages'][0]['content'][0]['type'] == 'image' and sent['headers']['x-api-key'] == 'sk-x'
    monkeypatch.setattr(httpx.Client, 'post', lambda self, url, json=None, headers=None: Resp(429, {'error': {'message': 'rate limit'}}))
    try:
        R.call('sk-x', R.MODEL, b'\xff\xd8', [{'slot': 1, 'kind': 'mcq'}])
        raise AssertionError
    except RuntimeError as ex:
        assert '429' in str(ex) and 'rate limit' in str(ex)


def test_variant_sources_plan_and_own(world):
    """Hər perspektiv plan dərsinin öz testləri (planda seçilən fayl üstündür) və müəllimin özü seçdiyi testlər."""
    from app.models import BankFile, BankQuestion, LessonBankLink, PlanLesson
    admin, ta, e, pr = ksq(world)
    src = admin.get(f'/api/exams/{ta}/{e["id"]}/sources').json()
    faiz = next(p for p in src['plan'] if p['topic'] == 'Faiz')
    assert faiz['files'] and src['all']
    S = world[1]
    with S() as db:
        f2 = BankFile(source_key='p003', lesson='t/x.html', label='Başqa test — Xüsusi', url='http://x', kind='movzu', question_count=60)
        db.add(f2); db.flush()
        for i in range(60):
            k = 'mcq' if i < 20 else 'open'
            db.add(BankQuestion(file_id=f2.id, n=i + 1, kind=k, text={'az': f'Xüsusi {i}'}, content_hash=f'x{i}', options=[{'az': '1'}, {'az': '2'}] if k == 'mcq' else None,
                                correct=0 if k == 'mcq' else None, answer=None if k == 'mcq' else str(100 + i), diff_auto=['asan', 'orta', 'çətin'][i % 3] if k == 'open' else ['asan', 'orta'][i % 2]))
        pl = db.query(PlanLesson).filter_by(assignment_id=ta, topic='Faiz').one()
        db.add(LessonBankLink(plan_lesson_id=pl.id, file_id=f2.id)); db.commit()
        fid = f2.id
    src = admin.get(f'/api/exams/{ta}/{e["id"]}/sources').json()
    assert [f['file_id'] for f in next(p for p in src['plan'] if p['topic'] == 'Faiz')['files']] == [fid]   # planda seçilən fayl
    v = admin.post(f'/api/exams/{ta}/{e["id"]}/variants', json={'n': 10, 'file_ids': [fid]}).json()
    bank = [q for x in v['variants'] for q in x['questions'] if q.get('bank_id')]
    assert bank and all(q['lesson'] == 'Başqa test — Xüsusi' for q in bank) and len(v['variants'][0]['questions']) == 10


def test_readiness_and_share(world):
    """Hazırlıq: mövzular üzrə hovuz, kiçik hovuzda ok=false və maksimal n; «2 şagirdə» rejimi çatışmazlığı aradan qaldırır."""
    admin, ta, e, pr = ksq(world)
    r = admin.post(f'/api/exams/{ta}/{e["id"]}/readiness', json={'n': 30}).json()
    faiz = next(t for t in r['topics'] if t['topic'] == 'Faiz')
    assert r['students'] == 3 and r['need'] == 90 and faiz['mcq'] == 40 and faiz['open'] > 0 and faiz['templates'] >= 1
    assert r['ok'] is True and r['max_n'] == 30
    # yalnız bir kiçik test seçilsə (plan nəzərə alınmır) – hovuz çatmır, maksimal n azalır və ya yoxdur
    from app.models import BankFile, BankQuestion
    with world[1]() as db:
        f = BankFile(source_key='p003', lesson='t/kicik.html', label='Kiçik test', url='http://x', kind='movzu', question_count=3)
        db.add(f); db.flush()
        for i in range(3):
            db.add(BankQuestion(file_id=f.id, n=i + 1, kind='mcq', text={'az': f'K{i}'}, content_hash=f'k{i}', options=[{'az': '1'}, {'az': '2'}], correct=0, diff_auto='asan'))
        db.commit()
        fid = f.id
    r2 = admin.post(f'/api/exams/{ta}/{e["id"]}/readiness', json={'n': 30, 'file_ids': [fid], 'only_mine': True}).json()
    assert r2['selected']['mcq'] == 3 and (r2['ok'] is False or r2['max_n'] == 30)
    v = admin.post(f'/api/exams/{ta}/{e["id"]}/variants', json={'n': 10, 'share': 2}).json()
    keys = [q['key'] for x in v['variants'] for q in x['questions']]
    from collections import Counter
    assert max(Counter(keys).values()) <= 2 and all(len({q['key'] for q in x['questions']}) == 10 for x in v['variants'])
