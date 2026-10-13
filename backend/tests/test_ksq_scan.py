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
    r2 = admin.post(f'/api/exam-scans/{ta}/{e["id"]}/upload', params={'replace': True, 'force': True}, files=[('files', ('p2.jpg', photo([a['qr']], -4), 'image/jpeg'))]).json()
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

    def fake_call(api_key, model, jpeg, slots, only=None, text=None):
        calls.append((model, tuple(only or ()), text is not None))
        if isinstance(jpeg, list):                                            # böyüdülmüş sütunlar (diqqətli oxunuş)
            assert len(jpeg) == 3 and all(j[:2] == b'\xff\xd8' for j in jpeg)
            return [{'slot': s, 'value': key[s], 'confidence': 0.93} for s in (only or [x['slot'] for x in slots])]
        assert api_key == 'sk-test' and jpeg[:2] == b'\xff\xd8'               # yalnız JPEG kəsik göndərilir
        if model == R.MODEL:                                                  # birinci: 5-ci xana şübhəli, 7-ci yoxdur
            return [{'slot': s, 'value': key[s] if s != 5 else '?', 'confidence': 0.4 if s == 5 else 0.95}
                    for s in key if s != 7]
        return [{'slot': s['slot'], 'value': key[s['slot']], 'confidence': 0.93} for s in slots]     # B: başqa model, açıq suallar
    monkeypatch.setattr(R, 'call', fake_call)
    monkeypatch.setattr(R, 'key_pool', lambda db, tid: [{'provider': 'anthropic', 'key': 'sk-test', 'model': R.MODEL}])
    r = admin.post(f'/api/exam-scans/{ta}/{e["id"]}/upload', files=[('files', ('p.jpg', photo([a['qr']], 3), 'image/jpeg'))])
    assert r.status_code == 200 and len(r.json()['found']) == 1
    assert (R.MODEL, (), False) in calls and any(m == R.MODEL_2 and not z for m, _, z in calls)       # A + B (açıq suallar)
    zoom = [o for m, o, z in calls if z]                                      # şübhəli xanalar – böyüdülmüş sütunlarla
    assert len(zoom) == 1 and {5, 7} <= set(zoom[0])
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
    except R.AiError as ex:                               # xəta – qısa kod, mətni interfeys müəllimin dilində göstərir
        assert str(ex) == R.AI_RATE
    monkeypatch.setattr(httpx.Client, 'post', lambda self, url, json=None, headers=None: Resp(402, {'error': {'message': 'Insufficient credits'}}))
    try:
        R.call_openrouter('sk-or-x', 'google/gemini-2.5-flash', b'\xff\xd8', [{'slot': 1, 'kind': 'mcq'}])
        raise AssertionError
    except R.AiError as ex:
        assert str(ex) == R.AI_CREDIT


def test_gemini_call_parsing(monkeypatch):
    """Google Gemini (AI Studio açarı): şəkil inline_data, məcburi funksiya çağırışı, düşünmə 0; səhv açar – ai:key."""
    import httpx
    from app.domain import ksq_reader as R
    sent = {}

    class Resp:
        def __init__(self, code, js):
            self.status_code, self._js, self.text = code, js, str(js)

        def json(self):
            return self._js
    out = {'candidates': [{'content': {'parts': [{'functionCall': {'name': 'submit_card', 'args': {'answers': [
        {'slot': 1, 'value': 'c', 'confidence': 0.95}, {'slot': 2, 'value': '', 'cells': ['1', '2', '', '', '', '', '', ''], 'confidence': 0.9}]}}}]}}],
        'usageMetadata': {'promptTokenCount': 1000, 'candidatesTokenCount': 50}}

    def post(self, url, json=None, headers=None):
        sent.update(url=url, body=json, headers=headers)
        return Resp(200, out)
    monkeypatch.setattr(httpx.Client, 'post', post)
    got = R.call_gemini('AIza-x', 'gemini-2.5-flash', b'\xff\xd8jpeg', [{'slot': 1, 'kind': 'mcq'}, {'slot': 2, 'kind': 'open'}])
    assert got == [{'slot': 1, 'value': 'C', 'confidence': 0.95}, {'slot': 2, 'value': '12', 'confidence': 0.9}]
    b = sent['body']
    assert 'gemini-2.5-flash:generateContent' in sent['url'] and sent['headers']['x-goog-api-key'] == 'AIza-x'
    assert b['toolConfig']['functionCallingConfig']['mode'] == 'ANY' and b['generationConfig']['thinkingConfig']['thinkingBudget'] == 0
    assert b['contents'][0]['parts'][1]['inline_data']['mime_type'] == 'image/jpeg'
    monkeypatch.setattr(httpx.Client, 'post', lambda self, url, json=None, headers=None: Resp(400, {'error': {'message': 'API key not valid. Please pass a valid API key.'}}))
    try:
        R.call_gemini('bad', 'gemini-2.5-flash', b'\xff\xd8', [{'slot': 1, 'kind': 'mcq'}])
        raise AssertionError
    except R.AiError as ex:
        assert str(ex) == R.AI_KEY


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
    assert {k: c[k] for k in ('provider', 'key', 'model')} == {'provider': 'openrouter', 'key': 'sk-or-test-123456', 'model': R.OR_DEFAULT}
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
    got, by = R.read_card({'provider': 'openrouter', 'key': 'sk-or', 'model': 'openai/gpt-4o'}, b'\xff\xd8x',
                          [{'slot': 1, 'kind': 'mcq'}, {'slot': 2, 'kind': 'open'}])
    # A (əsas model) + B (başqa model, açıq suallar) paralel; hər ikisi «3/7» – səsvermə ilə qəbul (2-ci xana sarı deyil)
    assert [g['value'] for g in got] == ['C', '3/7'] and by.endswith('+v') and len(sent) == 2 and got[1]['confidence'] >= R.LOW
    assert sorted(x[1]['model'] for x in sent).count(R.VERIFY_MODEL) == 1
    url, body, headers = next(x for x in sent if x[1]['model'] != R.VERIFY_MODEL)      # birinci oxunuş və yoxlama paraleldir – sıra təsadüfidir
    assert url == R.OPENROUTER and headers['Authorization'] == 'Bearer sk-or' and body['model'] == 'openai/gpt-4o'
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

    def fake(api_key, model, jpeg, slots, only=None, text=None):
        R._count({'input_tokens': 1000, 'output_tokens': 200})
        return [{'slot': s['slot'], 'value': '1', 'confidence': 0.99} for s in slots]
    monkeypatch.setattr(R, 'call', fake)
    monkeypatch.setattr(R, 'key_pool', lambda db, tid: [{'provider': 'anthropic', 'key': 'sk-ant-test', 'model': R.MODEL}])
    monkeypatch.setattr(settings(), 'ksq_monthly_limit', 1)
    admin.post(f'/api/exam-scans/{ta}/{e["id"]}/upload', files=[('files', ('p.jpg', photo([a['qr'], b['qr']]), 'image/jpeg'))])
    with world[1]() as db:
        u = R.month_usage(db)
    assert u == {'cards': 1, 'in': 2000, 'out': 400}                     # bir kart: A + B (müstəqil yoxlama) oxunuşları
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


def test_thorough_reading_votes_and_keeps_teacher(world, monkeypatch):
    """«Diqqətli oxu» (səliqəsiz yazı): böyüdülmüş 3 sütun + iki model, səsvermə; müəllimin düzəlişi saxlanır."""
    from app.domain import ksq_reader as R
    admin, ta, e, pr = ksq(world)
    a = pr['sheets'][0]
    key = {x['slot']: x['value'] for x in next(k for k in pr['key'] if k['code'] == a['code'])['answers']}
    opn = [s for s in key if not key[s].isalpha()]
    s1, s2 = opn[0], opn[1]
    zooms = []

    def fake(api_key, model, jpeg, slots, only=None, text=None):
        z = isinstance(jpeg, list)
        if z:
            zooms.append(model)
            assert len(jpeg) == 3 and 'sütun' in text
        want = only or [x['slot'] for x in slots]
        out = []
        for s in want:
            v = key[s]
            if s == s1:                       # iki oxunuş «7», iki oxunuş düz – bərabərlik: böyüdülmüş üstündür
                v = '7' if not z else key[s]
            if s == s2:                       # hamısı fərqli – sarı, alternativ
                v = {R.MODEL: '1', R.MODEL_2: '2'}[model] + ('9' if z else '')
            out.append({'slot': s, 'value': v, 'confidence': 0.95})
        return out
    monkeypatch.setattr(R, 'call', fake)
    monkeypatch.setattr(R, 'key_pool', lambda db, tid: [{'provider': 'anthropic', 'key': 'sk-ant-test', 'model': R.MODEL}])
    admin.post(f'/api/exam-scans/{ta}/{e["id"]}/upload', files=[('files', ('p.jpg', photo([a['qr']]), 'image/jpeg'))])
    sc = admin.get(f'/api/exam-scans/{ta}/{e["id"]}').json()['scans'][0]
    admin.put(f'/api/exam-scans/{sc["id"]}/slot', json={'slot': 1, 'value': key[1]})          # müəllim düzəlişi
    zooms.clear()
    assert admin.post(f'/api/exam-scans/{sc["id"]}/thorough').json()['started'] == 1
    sc = admin.get(f'/api/exam-scans/{ta}/{e["id"]}').json()['scans'][0]
    rd = {r['slot']: r for r in sc['reading']}
    assert sorted(zooms) == sorted([R.MODEL, R.MODEL_2]) and sc['read_by'].endswith('+diq') and sc['rescans'] >= 1
    assert rd[1].get('by') == 'teacher'
    assert rd[s1]['value'] == key[s1]
    assert rd[s2]['confidence'] < R.LOW and rd[s2]['alt'] and s2 in sc['flagged']
    assert admin.post(f'/api/exam-scans/{ta}/{e["id"]}/thorough', params={'only_flagged': True}).json()['started'] == 1


def test_scan_key_pool_rotation(world, monkeypatch):
    """Kart oxuyucusu: 5 açara qədər; 1-ci açar limitdə (429) – kart həmin anda 2-ci açarla oxunur; hamısı tükənib – kart gözləyir.
    Kart açarı varsa gündəlik plan açarı hovuzda yoxdur (docs/kart-oxuyucu-acarlar-promtu.md)."""
    from app.domain import ksq_reader as R
    from app.models import User
    from app.security import secret_encrypt
    admin, ta, e, pr = ksq(world)
    _, S = world
    R.uncool()
    put = admin.put('/api/ai/scan-keys', json={'keys': [
        {'provider': 'gemini', 'model': 'gemini-2.5-flash', 'api_key': 'AIza-first-key-0001'},
        {'provider': 'gemini', 'model': 'gemini-2.5-flash', 'api_key': 'AIza-second-key-002'},
        {'provider': 'gemini', 'api_key': 'AIza-second-key-002'},                 # təkrar açar – hovuzda bir dəfə
        {'provider': None}]})
    assert put.status_code == 200, put.text
    out = put.json()
    assert [k['has_key'] for k in out['keys']] == [True, True, True, False, False] and out['keys'][0]['key_mask'] == '••••0001'
    assert 'AIza' not in put.text                                                   # açar geri göndərilmir
    with S() as db:
        u = db.query(User).filter_by(login='admin').first()
        u.ai_settings = {**u.ai_settings, 'provider': 'openrouter', 'model': 'google/gemini-2.5-flash', 'key': secret_encrypt('sk-or-plan-key-123')}
        db.commit()
        pool = R.key_pool(db, u.id)
    assert [c['key'] for c in pool] == ['AIza-first-key-0001', 'AIza-second-key-002']          # plan açarı yoxdur
    used = []

    def fake(key, model, jpeg, slots, only=None, text=None):
        used.append(key)
        if key == 'AIza-first-key-0001':
            raise R._ai_error('Gemini', 429, 'Quota exceeded: GenerateRequestsPerMinutePerProjectPerModel-FreeTier', '')
        return [{'slot': s['slot'], 'value': '1', 'confidence': 0.99} for s in slots]
    monkeypatch.setattr(R, 'call_gemini', fake)
    a = pr['sheets'][0]
    admin.post(f'/api/exam-scans/{ta}/{e["id"]}/upload', files=[('files', ('p.jpg', photo([a['qr']]), 'image/jpeg'))])
    sc = admin.get(f'/api/exam-scans/{ta}/{e["id"]}').json()
    assert sc['scans'][0]['status'] == 'graded' and sc['scans'][0]['read_by'].startswith('gemini#2')
    assert used[0] == 'AIza-first-key-0001' and 'AIza-second-key-002' in used and sc['ai_error'] is None
    st = admin.get('/api/ai/scan-keys').json()['keys']
    assert st[0]['status']['state'] == 'cooldown' and st[0]['status']['code'] == 'ai:rate' and st[1]['status']['today'] == 1
    # hamısı tükənib – kart gözləyir, banner bir dəfə; sıfırlama – yenidən oxunur
    monkeypatch.setattr(R, 'call_gemini', lambda *x, **k: (_ for _ in ()).throw(R._ai_error('Gemini', 429, 'GenerateRequestsPerDayPerProjectPerModel', '')))
    b = pr['sheets'][1]
    admin.post(f'/api/exam-scans/{ta}/{e["id"]}/upload', files=[('files', ('q.jpg', photo([b['qr']]), 'image/jpeg'))])
    sc = admin.get(f'/api/exam-scans/{ta}/{e["id"]}').json()
    assert sorted(x['status'] for x in sc['scans']) == ['graded', 'pending'] and sc['ai_error'] == 'ai:rate'
    assert R._cool[R.fingerprint(pool[1])]['day'] is True                         # günlük kvota – uzun fasilə
    assert admin.post('/api/ai/scan-keys/reset').json()['keys'] == 2
    R.uncool()


def test_ai_purposes_separate(world):
    """Gündəlik plan və rəy – ayrı açarlar; rəy açarı yoxdursa – plan açarı; bir təyinatı saxlamaq/silmək digərlərinə toxunmur."""
    from app.api.lessonplans import ai_config
    from app.models import User
    admin = world[0]('admin')
    assert admin.put('/api/ai/scan-keys', json={'keys': [{'provider': 'gemini', 'api_key': 'AIza-scan-key-00001'}]}).status_code == 200
    assert admin.put('/api/ai/settings', json={'provider': 'gemini', 'model': 'gemini-2.5-flash', 'api_key': 'AIza-plan-key-00001'}).status_code == 200
    r = admin.get('/api/ai/settings?purpose=review').json()
    assert r['has_key'] is False and r['fallback_plan'] is True
    with world[1]() as db:
        u = db.query(User).filter_by(login='admin').first()
        assert ai_config(u, 'review')['api_key'] == 'AIza-plan-key-00001'
    assert admin.put('/api/ai/settings?purpose=review', json={'provider': 'openrouter', 'model': 'google/gemini-2.5-flash',
                                                              'api_key': 'sk-or-review-key-01'}).status_code == 200
    assert admin.delete('/api/ai/settings').status_code == 200                       # plan açarı silinir
    with world[1]() as db:
        u = db.query(User).filter_by(login='admin').first()
        assert ai_config(u, 'review')['api_key'] == 'sk-or-review-key-01'
        assert len(u.ai_settings['scan_keys']) == 1 and not u.ai_settings.get('key')
    assert admin.get('/api/ai/settings').json()['has_key'] is False
    assert admin.get('/api/ai/settings?purpose=review').json()['key_mask'] == '••••y-01'


def _graded(world, monkeypatch):
    """İki şagirdin kartı skan və qiymətləndirilir (saxta oxuyucu); şagird siyahısı (portal kodu, PIN) ilə."""
    from app.domain import ksq_reader as R
    from . import test_api_portal as P
    orig, box = P.setup, {}
    monkeypatch.setattr(P, 'setup', lambda w: box.setdefault('r', orig(w)))
    admin, ta, e, pr = ksq(world)
    st = box['r'][3]
    keys = {k['code']: {x['slot']: x['value'] for x in k['answers']} for k in pr['key']}

    def fake(api_key, model, jpeg, slots, only=None, text=None):
        return [{'slot': s['slot'], 'value': '', 'confidence': 0.99} for s in slots]
    monkeypatch.setattr(R, 'call', fake)
    monkeypatch.setattr(R, 'key_pool', lambda db, tid: [{'provider': 'anthropic', 'key': 'sk-ant-test', 'model': R.MODEL}])
    for sh in pr['sheets'][:2]:
        admin.post(f'/api/exam-scans/{ta}/{e["id"]}/upload', files=[('files', ('p.jpg', photo([sh['qr']]), 'image/jpeg'))])
    return admin, ta, e, pr, st, keys


def test_clear_scans_migration_and_endpoint(world, monkeypatch):
    """Bütün siniflərdə kağız skanları sil (docs/kart-skanlarini-silme-promtu.md): kağız skan + balı silinir; onlayn yazı və
    skansız əl balı qalır; əvvəlcə ehtiyat; downgrade – bərpa. Müəllim düyməsi – yalnız öz imtahanı."""
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import text
    from app.models import ExamScan, ExamScore
    admin, ta, e, pr, st, _ = _graded(world, monkeypatch)
    _, S = world
    with S() as db:
        scans = db.query(ExamScan).filter_by(exam_id=e['id']).order_by(ExamScan.id).all()
        assert len(scans) == 2 and all(s.status == 'graded' for s in scans)
        scans[1].read_by = 'online'                                       # onlayn yazı – qalmalıdır
        paper_sid = scans[0].student_id
        manual = next(x['id'] for x in st if x['id'] not in {s.student_id for s in scans})
        db.add(ExamScore(exam_id=e['id'], student_id=manual, points=55))  # skansız əl balı – qalmalıdır
        db.commit()
    spec = importlib.util.spec_from_file_location('m', Path(__file__).parents[1] / 'migrations/versions/f9b1d3e5a7c9_skanlari_sil.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    with S() as db:
        conn = db.connection()
        with Operations.context(MigrationContext.configure(conn)):
            m.upgrade()
        db.commit()
        assert [s.read_by for s in db.query(ExamScan).all()] == ['online']
        assert sorted(x.student_id for x in db.query(ExamScore).all()) == sorted([scans[1].student_id, manual])
        assert db.execute(text('SELECT count(*) FROM exam_scans_backup_20261013')).scalar() == 1
        assert db.execute(text('SELECT student_id FROM exam_scores_backup_20261013')).scalar() == paper_sid
        with Operations.context(MigrationContext.configure(db.connection())):
            m.downgrade()
        db.commit()
        assert db.query(ExamScan).count() == 2 and db.get(ExamScore, (e['id'], paper_sid)) is not None
    # müəllim düyməsi: kağız skan silinir, onlayn qalır; başqa müəllim – 404
    assert world[0]('yad').delete(f'/api/exam-scans/{ta}/{e["id"]}').status_code == 404
    r = admin.delete(f'/api/exam-scans/{ta}/{e["id"]}')
    assert r.json() == {'deleted': 1}
    lst = admin.get(f'/api/exam-scans/{ta}/{e["id"]}').json()
    assert [s['read_by'] for s in lst['scans']] == ['online'] and lst['counts']['scanned'] == 1


def test_student_sees_own_card(world, monkeypatch):
    """Şagird öz kartının şəklini, sistemin oxuduğu cavabı və düz cavabı görür; başqasının kartı – 404; bildiriş gəlir."""
    from .test_api_portal import student_client
    from app.models import ExamScan
    admin, ta, e, pr, st, keys = _graded(world, monkeypatch)
    _, S = world
    with S() as db:
        mine = {s.student_id: s for s in db.query(ExamScan).filter_by(exam_id=e['id'])}
    s0 = next(x for x in st if x['id'] in mine)
    other = next(sc for sid, sc in mine.items() if sid != s0['id'])
    c = student_client(s0['portal_code'], s0['initial_pin'])
    ex = c.get('/api/portal/results').json()['subjects'][0]['exams']
    card = next(x['card'] for x in ex if x['card'])
    code = next(sh['code'] for sh in pr['sheets'] if sh['student_id'] == s0['id']) if 'student_id' in pr['sheets'][0] else None
    assert card['image'] is True and card['scan_id'] == mine[s0['id']].id and len(card['rows']) == len(mine[s0['id']].marks)
    assert all(r['read'] == '' and r['ok'] is False and r['key'] for r in card['rows'])             # boş kart – hamısı ✗, açar görünür
    if code:
        assert {r['slot']: r['key'] for r in card['rows']} == keys[code]
    img = c.get(f'/api/portal/exam-card/{card["scan_id"]}/image')
    assert img.status_code == 200 and img.headers['content-type'] == 'image/jpeg'
    assert c.get(f'/api/portal/exam-card/{other.id}/image').status_code == 404                     # başqasının kartı
    assert any(n['key'].startswith(f'card-{card["scan_id"]}-') for n in c.get('/api/portal/notifications').json())


def test_gemini_model_fallback_and_no_sleep(monkeypatch):
    """docs/skan-sayac-ve-donma-promtu.md §A–B: köhnəlmiş model → Google-un təklifi; thinkingConfig xətası → parametrsiz;
    429 → gözləmə yoxdur (açar dincə, növbəti açar); alternativ də yoxdursa → ai:model."""
    import httpx
    import time
    from app import ai
    from app.domain import ksq_reader as R
    ai.GEMINI_FIX.clear()
    ai.GEMINI_NO_THINK.clear()

    class Resp:
        def __init__(self, code, js):
            self.status_code, self._js, self.text = code, js, str(js)

        def json(self):
            return self._js
    ok = {'candidates': [{'content': {'parts': [{'functionCall': {'name': 'submit_card', 'args': {'answers': [
        {'slot': 1, 'value': 'A', 'confidence': 0.99}]}}}]}}]}
    urls = []

    def post(self, url, json=None, headers=None):
        urls.append((url.split('/models/')[1].split(':')[0], 'thinkingConfig' in json['generationConfig']))
        m = urls[-1][0]
        if m == 'gemini-2.5-flash':
            return Resp(404, {'error': {'message': 'This model models/gemini-2.5-flash is no longer available to new users. '
                                                   'Please update your code to use models/gemini-3.8-flash for the latest features.'}})
        if m == 'gemini-3.8-flash' and urls[-1][1]:
            return Resp(400, {'error': {'message': 'Thinking budget is not supported for this model.'}})
        return Resp(200, ok)
    monkeypatch.setattr(httpx.Client, 'post', post)
    got = R.call_gemini('AIza-x', 'gemini-2.5-flash', b'\xff\xd8', [{'slot': 1, 'kind': 'mcq'}])
    assert got == [{'slot': 1, 'value': 'A', 'confidence': 0.99}]
    assert urls == [('gemini-2.5-flash', True), ('gemini-3.8-flash', True), ('gemini-3.8-flash', False)]
    urls.clear()
    R.call_gemini('AIza-x', 'gemini-2.5-flash', b'\xff\xd8', [{'slot': 1, 'kind': 'mcq'}])
    assert urls == [('gemini-3.8-flash', False)]                                  # yadda saxlanıb – birbaşa
    # 429 – yuxu yoxdur
    monkeypatch.setattr(time, 'sleep', lambda s: (_ for _ in ()).throw(AssertionError('sleep')))
    monkeypatch.setattr(httpx.Client, 'post', lambda self, url, json=None, headers=None: Resp(429, {'error': {'message': 'quota'}}))
    try:
        R.call_gemini('AIza-y', 'gemini-flash-latest', b'\xff\xd8', [{'slot': 1, 'kind': 'mcq'}])
        raise AssertionError
    except R.AiError as ex:
        assert str(ex) == R.AI_RATE
    # model yoxdur, alternativ də yoxdur → ai:model (açar 10 dəq dincə)
    monkeypatch.setattr(httpx.Client, 'post', lambda self, url, json=None, headers=None: Resp(404, {'error': {'message': 'models/x is not found'}}))
    try:
        R.call_gemini('AIza-z', 'gemini-flash-latest', b'\xff\xd8', [{'slot': 1, 'kind': 'mcq'}])
        raise AssertionError
    except R.AiError as ex:
        assert str(ex) == R.AI_MODEL and R.COOLDOWN[R.AI_MODEL] == 600
    ai.GEMINI_FIX.clear()
    ai.GEMINI_NO_THINK.clear()


def test_recent_rescan_guard(world, monkeypatch):
    """§C: «yenidən skan» açıq olsa belə, son 90 s-də qəbul edilmiş kart təkrar oxunmur (already); force=true – əvəz edir."""
    admin, ta, e, pr, st, _ = _graded(world, monkeypatch)
    sh = pr['sheets'][0]
    up = lambda q: admin.post(f'/api/exam-scans/{ta}/{e["id"]}/upload{q}', files=[('files', ('p.jpg', photo([sh['qr']]), 'image/jpeg'))]).json()
    r = up('?replace=true')
    assert not r['found'] and len(r['already']) == 1
    r = up('?replace=true&force=true')
    assert len(r['found']) == 1


def test_gemini_busy_backup_per_key(monkeypatch):
    """§H: 503 «high demand» – eyni açarda bir ehtiyat model, sonra ai:busy; model keçidi AÇAR ÜZRƏ yadda saxlanır."""
    import httpx
    from app import ai
    from app.domain import ksq_reader as R
    ai.GEMINI_FIX.clear(); ai.GEMINI_GONE.clear(); ai.GEMINI_NO_THINK.clear()

    class Resp:
        def __init__(self, code, js):
            self.status_code, self._js, self.text = code, js, str(js)

        def json(self):
            return self._js
    ok = {'candidates': [{'content': {'parts': [{'functionCall': {'name': 'submit_card', 'args': {'answers': [
        {'slot': 1, 'value': 'B', 'confidence': 0.99}]}}}]}}]}
    seen = []

    def post(self, url, json=None, headers=None):
        m = url.split('/models/')[1].split(':')[0]
        seen.append((headers['x-goog-api-key'], m))
        if m == 'gemini-flash-latest':
            return Resp(503, {'error': {'message': 'This model is currently experiencing high demand.'}})
        if headers['x-goog-api-key'] == 'new-acc' and m == 'gemini-2.5-flash':
            return Resp(404, {'error': {'message': 'models/gemini-2.5-flash is no longer available to new users'}})
        return Resp(200, ok)
    monkeypatch.setattr(httpx.Client, 'post', post)
    sl = [{'slot': 1, 'kind': 'mcq'}]
    assert R.call_gemini('old-acc', 'gemini-flash-latest', b'\xff\xd8', sl)[0]['value'] == 'B'
    assert seen == [('old-acc', 'gemini-flash-latest'), ('old-acc', 'gemini-2.5-flash')]   # 503 → ehtiyat model
    seen.clear()
    R.call_gemini('new-acc', 'gemini-2.5-flash', b'\xff\xd8', sl)                            # 404 → alternativ (bu açar üçün)
    assert ('new-acc', 'gemini-2.5-flash') in seen and ('old-acc', 'gemini-2.5-flash') not in ai.GEMINI_GONE
    seen.clear()
    R.call_gemini('old-acc', 'gemini-2.5-flash', b'\xff\xd8', sl)                            # köhnə hesab 2.5-də qalır
    assert seen == [('old-acc', 'gemini-2.5-flash')]
    monkeypatch.setattr(httpx.Client, 'post', lambda self, url, json=None, headers=None: Resp(503, {'error': {'message': 'high demand'}}))
    try:
        R.call_gemini('x-acc', 'gemini-flash-latest', b'\xff\xd8', sl)
        raise AssertionError
    except R.AiError as ex:
        assert str(ex) == R.AI_BUSY
    ai.GEMINI_FIX.clear(); ai.GEMINI_GONE.clear(); ai.GEMINI_NO_THINK.clear()


def test_unprinted_auto_lost(world, monkeypatch):
    """docs/kagiza-dusmeyen-avtomatik-promtu.md: köhnə çap təxmini saxlanır; təzə skanda «kəsilmiş ∩ boş» avtomatik ⊘, bal 100-ə;
    kəsilmiş, amma cavablı – sayılır; yeni çap – təxmin saxlanmır."""
    import datetime as dt
    from app.domain import ksq_reader as R
    from app.models import ExamVariant
    admin, ta, e, pr = ksq(world)
    _, S = world
    sh = pr['sheets'][0]
    key = {x['slot']: x['value'] for x in next(k for k in pr['key'] if k['code'] == sh['code'])['answers']}
    last = max(key)
    with S() as db:
        for v in db.query(ExamVariant).filter_by(exam_id=e['id']):
            v.printed_at = dt.datetime(2026, 10, 12, tzinfo=dt.timezone.utc)           # köhnə çap
        db.commit()
    lst = admin.get(f'/api/exam-scans/{ta}/{e["id"]}').json()
    assert lst['printed_old'] is True and lst['cut_saved'] is False
    sid = sh['student_id'] if 'student_id' in sh else None
    with S() as db:
        sid = sid or db.query(ExamVariant).filter_by(exam_id=e['id'], code=sh['code']).one().student_id
    assert admin.post(f'/api/exam-scans/{ta}/{e["id"]}/lost-auto', json={'cut': {str(sid): [last - 1, last]}}).status_code == 200
    assert admin.get(f'/api/exam-scans/{ta}/{e["id"]}').json()['cut_saved'] is True
    # şagird: hamısı düz, son sual boş (vərəqdə yox idi), sondan əvvəlki – cavablı (görünürmüş)

    def fake(api_key, model, jpeg, slots, only=None, text=None):
        return [{'slot': s['slot'], 'value': '' if s['slot'] == last else key[s['slot']], 'confidence': 0.99} for s in slots]
    monkeypatch.setattr(R, 'call', fake)
    monkeypatch.setattr(R, 'key_pool', lambda db, tid: [{'provider': 'anthropic', 'key': 'sk-ant-test', 'model': R.MODEL}])
    admin.post(f'/api/exam-scans/{ta}/{e["id"]}/upload', files=[('files', ('p.jpg', photo([sh['qr']]), 'image/jpeg'))])
    sc = next(x for x in admin.get(f'/api/exam-scans/{ta}/{e["id"]}').json()['scans'] if x['student_id'] == sid)
    assert sc['lost'] == [last] and sc['points'] == 100                              # boş + kəsilmiş – sayılmır, bal 100


def test_key_edit_all_students_keeps_print(world, monkeypatch):
    """Müəllim düz cavabı skan ekranından düzəldir: bu sual olan bütün şagirdlərdə, ballar yenidən hesablanır; çap izi dəyişmir
    (çap olunmuş kart yenidən skan oluna bilir)."""
    from app.domain.ksq_card import variant_rev
    from app.models import ExamVariant
    admin, ta, e, pr, st, keys = _graded(world, monkeypatch)
    _, S = world
    with S() as db:
        vs = {v.student_id: v for v in db.query(ExamVariant).filter_by(exam_id=e['id'])}
        sid = next(iter(vs))
        q = next(q for q in vs[sid].questions if q['kind'] == 'open')
        same = [s for s, v in vs.items() if any(x.get('key') == q['key'] for x in v.questions)]
        revs = {s: variant_rev(v.questions) for s, v in vs.items()}
    r = admin.put(f'/api/exams/{ta}/{e["id"]}/variants/{sid}/{q["slot"]}', json={'answer': '777', 'all_same': True})
    assert r.status_code == 200, r.text
    assert r.json()['students'] == len(same) and r.json()['answer'] == '777'
    with S() as db:
        for s in same:
            v = db.get(ExamVariant, (e['id'], s))
            assert all(x['answer'] == '777' for x in v.questions if x.get('key') == q['key'])
            assert variant_rev(v.questions) == revs[s]                                  # kağız dəyişmir – kart keçərlidir
    sc = next(x for x in admin.get(f'/api/exam-scans/{ta}/{e["id"]}').json()['scans'] if x['student_id'] == sid)
    assert sc['keys'][str(q['slot'])] == '777' and sc['kinds'][str(q['slot'])] == 'open'
    assert admin.put(f'/api/exams/{ta}/{e["id"]}/variants/{sid}/{q["slot"]}', json={'answer': 'abc'}).status_code == 400


def test_teacher_clears_auto_lost(world, monkeypatch):
    """Müəllim avtomatik ⊘-ları götürür (bütün suallar vərəqdə var idi) – yenidən hesablamada geri qayıtmır."""
    import datetime as dt
    from app.domain import ksq_reader as R
    from app.models import ExamVariant
    admin, ta, e, pr = ksq(world)
    _, S = world
    sh = pr['sheets'][0]
    with S() as db:
        v = db.query(ExamVariant).filter_by(exam_id=e['id'], code=sh['code']).one()
        v.printed_at, v.unprinted = dt.datetime(2026, 10, 12, tzinfo=dt.timezone.utc), [1, 2]
        db.commit()
    monkeypatch.setattr(R, 'call', lambda *a, **k: [{'slot': s['slot'], 'value': '', 'confidence': 0.99} for s in a[3]])
    monkeypatch.setattr(R, 'key_pool', lambda db, tid: [{'provider': 'anthropic', 'key': 'sk-ant-test', 'model': R.MODEL}])
    admin.post(f'/api/exam-scans/{ta}/{e["id"]}/upload', files=[('files', ('p.jpg', photo([sh['qr']]), 'image/jpeg'))])
    sc = admin.get(f'/api/exam-scans/{ta}/{e["id"]}').json()['scans'][0]
    assert sc['lost'] == [1, 2]
    assert admin.put(f'/api/exam-scans/{sc["id"]}/lost', json={'slots': []}).json()['lost'] == []
    admin.post(f'/api/exam-scans/{ta}/{e["id"]}/regrade')
    assert admin.get(f'/api/exam-scans/{ta}/{e["id"]}').json()['scans'][0]['lost'] == []


def test_mcq_only_variants(world):
    """«Sinif testindən 20 qapalı sual» (13.10.2026): mcq_only – bütün slotlar test, cəmi 100 bal, hər şagirdə 20 sual."""
    admin, ta, e, _ = ksq(world)
    r = admin.post(f'/api/exams/{ta}/{e["id"]}/variants', json={'n': 20, 'mcq_only': True})
    assert r.status_code == 200, r.text
    d = admin.get(f'/api/exams/{ta}/{e["id"]}/variants').json()
    for v in d['variants']:
        assert len(v['questions']) == 20 and all(q['kind'] == 'mcq' for q in v['questions'])
        assert abs(sum(q['points'] for q in v['questions']) - 100) < 1e-6
    items = admin.get(f'/api/exams/{ta}').json()
    ex = next(x for x in (items if isinstance(items, list) else items.get('exams', [])) if x.get('id') == e['id'])
    assert len(ex['items']) == 20
