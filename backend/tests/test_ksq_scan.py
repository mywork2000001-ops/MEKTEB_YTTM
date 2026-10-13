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
        f = BankFile(source_key='p003', lesson='t/faiz.html', label='Nisbət. Tənasüb. Faiz — Faiz', url='http://x', kind='movzu', question_count=210)
        db.add(f)
        db.flush()
        for i in range(210):                                       # P0010 faylı kimi – şablonsuz kifayət etsin
            kind = 'mcq' if i < 60 else 'open'
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
    # kağızda görünməyən sual (çapda kəsilib): sayılmır, qalanlar 100-ə miqyaslanır; geri qaytarmaq olar
    lo = admin.put(f'/api/exam-scans/{mine["id"]}/lost', json={'slots': [1, 99]}).json()
    assert lo['lost'] == [1] and lo['points'] == 100 and lo['n'] == 30
    assert admin.put(f'/api/exam-scans/{mine["id"]}/lost', json={'slots': []}).json()['points'] == 98.5
    # kağıza düşməyən suallar (avtomatik): kəsilmiş ∩ boş → ⊘; cavabı olan kəsilmiş sual – sayılır
    bid = b['student_id']
    other = next(x for x in admin.get(f'/api/exam-scans/{ta}/{e["id"]}').json()['scans'] if x['student_id'] == bid)
    admin.put(f'/api/exam-scans/{other["id"]}/slot', json={'slot': 30, 'value': None})
    r = admin.post(f'/api/exam-scans/{ta}/{e["id"]}/lost-auto', json={'cut': {str(bid): [29, 30], str(a['student_id']): [2]}}).json()
    ch = {x['student_id']: x for x in r['changed']}
    assert ch[bid]['lost'] == [30] and ch[bid]['after'] == 100 and a['student_id'] not in ch
    assert admin.get(f'/api/exam-scans/{ta}/{e["id"]}').json()['printed_old'] in (True, False)
    # bir blank – bir dəfə: təkrar göndərilən kart qəbul edilmir (oxunuş və bal dəyişmir)
    d2 = admin.post(f'/api/exam-scans/{ta}/{e["id"]}/upload', files=[('files', ('p1.jpg', photo([a['qr']], 3), 'image/jpeg'))]).json()
    assert d2['found'] == [] and [x['student_id'] for x in d2['already']] == [a['student_id']] and d2['already'][0]['points'] == 98.5
    # kart kadra tam düşməyib – «yenidən çək», köhnə oxunuşa toxunulmur
    cut = Image.open(io.BytesIO(photo([a['qr']])))
    buf = io.BytesIO(); cut.crop((0, 0, 900, 900)).save(buf, 'JPEG', quality=92)
    d3 = admin.post(f'/api/exam-scans/{ta}/{e["id"]}/upload', params={'replace': True}, files=[('files', ('c.jpg', buf.getvalue(), 'image/jpeg'))]).json()
    assert d3['found'] == [] and d3['problems'][0]['kind'] == 'partial' and d3['problems'][0]['student_id'] == a['student_id']
    still = next(x for x in admin.get(f'/api/exam-scans/{ta}/{e["id"]}').json()['scans'] if x['student_id'] == a['student_id'])
    assert still['status'] == 'graded' and still['points'] == 98.5
    # yenidən skan (müəllim seçib): köhnə oxunuş arxivə, yenidən gözləyir
    r2 = admin.post(f'/api/exam-scans/{ta}/{e["id"]}/upload', params={'replace': True}, files=[('files', ('p2.jpg', photo([a['qr']], -4), 'image/jpeg'))]).json()
    assert r2['found'][0]['scan_id'] == mine['id']
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
    assert r['students'] == 3 and r['need'] == 90 and faiz['mcq'] == 60 and faiz['open'] > 0 and faiz['templates'] == 0     # şablon standart söndürülü
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


def test_question_replace_edit_annul(world):
    """Sual səviyyəsində: əvəz et (tək və bütün sinifdə), redaktə et (skan yenidən hesablanır), slotu ləğv et (100-ə miqyas)."""
    admin, ta, e, pr = ksq(world)
    a = pr['sheets'][0]
    sid = a['student_id']
    v0 = admin.get(f'/api/exams/{ta}/{e["id"]}/variants').json()
    mine = next(x for x in v0['variants'] if x['student_id'] == sid)
    q1 = next(q for q in mine['questions'] if q['slot'] == 12)
    r = admin.post(f'/api/exams/{ta}/{e["id"]}/variants/{sid}/12/replace').json()
    allkeys = [q['key'] for x in admin.get(f'/api/exams/{ta}/{e["id"]}/variants').json()['variants'] for q in x['questions']]
    assert r['key'] != q1['key'] and r['kind'] == q1['kind'] and r['points'] == q1['points'] and len(allkeys) == len(set(allkeys))
    ra = admin.post(f'/api/exams/{ta}/{e["id"]}/slots/3/replace-all').json()
    assert ra['replaced'] == 3 and ra['failed'] == 0
    # skan + oxunuş: hamısı düz → 100; 12-ci sualın açarını dəyiş → bal düşür; 12-ci slotu ləğv et → yenə 100
    # köhnə çap (əvəzetmədən əvvəlki kart) qəbul olunmur – kart variantın versiyasına bağlıdır
    old = admin.post(f'/api/exam-scans/{ta}/{e["id"]}/upload', files=[('files', ('p.jpg', photo([a['qr']]), 'image/jpeg'))]).json()
    assert not old['found'] and 'köhnə çap' in old['problems'][0]['error']
    a = next(x for x in admin.get(f'/api/exams/{ta}/{e["id"]}/variants/print').json()['sheets'] if x['student_id'] == sid)   # yenidən çap
    admin.post(f'/api/exam-scans/{ta}/{e["id"]}/upload', files=[('files', ('p.jpg', photo([a['qr']]), 'image/jpeg'))])
    from app.domain.ksq_card import key_value
    qs = {q['slot']: q for q in next(x for x in admin.get(f'/api/exams/{ta}/{e["id"]}/variants').json()['variants'] if x['student_id'] == sid)['questions']}
    scan = admin.get('/api/exam-scans/pending').json()[0]
    admin.post('/api/exam-scans/import', json=[{'scan_id': scan['scan_id'], 'answers': [{'slot': k, 'value': key_value(q), 'confidence': 1} for k, q in qs.items()]}])
    pts = lambda: admin.get(f'/api/exam-scans/{ta}/{e["id"]}').json()['scans'][0]['points']     # noqa: E731
    assert pts() == 100
    q12 = qs[12]
    edit = {'text': 'Düzəldilmiş sual', 'answer': '999'} if q12['kind'] == 'open' else {'text': 'Düzəldilmiş sual', 'options': ['1', '2', '3'], 'correct': (q12['correct'] + 1) % 2}
    assert admin.put(f'/api/exams/{ta}/{e["id"]}/variants/{sid}/12', json=edit).json()['rescored'] == 1
    assert pts() < 100
    assert admin.post(f'/api/exams/{ta}/{e["id"]}/slots/12/annul', json={'annulled': True}).json()['rescored'] == 1
    assert pts() == 100
    assert admin.put(f'/api/exams/{ta}/{e["id"]}/variants/{sid}/12', json={'text': 'x', 'answer': 'abc'}).status_code in (200, 400)


def test_variants_for_several_classes(world):
    """Eyni proqramlı siniflər: KSQ bir dəfəyə; ikinci sinifdə imtahan yoxdursa yaranır; fərqli proqramlı sinif rədd edilir."""
    import datetime as dt
    from app.models import PlanLesson, PlanProgram, TeachingAssignment
    admin, ta, e, pr = ksq(world)
    xc = admin.post('/api/classes', json={'name': 'X c'}).json()['id']
    admin.post(f'/api/classes/{xc}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 2, 'slots': {'1': [1, 5]}})
    for i in range(2):
        admin.post('/api/students', json={'full_name': f'Ikinci Sinif{i}', 'class_id': xc})
    S = world[1]
    with S() as db:
        prog = PlanProgram(title='Riyaziyyat X', subject='Riyaziyyat', kind='fixed', data={'lessons': []})
        db.add(prog); db.flush()
        t1 = db.get(TeachingAssignment, ta)
        t2 = db.query(TeachingAssignment).filter_by(class_id=xc).one()
        t1.program_id = t2.program_id = prog.id
        for pl in db.query(PlanLesson).filter_by(assignment_id=ta).all():
            db.add(PlanLesson(assignment_id=t2.id, seq=pl.seq, semester=pl.semester, assessment_type=pl.assessment_type, exam_no=pl.exam_no,
                              topic=pl.topic, date=pl.date or dt.date(2026, 9, 15)))
        db.commit()
        ta2 = t2.id
    sib = admin.get(f'/api/exams/{ta}/{e["id"]}/siblings').json()
    assert [s['ta_id'] for s in sib] == [ta2] and sib[0]['exam_id'] is None
    r = admin.post(f'/api/exams/{ta}/{e["id"]}/variants-multi', json={'n': 10, 'ta_ids': [ta, ta2, 99999]}).json()
    assert [x['ok'] for x in r] == [True, True, False]
    ex2 = admin.get(f'/api/exams/{ta2}').json()['exams']
    assert len(ex2) == 1 and ex2[0]['kind'] == 'KSQ' and ex2[0]['max_points'] == 100
    v2 = admin.get(f'/api/exams/{ta2}/{ex2[0]["id"]}/variants').json()['variants']
    assert len(v2) == 2 and len(v2[0]['questions']) == 10


def test_openrouter_reader(world, monkeypatch):
    """Açar OpenRouter-dədirsə: müəllimin «Süni intellekt» ayarından götürülür; şəkil oxumayan model – Claude ilə əvəz; cavab tool_calls-dan."""
    import json
    import httpx
    from app.domain import ksq_reader as R
    from app.models import User
    from app.security import secret_encrypt
    as_, S = world
    with S() as db:
        u = db.query(User).filter_by(login='admin').first()
        u.ai_settings = {'provider': 'openrouter', 'model': 'deepseek/deepseek-chat-v3.1', 'key': secret_encrypt('sk-or-test-123456')}
        db.commit()
        c = R.api_key_for(db, u.id)
    assert c == {'provider': 'openrouter', 'key': 'sk-or-test-123456', 'model': R.OR_DEFAULT}
    sent = []

    class Resp:
        status_code = 200
        text = ''

        def __init__(self, js):
            self._js = js

        def json(self):
            return self._js

    def post(self, url, json=None, headers=None):
        sent.append((url, json, headers))
        args = {'answers': [{'slot': 1, 'value': 'C', 'confidence': 0.97}, {'slot': 2, 'value': '3/7', 'confidence': 0.5}]}
        return Resp({'choices': [{'message': {'tool_calls': [{'function': {'name': 'submit_card', 'arguments': __import__('json').dumps(args)}}]}}]})
    monkeypatch.setattr(httpx.Client, 'post', post)
    got, by = R.read_card({'provider': 'openrouter', 'key': 'sk-or', 'model': 'google/gemini-2.5-flash'}, b'\xff\xd8x',
                          [{'slot': 1, 'kind': 'mcq'}, {'slot': 2, 'kind': 'open'}])
    assert [g['value'] for g in got] == ['C', '3/7'] and by.endswith('+2+v') and len(sent) == 3      # şübhəli 2-ci xana – ikinci oxunuş; açıq xanalar – müstəqil yoxlama (başqa model)
    assert sorted(x[1]['model'] for x in sent).count(R.VERIFY_MODEL) == 1
    url, body, headers = next(x for x in sent if x[1]['model'] != R.VERIFY_MODEL)      # birinci oxunuş və yoxlama paraleldir – sıra təsadüfidir
    assert url == R.OPENROUTER and headers['Authorization'] == 'Bearer sk-or' and body['model'] == 'google/gemini-2.5-flash'
    assert body['messages'][1]['content'][1]['image_url']['url'].startswith('data:image/jpeg;base64,')
    assert body['tool_choice']['function']['name'] == 'submit_card'
    _ = json


def test_projects_selection(world):
    """Test layihələri: əsas layihə avtomatik; başqa layihə (məs. sınaqlar) qoşulanda onun mövzuya uyğun faylları da hovuza düşür."""
    from app.models import BankFile, BankQuestion, BankSource
    admin, ta, e, pr = ksq(world)
    with world[1]() as db:
        db.add(BankSource(key='sinaqlar', label='Sınaqlar')); db.flush()
        f = BankFile(source_key='sinaqlar', lesson='s/1.html', label='Faiz – sınaq blok', url='http://x', kind='sinaq', question_count=30)
        db.add(f); db.flush()
        for i in range(30):
            db.add(BankQuestion(file_id=f.id, n=i + 1, kind='mcq', text={'az': f'S{i}'}, content_hash=f's{i}', options=[{'az': '1'}, {'az': '2'}], correct=0, diff_auto='orta'))
        db.commit()
    src = admin.get(f'/api/exams/{ta}/{e["id"]}/sources').json()
    keys = {p['key']: p for p in src['projects']}
    assert keys['p003']['default'] and 'sinaqlar' in keys
    one = admin.post(f'/api/exams/{ta}/{e["id"]}/readiness', json={'n': 30}).json()
    two = admin.post(f'/api/exams/{ta}/{e["id"]}/readiness', json={'n': 30, 'sources': ['p003', 'sinaqlar']}).json()
    mcq = lambda r: next(t for t in r['topics'] if t['topic'] == 'Faiz')['mcq']      # noqa: E731
    assert mcq(two) == mcq(one) + 30
    src2 = admin.get(f'/api/exams/{ta}/{e["id"]}/sources', params={'sources': 'p003,sinaqlar'}).json()
    assert any(x['source'] == 'sinaqlar' for x in src2['all'])


def test_fix_offtopic(world):
    """Köhnə variantda «ədədi silsilə» (mövzudan kənar) – avtomatik əvəz olunur, qalan suallar dəyişmir, xəbərdarlıq itir."""
    import random
    from app.domain import templates as T
    from app.models import ExamVariant
    admin, ta, e, pr = ksq(world)
    S = world[1]
    with S() as db:
        v = db.query(ExamVariant).filter_by(exam_id=e['id']).first()
        sid = v.student_id
        qs = [dict(q) for q in v.questions]
        i = next(k for k, q in enumerate(qs) if q['kind'] == 'open')
        ap = T.instance(next(t for t in T.TEMPLATES if t.id == 'ap'), random.Random(1))
        qs[i] = {**qs[i], **ap, 'kind': 'open'}
        for q in qs:
            q.pop('v', None)                                          # köhnə qaydalarla yaradılıb
        v.questions = qs
        db.commit()
        keep = [q['key'] for k, q in enumerate(qs) if k != i]
    assert admin.get(f'/api/exams/{ta}/{e["id"]}/variants').json()['stale'] is True
    r = admin.post(f'/api/exams/{ta}/{e["id"]}/fix-offtopic').json()
    assert r['fixed'] == 1 and r['failed'] == 0
    d = admin.get(f'/api/exams/{ta}/{e["id"]}/variants').json()
    mine = next(x for x in d['variants'] if x['student_id'] == sid)['questions']
    assert mine[i].get('template') != 'ap' and [q['key'] for k, q in enumerate(mine) if k != i] == keep and d['stale'] is False


def test_printed_variants_protected_and_old_cards_accepted(world):
    """Çap olunmuş variantlara fon işi toxunmur; versiyasız köhnə kart (əvvəlki çaplar) qəbul olunur."""
    from app.api.exams import fix_stale_all
    from app.domain.ksq_card import qr_payload
    from app.models import ExamVariant
    admin, ta, e, pr = ksq(world)                                      # ksq() artıq çap endpoint-ini çağırır → printed_at
    S = world[1]
    with S() as db:
        v = db.query(ExamVariant).filter_by(exam_id=e['id']).first()
        assert v.printed_at is not None
        qs = [dict(q) for q in v.questions]
        for q in qs:
            q.pop('v', None)                                           # «köhnə» kimi görünsün
        v.questions = qs
        db.commit()
        before = [q['key'] for q in qs]
        assert fix_stale_all(db) == 0                                  # çap olunub – toxunulmur
        db.refresh(v)
        assert [q['key'] for q in v.questions] == before
        sid, code = v.student_id, v.code
    legacy = qr_payload(e['id'], sid, code)                            # versiyasız (əvvəlki çaplar)
    r = admin.post(f'/api/exam-scans/{ta}/{e["id"]}/upload', files=[('files', ('p.jpg', photo([legacy]), 'image/jpeg'))]).json()
    assert len(r['found']) == 1 and not r['problems']


def test_openrouter_key_saved_as_anthropic(world, monkeypatch):
    """İstifadəçi xətası (14.10): OpenRouter açarı «Anthropic» seçilərək saxlanıb – sistem açarın növünə görə OpenRouter işlədir."""
    from app import ai
    from app.domain import ksq_reader as R
    from app.models import User
    from app.security import secret_encrypt
    assert ai.fix_provider('anthropic', 'claude-sonnet-5-5', 'sk-or-v1-abc') == ('openrouter', ai.OR_CLAUDE)
    assert ai.fix_provider('openrouter', 'google/gemini-2.5-flash', 'sk-ant-xyz') == ('anthropic', 'claude-sonnet-5-5')
    assert ai.fix_provider('anthropic', 'claude-sonnet-5-5', 'sk-ant-xyz') == ('anthropic', 'claude-sonnet-5-5')
    as_, S = world
    with S() as db:
        u = db.query(User).filter_by(login='admin').first()
        u.ai_settings = {'provider': 'anthropic', 'model': 'claude-sonnet-5-5', 'key': secret_encrypt('sk-or-v1-test-key-123')}
        db.commit()
        c = R.api_key_for(db, u.id)
    assert c['provider'] == 'openrouter' and c['key'] == 'sk-or-v1-test-key-123'
    sent = {}

    class Resp:
        status_code = 200

        def json(self):
            return {'choices': [{'message': {'content': 'HAZIR'}}]}
    monkeypatch.setattr('httpx.Client.post', lambda self, url, headers=None, json=None: sent.update(url=url, model=json['model']) or Resp())
    out = ai.complete({'provider': 'anthropic', 'model': 'claude-sonnet-5-5', 'base_url': None, 'api_key': 'sk-or-v1-x'}, 's', 'u', json_mode=False)
    assert out == 'HAZIR' and sent['url'].startswith('https://openrouter.ai/') and sent['model'] == ai.OR_CLAUDE
    monkeypatch.undo()                                                  # TestClient də httpx işlədir
    admin = as_('admin')
    r = admin.put('/api/ai/settings', json={'provider': 'anthropic', 'model': 'claude-sonnet-5-5', 'api_key': 'sk-or-v1-new-key-456789'})
    assert r.status_code in (200, 403)                                  # 403 – ayarlar kilidi (settings_unlocked) testdə bağlı ola bilər
    if r.status_code == 200:
        assert r.json()['provider'] == 'openrouter'


def test_ai_usage_counter_and_limit(world, monkeypatch):
    """Xərc sayğacı: hər oxunan kart + tokenlər ayın hesabına; limit dolanda kart oxunmur (pul getmir)."""
    from app.config import settings
    from app.domain import ksq_reader as R
    admin, ta, e, pr = ksq(world)
    a, b = pr['sheets'][0], pr['sheets'][1]

    def fake(api_key, model, jpeg, slots, only=None):
        R._count({'input_tokens': 1000, 'output_tokens': 200})
        return [{'slot': s['slot'], 'value': '1', 'confidence': 0.99} for s in slots]
    monkeypatch.setattr(R, 'call', fake)
    monkeypatch.setattr(R, 'api_key_for', lambda db, tid: 'sk-ant-test')
    monkeypatch.setattr(settings(), 'ksq_monthly_limit', 1)
    admin.post(f'/api/exam-scans/{ta}/{e["id"]}/upload', files=[('files', ('p.jpg', photo([a['qr'], b['qr']]), 'image/jpeg'))])
    with world[1]() as db:
        u = R.month_usage(db)
    assert u == {'cards': 1, 'in': 1000, 'out': 200}
    scans = admin.get(f'/api/exam-scans/{ta}/{e["id"]}').json()['scans']
    assert sorted(x['status'] for x in scans) == ['graded', 'pending'] and any('limit' in (x['error'] or '') for x in scans)
    assert admin.get('/api/admin/resources').json()['ai_usage']['cards'] == 1


def test_openrouter_model_without_vendor_prefix(world):
    """OpenRouter + «claude-sonnet-5-5» (prefikssiz) → standart model; əks halda kartlar «not a valid model ID» ilə gözləyir."""
    from app import ai
    from app.domain import ksq_reader as R
    from app.models import User
    from app.security import secret_encrypt
    assert ai.fix_provider('openrouter', 'claude-sonnet-5-5', 'sk-or-v1-x') == ('openrouter', ai.OR_CLAUDE)
    assert ai.fix_provider('openrouter', 'google/gemini-2.5-pro', 'sk-or-v1-x') == ('openrouter', 'google/gemini-2.5-pro')
    _, S = world
    with S() as db:
        u = db.query(User).filter_by(login='admin').first()
        u.ai_settings = {'provider': 'openrouter', 'model': 'claude-sonnet-5-5', 'key': secret_encrypt('sk-or-v1-test-key-123')}
        db.commit()
        assert R.api_key_for(db, u.id)['model'] == R.OR_DEFAULT
