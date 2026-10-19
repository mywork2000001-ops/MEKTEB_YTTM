"""Ümumi A4 cavab vərəqəsi (docs/yazili-sinaq-ve-skan-duymesi-promtu.md §B): oxuyucuda `score` slotu (müəllim balı dairələri),
boş forma (QR-də yalnız imtahan), sual kitabçası."""
from app.domain import ksq_reader as R
from app.domain.ksq_card import blank_qr, parse_qr

from .test_api_portal import mk_task, setup
from .test_ksq_scan import photo

SLOTS = [{'slot': 1, 'kind': 'mcq'}, {'slot': 2, 'kind': 'mcq'}, {'slot': 3, 'kind': 'open'}, {'slot': 4, 'kind': 'score'}, {'slot': 5, 'kind': 'score'}]


def test_reader_score_slots_clean_and_plausible():
    out = R._clean({'answers': [
        {'slot': 1, 'value': 'b', 'confidence': 0.99},
        {'slot': 3, 'value': '', 'cells': ['2', ',', '5', '', '', '', '', ''], 'confidence': 0.9},
        {'slot': 4, 'value': '3/4', 'confidence': 0.95},
        {'slot': 5, 'value': '0,5', 'confidence': 0.95}]}, SLOTS)
    by = {a['slot']: a for a in out}
    assert by[1]['value'] == 'B' and by[3]['value'] == '2,5'
    assert by[4]['value'] == '3/4' and by[5]['value'] == '1/2'            # 0,5 → ½ (dairə)
    bad = R._clean({'answers': [{'slot': 4, 'value': '7', 'confidence': 0.99}, {'slot': 5, 'value': '*', 'confidence': 1}]}, SLOTS)
    assert bad[0]['value'] == '' and bad[0]['confidence'] < R.LOW             # tanınmayan bal – sarı xana
    assert bad[1]['value'] == '*' and bad[1]['confidence'] < R.LOW            # iki dairə qaralanıb – sarı
    assert R.plausible('score', '') and R.plausible('score', '1/4') and not R.plausible('score', '2')


def test_reader_prompt_and_columns_exclude_score():
    t = R._instructions(SLOTS)
    assert 'Müəllim balı' in t and '0 · ¼ · ½ · ¾ · 1' in t
    assert 'Açıq suallar 3–3' in t                                              # score slotları açıq xana sayılmır
    assert sorted(s for c in R._columns(SLOTS) for s in c) == [1, 2, 3]


def test_blank_qr_signed_and_tamper_rejected():
    q = blank_qr(42)
    assert parse_qr(q) == {'exam_id': 42, 'student_id': 0, 'code': 'BLANK'}
    assert parse_qr(q.replace('|42|', '|43|')) is None


def test_blank_form_print_and_scan_pick_student(world):
    admin, ta, cid, st, ids = setup(world)
    _, S = world
    from .test_paper_exams import _bank
    fid = _bank(S)
    e = admin.post(f'/api/paper-exams/{ta}', json={'file_ids': [fid], 'n': 10, 'date': '2026-10-05', 'variant_mode': 'same'}).json()['exam']
    bl = admin.get(f'/api/exams/{ta}/{e["id"]}/variants/print', params={'blank': True}).json()
    assert len(bl['sheets']) == 1 and bl['sheets'][0]['student_id'] == 0 and bl['sheets'][0]['code'] == 'BLANK'
    assert parse_qr(bl['sheets'][0]['qr'])['student_id'] == 0 and bl['exam']['title']
    # boş forma şəkli: ümumi skan imtahanı tapır, şagirdi seçmək istəyir
    d = admin.post('/api/scans/any', files=[('files', ('b.jpg', photo([bl['sheets'][0]['qr']]), 'image/jpeg'))]).json()
    assert d['found'] == [] and d['blank'][0]['exam_id'] == e['id'] and d['unmatched'] == 0
    # şagird seçilir (əl ilə) → qəbul
    sid = st[1]['id']
    m = admin.post('/api/scans/any/manual', data={'exam_id': e['id'], 'student_id': sid},
                   files={'file': ('b.jpg', photo([bl['sheets'][0]['qr']]), 'image/jpeg')})
    assert m.status_code == 200 and m.json()['found'][0]['student_id'] == sid
    # «hər şagirdə fərqli» imtahan üçün boş forma olmaz
    e2 = admin.post(f'/api/paper-exams/{ta}', json={'file_ids': [fid], 'n': 10, 'date': '2026-10-06', 'variant_mode': 'different'}).json()['exam']
    assert admin.get(f'/api/exams/{ta}/{e2["id"]}/variants/print', params={'blank': True}).status_code == 409


def test_print_has_exam_title_and_label(world):
    admin, ta, cid, st, ids = setup(world)
    t = mk_task(admin, ta, ids).json()
    e = admin.post(f'/api/paper-exams/{ta}', json={'task_id': t['id'], 'date': '2026-10-05', 'title': 'Sınaq-3'}).json()['exam']
    pr = admin.get(f'/api/exams/{ta}/{e["id"]}/variants/print').json()
    assert pr['exam']['title'] == 'Sınaq-3' and pr['exam']['label'] == f'{e["kind"]}-{e["no"]}'
