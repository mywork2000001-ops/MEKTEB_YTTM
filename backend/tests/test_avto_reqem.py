"""Avtomatik şablon (scripts/avto_reqem.py): kvadrat tənlik, Bezu, kəsr, faiz, hərəkət, şəkil, səhv açar, birmənasızlıq, determinizm."""
import copy
import json
from fractions import Fraction
from pathlib import Path

from scripts import avto_reqem as ar
from scripts import reqem_variantlari as rv

NUMUNE = Path(__file__).resolve().parent.parent / 'scripts' / 'examples' / 'reqem_numune.json'
N = 12


def tr(az, ru, en):
    return {'az': az, 'ru': ru, 'en': en}


def mcq_opts(*vals):
    return [tr(v, v, v) for v in vals]


QUAD = dict(kind='open', answer='1;4', text=tr(
    '$x^2 - 5x + 4 = 0$ tənliyinin köklərini artan sırada ";" ilə yazın.',
    'Запишите корни уравнения $x^2 - 5x + 4 = 0$ по возрастанию через ";".',
    'Write the roots of $x^2 - 5x + 4 = 0$ in increasing order, separated by ";".'))
BEZOUT = dict(kind='open', answer='11', text=tr(
    '$P(x) = x^3 + 2x^2 - 3x + 1$ çoxhədlisinin $x - 2$ binomuna bölünməsindən alınan qalığı tapın.',
    'Найдите остаток от деления многочлена $P(x) = x^3 + 2x^2 - 3x + 1$ на двучлен $x - 2$.',
    'Find the remainder when $P(x) = x^3 + 2x^2 - 3x + 1$ is divided by $x - 2$.'))
FRACTION = dict(kind='open', answer='17/12', text=tr(
    '$\\frac{2}{3} + \\frac{3}{4}$ ifadəsini hesablayın.',
    'Вычислите $\\frac{2}{3} + \\frac{3}{4}$.',
    'Calculate $\\frac{2}{3} + \\frac{3}{4}$.'))
PERCENT = dict(kind='open', answer='180', text=tr(
    'Malın qiyməti 150 manat idi. Qiymət 20% artdı. Yeni qiymət neçə manatdır?',
    'Цена товара была 150 манатов. Цена выросла на 20%. Сколько манатов стоит товар теперь?',
    'The price of an item was 150 manats. The price rose by 20%. What is the new price in manats?'))
MOTION = dict(kind='mcq', correct=1,
              options=mcq_opts('$120$ km', '$180$ km', '$63$ km', '$20$ km'),
              text=tr('Avtomobil 60 km/saat sürətlə 3 saat getdi. Neçə km yol getdi?',
                      'Автомобиль ехал 3 часа со скоростью 60 км/ч. Сколько километров он проехал?',
                      'A car travelled for 3 hours at 60 km/h. How many kilometres did it cover?'))
PICTURE = dict(kind='open', answer='5', image='data:image/png;base64,AAAA', text=tr(
    'Şəkildə $x$-in qiymətini tapın: $AB = 12$, $BC = 7$.', 'Найдите $x$ на рисунке: $AB = 12$, $BC = 7$.',
    'Find $x$ in the figure: $AB = 12$, $BC = 7$.'))
WRONG_KEY = dict(BEZOUT, answer='12')
AMBIG = dict(kind='open', answer='4', text=tr(
    'Sinifdə 2 oğlan və 2 qız var. Sinifdə neçə şagird var?', 'В классе 2 мальчика и 2 девочки. Сколько всего учеников?',
    'There are 2 boys and 2 girls in a class. How many students are there?'))


def conv(*qs, n=N):
    return ar.convert(list(qs), n)


def studs(n=N):
    return [(str(i), f'Şagird {i}') for i in range(1, n + 1)]


def test_kvadrat_tenlik():
    (t,), (r,) = conv(QUAD)
    assert r['method'] == 'sympy', r
    assert not t.get('fixed')
    built = rv.build({'code': 'Q', 'questions': [t]}, studs(25), 'Q')
    assert len({tuple(sorted(st['questions'][0]['params'].items())) for st in built}) == 25
    for st in built:
        q = st['questions'][0]
        p = {k: int(v) for k, v in q['params'].items()}
        x1, x2 = sorted((p['r1'], p['r2']))
        assert q['answer'] == f'{x1};{x2}'
        for lg in ('az', 'ru', 'en'):          # əmsallar Viyetə uyğun, eyni ədəd üç dildə
            assert f'x^2 - {x1 + x2}x + {x1 * x2} = 0' in q['text'][lg]


def test_bezu_qaliq():
    (t,), (r,) = conv(BEZOUT)
    assert r['method'] == 'sympy' and 'Bezu' in r['detail']
    built = rv.build({'code': 'B', 'questions': [t]}, studs(), 'B')
    sets = {tuple(sorted(st['questions'][0]['params'].items())) for st in built}
    assert len(sets) == N
    for st in built:
        p = {k: int(v) for k, v in st['questions'][0]['params'].items()}
        k_ = p['n3']
        assert st['questions'][0]['answer'] == str(k_ ** 3 + p['n1'] * k_ ** 2 - p['n2'] * k_ + 1)


def test_kesr_hesabi():
    (t,), (r,) = conv(FRACTION)
    assert r['method'] == 'sympy', r
    built = ar.clean_built(rv.build({'code': 'F', 'questions': [t]}, studs(), 'F'))
    for st in built:
        q = st['questions'][0]
        p = {k: int(v) for k, v in q['params'].items()}
        want = Fraction(p['n1'], p['n2']) + Fraction(p['n3'], p['n4'])
        assert q['answer'] == (str(want.numerator) if want.denominator == 1 else f'{want.numerator}/{want.denominator}')
        assert rv.CARD_RE.match(q['answer'])
        assert '\\frac' in q['text']['ru']


def test_faiz_meselesi():
    (t,), (r,) = conv(PERCENT)
    assert r['method'] == 'düstur', r
    built = ar.clean_built(rv.build({'code': 'P', 'questions': [t]}, studs(), 'P'))
    for st in built:
        q = st['questions'][0]
        p = {k: int(v) for k, v in q['params'].items()}
        assert Fraction(q['answer'].replace(',', '.')) == Fraction(p['n1']) * (1 + Fraction(p['n2'], 100))
        for lg, tx in q['text'].items():       # eyni ədəd üç dildə də
            assert str(p['n1']) in tx and f"{p['n2']}%" in tx, (lg, tx)
        assert 10 <= p['n2'] <= 99 and 100 <= p['n1'] <= 999


def test_hereket_mcq_distraktorlar():
    (t,), (r,) = conv(MOTION)
    assert r['method'] == 'düstur', r
    built = rv.build({'code': 'M', 'questions': [t]}, studs(), 'M')
    for st in built:
        q = st['questions'][0]
        p = {k: int(v) for k, v in q['params'].items()}
        shown = [o['az'] for o in q['options']]
        assert len(set(shown)) == 4
        assert shown[q['correct']] == f"${p['n1'] * p['n2']}$ km"
        assert f"${p['n1'] * p['n2'] - p['n1']}$ km" in shown      # mənbə distraktoru «cavab − n1» əlaqəsi saxlandı


def test_sekilli_sual_fixed():
    (t,), (r,) = conv(PICTURE)
    assert r['method'] == 'fixed' and 'şəkil' in r['detail'] and t['fixed']


def test_sehv_acar_fixed():
    (t,), (r,) = conv(WRONG_KEY)
    assert r['method'] == 'fixed' and t['fixed']


def test_birmenali_olmayan_dustur_fixed():
    (t,), (r,) = conv(AMBIG)
    assert r['method'] == 'fixed' and 'birqiymətli' in r['detail']


def test_determinizm_ve_butov_cixis(tmp_path):
    qs = [QUAD, BEZOUT, FRACTION, PERCENT, MOTION, PICTURE, WRONG_KEY, AMBIG]
    t1, r1 = ar.convert(copy.deepcopy(qs), N)
    t2, r2 = ar.convert(copy.deepcopy(qs), N)
    assert t1 == t2 and r1 == r2
    tpl = {'code': 'D', 'title': 'D', 'questions': t1}
    b1 = rv.build(tpl, studs(), 'D')
    assert b1 == rv.build(copy.deepcopy(tpl), studs(), 'D')
    f = tmp_path / 'q.json'
    f.write_text(json.dumps(qs, ensure_ascii=False), encoding='utf-8')
    assert ar.main([str(f), '--n', '5', '--out', str(tmp_path / 'out')]) == 0
    out = tmp_path / 'out' / 'q'
    assert (out / 'avto_sablon.json').exists() and (out / 'hesabat.txt').exists() and (out / 'variants.json').exists()
    # variants.json yenidən giriş kimi oxunur
    again = ar.load_questions(out / 'variants.json')
    assert len(again) == len(qs)


def test_numune_avtomatik():
    tpl = json.loads(NUMUNE.read_text(encoding='utf-8'))
    plain = ar.template_to_questions(tpl)
    tq, rep = ar.convert(plain, 25)
    auto = [r for r in rep if r['method'] != 'fixed']
    assert len(auto) >= 3, ar.report_lines(rep)
    ar.build_safe(plain, {'code': 'N', 'title': 'N', 'questions': tq}, studs(25), 'N', rep)
