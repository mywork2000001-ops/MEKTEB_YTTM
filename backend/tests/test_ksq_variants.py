"""KSQ/BSQ kağız variantları (docs/ksq-bsq-kagiz-promtu.md): 30 slot / 100 bal, ciddi təkrarsızlıq, şablonların düzgünlüyü, API."""
import ast
import datetime as dt
import math
import random
from fractions import Fraction

import pytest

from app.domain import templates as T
from app.domain.ksq_variants import Cand, Shortage, card_answer, fairness, generate, slots
from app.models import BankFile, BankQuestion, BankSource, PlanLesson, TeachingAssignment


def test_slot_plan():
    s = slots()
    assert len(s) == 30 and sum(x['points'] for x in s) == 100
    assert sum(x['kind'] == 'open' for x in s) == 21                          # 70% açıq


def test_card_answer():
    assert card_answer('3/7') == '3/7' and card_answer('2.5') == '2,5' and card_answer('x=3|3') == '3'
    assert card_answer('-12') == '-12' and card_answer('1;4') == '1;4'
    assert card_answer('√2') is None and card_answer('x>3') is None and card_answer('123456789') is None


def _parse(x: str) -> Fraction:
    return Fraction(x.replace(',', '.')) if '/' not in x else Fraction(*map(int, x.split('/')))


# hər şablonun cavabı müstəqil (başqa yolla) hesablanır — 100 təsadüfi parametr
CHECK = {
    'pct': lambda p: Fraction(p[1] * p[0], 100),
    'pct_back': lambda p: p[1],
    'lin': lambda p: p[1],
    'lin2': lambda p: Fraction(p[3] - p[1], p[0] - p[2]),
    'gcd': lambda p: math.gcd(*p),
    'lcm': lambda p: math.lcm(*p),
    'divcount': lambda p: sum(p[0] % k == 0 for k in range(1, p[0] + 1)),
    'frac_add': lambda p: Fraction(p[0], p[1]) + Fraction(p[2], p[3]),
    'frac_mul': lambda p: Fraction(p[0], p[1]) * Fraction(p[2], p[3]),
    'dec': lambda p: Fraction(str(p[0])) * Fraction(str(p[1])),
    'ratio': lambda p: Fraction(max(p[0], p[1]) * (p[0] + p[1]) * p[2], p[0] + p[1]),
    'ap': lambda p: p[0] + (p[2] - 1) * p[1],
    'ap_sum': lambda p: sum(p[0] + k * p[1] for k in range(p[2])),
    'quad_sum': lambda p: p[0] * p[1],
    'quad_big': lambda p: max(p[1], p[2]),
    'sys': lambda p: p[0],
    'angle_adj': lambda p: Fraction(180 * max(p), sum(p)),
    'rect': lambda p: p[0] * p[1],
    'pyth': lambda p: Fraction(math.isqrt((p[0] * p[2]) ** 2 + (p[1] * p[2]) ** 2)),
    'power': lambda p: p[0] ** p[3],
    'sets': lambda p: len(set(range(p[0])) | set(range(p[0] - p[2], p[0] - p[2] + p[1]))),        # sayma ilə: A və B kəsişməsi p[2]
    'sets_word': lambda p: p[0] - len(set(range(p[1])) | set(range(p[1] - p[3], p[1] - p[3] + p[2]))),
    'part': lambda p: Fraction(p[2]) / p[1] * p[0],
    'part_back': lambda p: p[2],
    'remainder': lambda p: p[0] - (p[0] // p[1]) * p[1],
    'segment': lambda p: (p[0] + p[1]) - p[0],
}


def test_template_topic_audit():
    """Audit 13.10: X-b KSQ-1 mövzularına aid olmayan şablonlar (silsilə, tənliklər sistemi) düşmür; çoxluq/hissə/qalıq şablonları var."""
    from app.bank.match import stems
    ids = lambda t: {x.id for x in T.matching(stems(t))}      # noqa: E731
    assert not ids('Ədədin bölünəni və böləni. Tam və qalıqlı bölmə') & {'ap', 'ap_sum', 'sys'}
    assert 'remainder' in ids('Ədədin bölünəni və böləni. Tam və qalıqlı bölmə')
    assert not ids('Natural ədədlər və onların onluq say sistemində yazılışı') & {'sys', 'dec'}
    assert {'sets', 'sets_word'} <= ids('Çoxluq anlayışı. Çoxluqların birləşməsi')
    assert {'part', 'part_back'} <= ids('Ədədin hissəsinin və hissəsinə görə ədədin tapılması')
    assert 'sys' in ids('Xətti tənliklər sistemi') and 'ap' in ids('Ədədi silsilə')
    assert not ids('Nöqtə və düz xətt. Parça, şüa') & {'lin', 'lin2'} and 'segment' in ids('Nöqtə və düz xətt. Parça, şüa')
    assert 'divcount' not in ids('Faizə aid məsələlər: bank faizi (sadə və mürəkkəb faiz)')
    assert not ids('Nisbət. Tənasüb. Ədədin verilmiş nisbətdə bölünməsi') & {'gcd', 'lcm'}


@pytest.mark.parametrize('t', T.TEMPLATES, ids=lambda t: t.id)
def test_template_answers(t):
    assert t.id in CHECK, 'yeni şablonun müstəqil yoxlaması yazılmalıdır'
    rng = random.Random(1)
    keys = set()
    for _ in range(100):
        q = T.instance(t, rng)
        params = ast.literal_eval(q['key'].split(':', 2)[2])
        assert card_answer(q['answer']) == q['answer'], (t.id, q['answer'])      # kart üçün yararlı
        assert _parse(q['answer']) == Fraction(CHECK[t.id](params)), (t.id, params, q['answer'])
        assert all(q['text'][k] for k in ('az', 'ru', 'en'))
        keys.add(q['key'])
    assert len(keys) >= 30, f'{t.id}: 100 cəhddə yalnız {len(keys)} fərqli variant'


def _cands(n_per: int) -> list[Cand]:
    out = []
    for kind, levels in (('mcq', ('asan', 'orta')), ('open', ('asan', 'orta', 'çətin'))):
        for lvl in levels:
            for i in range(n_per):
                for ti in range(3):
                    key = f'b:{kind}{lvl}{i}-{ti}'
                    out.append(Cand(key, kind, lvl, ti, {'kind': kind, 'text': {'az': f'Sual {key}'}, 'answer': '5',
                                                         'options': ['1', '2'] if kind == 'mcq' else None, 'correct': 0}))
    return out


def test_generate_strictly_unique():
    topics = [('Mövzu A', None), ('Mövzu B', None), ('Mövzu C', None)]
    students = list(range(1, 26))
    hist = {1: {'b:opençətin0-0', 'b:mcqasan3-1'}}
    res = generate(students, topics, _cands(90), hist, seed=7)
    keys = [q['key'] for v in res.values() for q in v]
    assert len(keys) == 25 * 30 and len(set(keys)) == len(keys)           # sıfır təkrar
    assert not ({q['key'] for q in res[1]} & hist[1])                     # tarixçə istisna
    for v in res.values():
        assert sum(q['points'] for q in v) == 100 and [q['slot'] for q in v] == list(range(1, 31))
    rep = fairness(res)
    assert rep['unique'] == rep['questions'] == 750 and rep['open_pct'] == 70.0


def test_generate_shortage_is_strict(monkeypatch):
    # mövzuya uyğun şablon yoxdursa ümumi şablonlar işləyir; şablon ümumiyyətlə yoxdursa – səssiz təkrar yox, Shortage
    monkeypatch.setattr(T, 'TEMPLATES', [])
    with pytest.raises(Shortage) as e:
        generate(list(range(1, 26)), [('Heç nə', None)], _cands(2), {}, seed=1)
    assert e.value.items and all(x['missing'] > 0 for x in e.value.items)


def test_templates_fill_gaps():
    # bankda açıq sual yoxdur, amma mövzu «Faiz» — şablonlar doldurur, yenə təkrarsız
    only_mcq = [c for c in _cands(40) if c.kind == 'mcq']
    res = generate(list(range(1, 11)), [('Faiz', None), ('Xətti tənliklər', None)], only_mcq, {}, seed=3, templates=True)
    keys = [q['key'] for v in res.values() for q in v]
    assert len(set(keys)) == len(keys) == 300
    assert sum(q.get('template') is not None for v in res.values() for q in v) == 210


def test_api_variants(world):
    from .test_api_portal import setup
    as_, S = world
    admin, ta, cid, st, _ = setup(world)
    with S() as db:
        db.add(BankSource(key='p003', label='P0010'))
        db.flush()
        f = BankFile(source_key='p003', lesson='t/faiz.html', label='Nisbət. Tənasüb. Faiz — Faiz', url='http://x', kind='movzu', question_count=210)
        db.add(f)
        db.flush()
        for i in range(210):
            kind = 'mcq' if i < 60 else 'open'
            db.add(BankQuestion(file_id=f.id, n=i + 1, kind=kind, text={'az': f'Faiz sualı {i}'}, content_hash=f'h{i}',
                                options=[{'az': '1'}, {'az': '2'}] if kind == 'mcq' else None, correct=0 if kind == 'mcq' else None,
                                answer=None if kind == 'mcq' else str(i), diff_auto=['asan', 'orta', 'çətin'][i % 3] if kind == 'open' else ['asan', 'orta'][i % 2]))
        pl = db.query(PlanLesson).filter_by(assignment_id=ta, seq=3).one()
        pl.topic = 'Faiz'
        db.add(PlanLesson(assignment_id=ta, seq=9, semester=1, assessment_type='KSQ', exam_no=1, topic='KSQ-1', date=dt.date(2026, 10, 20)))
        db.commit()
    e = admin.post(f'/api/exams/{ta}', json={'kind': 'KSQ', 'no': 1, 'semester': 1, 'date': '2026-10-20', 'max_points': 20}).json()
    r = admin.post(f'/api/exams/{ta}/{e["id"]}/variants')
    assert r.status_code == 200, r.text
    d = r.json()
    assert len(d['variants']) == 3 and d['exam']['max_points'] == 100 and len(d['exam']['items']) == 30
    keys = [q['key'] for v in d['variants'] for q in v['questions']]
    assert len(keys) == 90 and len(set(keys)) == 90
    assert d['report']['open_pct'] == 70.0
    assert admin.get(f'/api/exams/{ta}/{e["id"]}/variants').json()['variants'][0]['code'] == 'KSQ1-01'
    # çap: hər şagirdə 30 sual, imzalı QR, cavab vərəqdə yoxdur, açarda var
    from app.domain.ksq_card import parse_qr
    pr = admin.get(f'/api/exams/{ta}/{e["id"]}/variants/print').json()
    sh = pr['sheets'][0]
    assert len(pr['sheets']) == 3 and len(sh['questions']) == 30 and [q['slot'] for q in sh['questions']] == list(range(1, 31))
    assert all('answer' not in q and 'correct' not in q for q in sh['questions'])
    info = parse_qr(sh['qr'])
    assert info == {'exam_id': e['id'], 'student_id': sh['student_id'], 'code': sh['code']}
    assert parse_qr(sh['qr'][:-1] + ('A' if sh['qr'][-1] != 'A' else 'B')) is None          # saxta imza
    assert parse_qr(sh['qr'].replace(sh['code'], 'KSQ1-99')) is None
    k = pr['key'][0]['answers']
    assert len(k) == 30 and all(x['value'] for x in k) and k[0]['value'] in 'ABCDE'
    assert sum(x['points'] for x in k) == 100
    # nəticə yazılıbsa — yenidən yaratmaq olmaz
    admin.put(f'/api/exams/{ta}/{e["id"]}/scores', json=[{'student_id': st[0]['id'], 'points': 50}])
    assert admin.post(f'/api/exams/{ta}/{e["id"]}/variants').status_code == 409


def test_fill_task_translations(world):
    """Bankda sonradan yaranan rus tərcüməsi verilmiş testin sual surətinə əlavə olunur (açar toxunulmur)."""
    from app.bank.sync import fill_task_translations
    from app.models import OnlineTask
    from .test_api_portal import mk_task, setup
    as_, S = world
    admin, ta, cid, st, ids = setup(world)
    tid = mk_task(admin, ta, ids).json()['id']
    with S() as db:
        q = db.get(BankQuestion, ids[0])
        q.text = {'az': '2+2=?', 'ru': '2+2=? (ru)'}
        q.options = [{'az': '3', 'ru': 'три'}, {'az': '4', 'ru': 'четыре'}]
        db.commit()
        assert fill_task_translations(db) == 1
        db.commit()
        t = db.get(OnlineTask, tid)
        q0 = next(x for x in t.questions if x['bank_id'] == ids[0])
        assert q0['text']['ru'] == '2+2=? (ru)' and q0['options'][1]['ru'] == 'четыре' and q0['correct'] == 1
        assert fill_task_translations(db) == 0                       # ikinci dəfə — dəyişiklik yoxdur


def test_slots_any_count():
    """Müəllim sual sayını seçir (10–30): cəmi həmişə 100 bal, test/açıq payı saxlanır, sərhədlər kəsilir."""
    for n in range(10, 31):
        s = slots(n)
        assert len(s) == n and abs(sum(x['points'] for x in s) - 100) < 1e-9 and all(x['points'] >= 0.5 for x in s)
        assert 0.2 <= sum(x['kind'] == 'mcq' for x in s) / n <= 0.4
    assert len(slots(5)) == 10 and len(slots(99)) == 30


def test_cross_class_reuse_cap():
    """Başqa sinfin eyni imtahanı ilə təkrar: əvvəl təzə suallar, çatmasa ən çox 20%."""
    rng = random.Random(1)
    cands = [Cand(f'b{i}', k, lvl, 0, {'text': {'az': f'q{i}'}, 'kind': k}) for i, (k, lvl) in
             enumerate([(k, l) for k in ('mcq', 'open') for l in ('asan', 'orta', 'çətin') for _ in range(30)])]
    others = {c.key for c in cands[::3]}                               # üçdə biri başqa sinifdə işlənib
    res = generate([1, 2], [('Faiz', None)], cands, {}, seed=3, n=10, others=others)
    keys = [q['key'] for v in res.values() for q in v]
    assert len(keys) == 20 and len(set(keys)) == 20
    assert sum(k in others for k in keys) <= 4                         # 20% × 20
    _ = rng


def test_mcq_shortage_filled_by_templates():
    """İstifadəçi halı (12.10.2026): 25 şagird, 20 sual, bankda test sualı az → test slotları şablondan (A–E), çatışmazlıq yoxdur."""
    cands = [Cand(f'b{i}', 'mcq', 'asan', 0, {'text': {'az': f'q{i}'}, 'kind': 'mcq', 'options': [{'az': '1'}, {'az': '2'}], 'correct': 0})
             for i in range(8)]
    res = generate(list(range(25)), [('Faiz', None)], cands, {}, seed=5, n=20, templates=True)
    qs = [q for v in res.values() for q in v]
    assert len(qs) == 500 and len({q['key'] for q in qs}) == 500
    mcq = [q for q in qs if q['kind'] == 'mcq']
    tpl = [q for q in mcq if q.get('template')]
    assert len(mcq) == 25 * sum(s['kind'] == 'mcq' for s in slots(20)) and tpl
    for q in tpl:
        opts = [o['az'] for o in q['options']]
        assert len(opts) == 5 and len(set(opts)) == 5 and 0 <= q['correct'] < 5


def test_distractors_distinct():
    rng = random.Random(2)
    for ans in ('12', '-4', '2,5', '3/7', '0', '1;4'):
        d = T.distractors(ans, rng)
        assert d and len(set(d)) == 4 and ans not in d



def test_bank_only_by_default():
    """Qayda (13.10): X–XI KSQ sualları yalnız layihə (P0010) fayllarından – şablon standart söndürülü; çatmasa Shortage."""
    cands = [Cand(f'b{i}', 'mcq', 'asan', 0, {'text': {'az': f'q{i}'}, 'kind': 'mcq', 'options': [{'az': '1'}, {'az': '2'}], 'correct': 0})
             for i in range(8)]
    with pytest.raises(Shortage):
        generate(list(range(25)), [('Faiz', None)], cands, {}, seed=5, n=20)


def test_auto_minimal_share_no_templates():
    """Bank kiçikdir: sistem özü ən az təkrarı seçir (k = 2, 3, …); şablon sualı yoxdur; şagirdin öz variantında təkrar yoxdur."""
    from collections import Counter
    from app.domain.ksq_variants import generate_auto
    cands = []
    for i in range(40):
        lvl = ['asan', 'orta', 'çətin'][i % 3]
        cands.append(Cand(f'm{i}', 'mcq', ['asan', 'orta'][i % 2], 0, {'text': {'az': f'm{i}'}, 'kind': 'mcq', 'options': [{'az': '1'}, {'az': '2'}], 'correct': 0}))
        cands.append(Cand(f'o{i}', 'open', lvl, 0, {'text': {'az': f'o{i}'}, 'kind': 'open', 'answer': str(i)}))
    res, k = generate_auto(list(range(12)), [('Faiz', None)], cands, {}, seed=1, n=10)
    qs = [q for v in res.values() for q in v]
    use = Counter(q['key'] for q in qs)
    assert k > 1 and max(use.values()) <= k and not any(q.get('template') for q in qs)
    assert all(len({q['key'] for q in v}) == 10 for v in res.values())
    with pytest.raises(Shortage):                                     # bir şagirdə də çatmırsa – Shortage (sual sayını azaltmaq)
        generate_auto([1], [('Faiz', None)], cands[:6], {}, seed=1, n=30)


def test_shared_file_goes_to_best_topic(world):
    """Fayl iki mövzuda: sualları faylın birinci durduğu mövzuya yazılır (canlı audit 13.10: «Qalıqlı bölmə» 0 göstərirdi)."""
    from app.domain.ksq_variants import bank_candidates
    _, S = world
    with S() as db:
        db.add(BankSource(key='p003', label='P0010')); db.flush()
        a = BankFile(source_key='p003', lesson='a', label='Natural — Toplama', url='u', kind='movzu', question_count=2)
        b = BankFile(source_key='p003', lesson='b', label='Natural — Qalıqlı bölmə', url='u', kind='movzu', question_count=2)
        db.add_all([a, b]); db.flush()
        for f, h in ((a, 'a'), (b, 'b')):
            for i in range(2):
                db.add(BankQuestion(file_id=f.id, n=i + 1, kind='mcq', text={'az': f'{h}{i}'}, content_hash=f'{h}{i}', options=[{'az': '1'}, {'az': '2'}], correct=0))
        db.commit()
        cs = bank_candidates(db, [('Toplama', None), ('Qalıqlı bölmə', None)], 'p003', {0: [a.id, b.id], 1: [b.id]})
        tops = {c.q['lesson']: c.topic for c in cs if c.kind == 'mcq'}
        assert tops == {'Natural — Toplama': 0, 'Natural — Qalıqlı bölmə': 1}
        qb = next(c for c in cs if c.q['lesson'] == 'Natural — Qalıqlı bölmə')
        assert qb.on(0) and qb.on(1)                                       # ortaq fayl – hər iki mövzuda sayılır və istifadə olunur
