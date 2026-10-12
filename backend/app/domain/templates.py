"""Parametrli sual şablonları (docs/ksq-bsq-kagiz-promtu.md §2, §7) — hovuz çatmayanda hər şagirdə fərqli ədədlərlə sual.

Hər şablon: açar sözlər (plan mövzusu ilə uyğunluq — `bank.match.stems` kökləri), səviyyə, parametr generatoru və
cavab. Cavab həmişə kart üçün yararlıdır (tam ədəd, onluq kəsr «2,5», adi kəsr «3/7» — ixtisar olunmuş).
`instance(t, rng)` — {key, kind:'open', text{az,ru,en}, answer, level, template}; `key` = şablon + parametrlər (unikallıq).
Hər şablonun cavabı testdə müstəqil yoxlanılır (tests/test_ksq_variants.py — 100 təsadüfi parametr)."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from fractions import Fraction
from typing import Callable


def fmt(x) -> str:
    """Kart formatı: tam → «12», onluq → «2,5», kəsr → «3/7»."""
    if isinstance(x, Fraction):
        if x.denominator == 1:
            return str(x.numerator)
        d = x.denominator
        while d % 2 == 0:
            d //= 2
        while d % 5 == 0:
            d //= 5
        if d == 1 and len(str(float(x))) <= 7:
            return str(float(x)).replace('.', ',')
        return f'{x.numerator}/{x.denominator}'
    if isinstance(x, float):
        return (str(int(x)) if x == int(x) else str(x)).replace('.', ',')
    return str(x)


@dataclass(frozen=True)
class Template:
    id: str
    keys: tuple[str, ...]          # mövzu kökləri (ilk 5 hərf, «ə→e» normallaşdırılmış)
    level: str                     # asan | orta | çətin
    make: Callable[[random.Random], tuple[dict, object, tuple]]   # (mətn {az,ru,en}, cavab, parametrlər)
    need: tuple[str, ...] = ()     # bunların HAMISI da mövzuda olmalıdır (məs. «sistem» + «tənlik»; «onluq say sistemi» – yox)


def _t(az, ru, en):
    return {'az': az, 'ru': ru, 'en': en}


def _sets(r):
    a, b = r.randint(8, 30), r.randint(8, 30)
    c = r.randint(1, min(a, b) - 1)
    return (_t(f'$A$ çoxluğunun ${a}$, $B$ çoxluğunun ${b}$ elementi var, $A \\cap B$ çoxluğunun isə ${c}$ elementi var. $A \\cup B$ çoxluğunun neçə elementi var?',
               f'Во множестве $A$ ${a}$ элементов, в $B$ — ${b}$, в $A \\cap B$ — ${c}$. Сколько элементов в $A \\cup B$?',
               f'Set $A$ has ${a}$ elements, $B$ has ${b}$, and $A \\cap B$ has ${c}$. How many elements are in $A \\cup B$?'), a + b - c, (a, b, c))


def _sets_word(r):
    n = r.randint(25, 40)
    x, y = r.randint(10, n - 8), r.randint(8, n - 8)
    z = r.randint(max(1, x + y - n + 1), min(x, y) - 1)
    return (_t(f'Sinifdə ${n}$ şagird var. ${x}$ şagird riyaziyyat, ${y}$ şagird fizika dərnəyinə gedir, ${z}$ şagird hər ikisinə. Neçə şagird heç bir dərnəyə getmir?',
               f'В классе ${n}$ учеников. ${x}$ ходят в кружок математики, ${y}$ — физики, ${z}$ — в оба. Сколько учеников не ходят ни в один кружок?',
               f'A class has ${n}$ students. ${x}$ attend the maths club, ${y}$ the physics club, ${z}$ both. How many attend neither?'), n - (x + y - z), (n, x, y, z))


def _part(r):
    q = r.choice([3, 4, 5, 6, 8, 10])
    p = r.choice([k for k in range(1, q) if math.gcd(k, q) == 1])
    n = q * r.randint(3, 30)
    return (_t(f'${n}$ ədədinin $\\frac{{{p}}}{{{q}}}$ hissəsini tapın.', f'Найди $\\frac{{{p}}}{{{q}}}$ от числа ${n}$.',
               f'Find $\\frac{{{p}}}{{{q}}}$ of ${n}$.'), Fraction(n * p, q), (p, q, n))


def _part_back(r):
    q = r.choice([3, 4, 5, 6, 7, 8, 9])
    p = r.choice([k for k in range(1, q) if math.gcd(k, q) == 1])
    x = q * r.randint(2, 25)
    v = x * p // q
    return (_t(f'Ədədin $\\frac{{{p}}}{{{q}}}$ hissəsi ${v}$-dir. Ədədi tapın.', f'$\\frac{{{p}}}{{{q}}}$ числа равны ${v}$. Найди число.',
               f'$\\frac{{{p}}}{{{q}}}$ of a number is ${v}$. Find the number.'), x, (p, q, x))


def _remainder(r):
    b = r.randint(3, 19)
    a = b * r.randint(5, 60) + r.randint(1, b - 1)
    return (_t(f'${a}$ ədədini ${b}$-yə böldükdə qalıq neçə olar?', f'Какой остаток при делении ${a}$ на ${b}$?',
               f'What is the remainder when ${a}$ is divided by ${b}$?'), a % b, (a, b))


def _pct(r):
    p, n = r.choice([5, 10, 15, 20, 25, 30, 40, 45, 60, 75]), r.randrange(20, 400, 20)
    return _t(f'${n}$ ədədinin ${p}\\%$-ni tapın.', f'Найди ${p}\\%$ от числа ${n}$.', f'Find ${p}\\%$ of ${n}$.'), Fraction(n * p, 100), (p, n)


def _pct_back(r):
    p, x = r.choice([10, 20, 25, 30, 40, 50, 60, 75]), r.randrange(20, 300, 4)
    v = Fraction(x * p, 100)
    if v.denominator != 1:
        x, v = x * 4, Fraction(x * 4 * p, 100)
    return (_t(f'${p}\\%$-i ${fmt(v)}$ olan ədədi tapın.', f'Найди число, ${p}\\%$ которого равны ${fmt(v)}$.',
               f'Find the number whose ${p}\\%$ is ${fmt(v)}$.'), x, (p, x))


def _lin(r):
    a, x, b = r.choice([2, 3, 4, 5, 6, 7, 8, 9]), r.randint(-12, 15), r.randint(-20, 20)
    c = a * x + b
    sb = f'+ {b}' if b >= 0 else f'- {-b}'
    return _t(f'${a}x {sb} = {c}$ tənliyini həll edin.', f'Реши уравнение ${a}x {sb} = {c}$.', f'Solve ${a}x {sb} = {c}$.'), x, (a, x, b)


def _lin2(r):
    a, c = r.randint(2, 9), r.randint(2, 9)
    while c == a:
        c = r.randint(2, 9)
    x = r.randint(-9, 12)
    b = r.randint(-15, 15)
    d = a * x + b - c * x
    sb = f'+ {b}' if b >= 0 else f'- {-b}'
    sd = f'+ {d}' if d >= 0 else f'- {-d}'
    return (_t(f'${a}x {sb} = {c}x {sd}$ tənliyini həll edin.', f'Реши уравнение ${a}x {sb} = {c}x {sd}$.', f'Solve ${a}x {sb} = {c}x {sd}$.'),
            x, (a, b, c, d))


def _gcd(r):
    g = r.choice([2, 3, 4, 5, 6, 7, 8, 9, 12, 14, 15])
    m, n = r.sample([k for k in range(2, 13)], 2)
    while math.gcd(m, n) != 1:
        m, n = r.sample([k for k in range(2, 13)], 2)
    a, b = g * m, g * n
    return _t(f'ƏBOB$({a};\\,{b})$-ni tapın.', f'Найди НОД$({a};\\,{b})$.', f'Find GCD$({a};\\,{b})$.'), g, (a, b)


def _lcm(r):
    a, b = r.sample(range(4, 37), 2)
    return _t(f'ƏKOB$({a};\\,{b})$-ni tapın.', f'Найди НОК$({a};\\,{b})$.', f'Find LCM$({a};\\,{b})$.'), a * b // math.gcd(a, b), (a, b)


def _frac_add(r):
    a, b, c, d = r.randint(1, 9), r.randint(2, 12), r.randint(1, 9), r.randint(2, 12)
    return (_t(f'$\\frac{{{a}}}{{{b}}}+\\frac{{{c}}}{{{d}}}$ cəmini hesablayın (adi kəsr kimi yazın).',
               f'Вычисли $\\frac{{{a}}}{{{b}}}+\\frac{{{c}}}{{{d}}}$ (ответ — обыкновенная дробь).',
               f'Compute $\\frac{{{a}}}{{{b}}}+\\frac{{{c}}}{{{d}}}$ (as a fraction).'), Fraction(a, b) + Fraction(c, d), (a, b, c, d))


def _frac_mul(r):
    a, b, c, d = r.randint(1, 12), r.randint(2, 15), r.randint(1, 12), r.randint(2, 15)
    return (_t(f'$\\frac{{{a}}}{{{b}}}\\cdot\\frac{{{c}}}{{{d}}}$ hasilini hesablayın.', f'Вычисли $\\frac{{{a}}}{{{b}}}\\cdot\\frac{{{c}}}{{{d}}}$.',
               f'Compute $\\frac{{{a}}}{{{b}}}\\cdot\\frac{{{c}}}{{{d}}}$.'), Fraction(a, b) * Fraction(c, d), (a, b, c, d))


def _ratio(r):
    p, q = r.sample(range(1, 10), 2)
    k = r.randint(2, 15)
    s = (p + q) * k
    return (_t(f'${s}$ ədədini ${p}:{q}$ nisbətində iki hissəyə bölün. Böyük hissəni tapın.',
               f'Раздели ${s}$ в отношении ${p}:{q}$. Найди большую часть.', f'Split ${s}$ in the ratio ${p}:{q}$. Find the larger part.'),
            max(p, q) * k, (p, q, k))


def _ap(r):
    a1, d, n = r.randint(-10, 20), r.choice([-5, -4, -3, -2, 2, 3, 4, 5, 6, 7]), r.randint(8, 25)
    return (_t(f'Ədədi silsilədə $a_1={a1}$, $d={d}$. $a_{{{n}}}$-i tapın.', f'В арифметической прогрессии $a_1={a1}$, $d={d}$. Найди $a_{{{n}}}$.',
               f'Arithmetic progression: $a_1={a1}$, $d={d}$. Find $a_{{{n}}}$.'), a1 + (n - 1) * d, (a1, d, n))


def _ap_sum(r):
    a1, d, n = r.randint(1, 15), r.randint(1, 6), r.randint(6, 20)
    return (_t(f'Ədədi silsilədə $a_1={a1}$, $d={d}$. İlk ${n}$ həddin cəmini tapın.',
               f'В арифметической прогрессии $a_1={a1}$, $d={d}$. Найди сумму первых ${n}$ членов.',
               f'Arithmetic progression: $a_1={a1}$, $d={d}$. Find the sum of the first ${n}$ terms.'), n * (2 * a1 + (n - 1) * d) // 2, (a1, d, n))


def _quad_sum(r):
    x1, x2 = r.sample(range(-9, 13), 2)
    p, q = -(x1 + x2), x1 * x2
    sp = f'+ {p}x' if p > 0 else (f'- {-p}x' if p < 0 else '')
    sq = f'+ {q}' if q >= 0 else f'- {-q}'
    return (_t(f'$x^2 {sp} {sq} = 0$ tənliyinin köklərinin hasilini tapın.', f'Найди произведение корней уравнения $x^2 {sp} {sq} = 0$.',
               f'Find the product of the roots of $x^2 {sp} {sq} = 0$.'), q, (x1, x2))


def _quad_big(r):
    x1, x2 = sorted(r.sample(range(-9, 13), 2))
    a = r.choice([1, 2, 3])
    b, c = -a * (x1 + x2), a * x1 * x2
    sb = f'+ {b}x' if b > 0 else (f'- {-b}x' if b < 0 else '')
    sc = f'+ {c}' if c >= 0 else f'- {-c}'
    lead = '' if a == 1 else str(a)
    return (_t(f'${lead}x^2 {sb} {sc} = 0$ tənliyinin böyük kökünü tapın.', f'Найди больший корень уравнения ${lead}x^2 {sb} {sc} = 0$.',
               f'Find the larger root of ${lead}x^2 {sb} {sc} = 0$.'), x2, (a, x1, x2))


def _angle_adj(r):
    k1, k2 = r.sample(range(1, 10), 2)
    while 180 % (k1 + k2):
        k1, k2 = r.sample(range(1, 10), 2)
    return (_t(f'Qonşu bucaqların nisbəti ${k1}:{k2}$-dir. Böyük bucağı (dərəcə ilə) tapın.',
               f'Смежные углы относятся как ${k1}:{k2}$. Найди больший угол (в градусах).',
               f'Adjacent angles are in ratio ${k1}:{k2}$. Find the larger one (degrees).'), 180 * max(k1, k2) // (k1 + k2), (k1, k2))


def _rect(r):
    a, b = r.sample(range(3, 30), 2)
    return (_t(f'Düzbucaqlının tərəfləri ${a}$ sm və ${b}$ sm-dir. Sahəsini (sm²) tapın.',
               f'Стороны прямоугольника ${a}$ см и ${b}$ см. Найди площадь (см²).',
               f'A rectangle has sides ${a}$ cm and ${b}$ cm. Find its area (cm²).'), a * b, (a, b))


def _pyth(r):
    a, b, c = r.choice([(3, 4, 5), (5, 12, 13), (8, 15, 17), (7, 24, 25), (20, 21, 29), (9, 40, 41)])
    k = r.randint(1, 6)
    return (_t(f'Düzbucaqlı üçbucağın katetləri ${a * k}$ və ${b * k}$-dir. Hipotenuzu tapın.',
               f'Катеты прямоугольного треугольника ${a * k}$ и ${b * k}$. Найди гипотенузу.',
               f'A right triangle has legs ${a * k}$ and ${b * k}$. Find the hypotenuse.'), c * k, (a, b, k))


def _power(r):
    a, m, n = r.choice([2, 3, 5]), r.randint(2, 9), r.randint(2, 9)
    k = r.randint(1, min(m + n - 1, 4 if a == 2 else 3))
    return (_t(f'$\\frac{{{a}^{{{m}}}\\cdot{a}^{{{n}}}}}{{{a}^{{{m + n - k}}}}}$ ifadəsinin qiymətini tapın.',
               f'Найди значение $\\frac{{{a}^{{{m}}}\\cdot{a}^{{{n}}}}}{{{a}^{{{m + n - k}}}}}$.',
               f'Evaluate $\\frac{{{a}^{{{m}}}\\cdot{a}^{{{n}}}}}{{{a}^{{{m + n - k}}}}}$.'), a ** k, (a, m, n, k))


def _sys(r):
    x, y = r.randint(-8, 10), r.randint(-8, 10)
    a, b = r.randint(1, 5), r.randint(1, 5)
    return (_t(f'$\\begin{{cases}}x+y={x + y}\\\\{a}x-{b}y={a * x - b * y}\\end{{cases}}$ sistemindən $x$-i tapın.',
               f'Из системы $\\begin{{cases}}x+y={x + y}\\\\{a}x-{b}y={a * x - b * y}\\end{{cases}}$ найди $x$.',
               f'From the system $\\begin{{cases}}x+y={x + y}\\\\{a}x-{b}y={a * x - b * y}\\end{{cases}}$ find $x$.'), x, (x, y, a, b))


def _divcount(r):
    p = r.sample([2, 3, 5, 7], 2)
    e1, e2 = r.randint(1, 4), r.randint(1, 3)
    n = p[0] ** e1 * p[1] ** e2
    return (_t(f'${n}$ ədədinin natural bölənlərinin sayını tapın.', f'Найди число натуральных делителей числа ${n}$.',
               f'Find the number of divisors of ${n}$.'), (e1 + 1) * (e2 + 1), (n,))


def _dec(r):
    a, b = r.randint(11, 99) / 10, r.randint(11, 99) / 10
    return (_t(f'${fmt(a)}\\cdot{fmt(b)}$ hasilini hesablayın.', f'Вычисли ${fmt(a)}\\cdot{fmt(b)}$.', f'Compute ${fmt(a)}\\cdot{fmt(b)}$.'),
            Fraction(round(a * 10) * round(b * 10), 100), (a, b))


TEMPLATES: list[Template] = [
    Template('pct', ('faiz', 'nisbe', 'tenas'), 'asan', _pct),
    Template('pct_back', ('faiz',), 'orta', _pct_back),
    Template('lin', ('tenli', 'birme', 'xetti'), 'asan', _lin),
    Template('lin2', ('tenli', 'birme', 'xetti'), 'orta', _lin2),
    Template('gcd', ('natur', 'eboba', 'bolen', 'bolun', 'ortaq'), 'asan', _gcd),
    Template('lcm', ('natur', 'ekoba', 'bolun', 'ortaq'), 'orta', _lcm),
    Template('divcount', ('natur', 'bolen', 'sadev', 'vuruq'), 'çətin', _divcount),
    Template('frac_add', ('kesrl', 'adike', 'kesr'), 'orta', _frac_add),
    Template('frac_mul', ('kesrl', 'adike', 'kesr'), 'asan', _frac_mul),
    Template('dec', ('onluq', 'kesrl'), 'asan', _dec, ('kesr',)),
    Template('ratio', ('nisbe', 'tenas', 'mutena'), 'orta', _ratio),
    Template('ap', ('silsi',), 'orta', _ap),                    # «ədədi» – hər «ədədin» sözünə uyğun gəlirdi (audit 13.10)
    Template('ap_sum', ('silsi',), 'çətin', _ap_sum),
    Template('quad_sum', ('kvadr', 'viyet', 'tenli'), 'orta', _quad_sum),
    Template('quad_big', ('kvadr', 'tenli'), 'çətin', _quad_big),
    Template('sys', ('siste',), 'çətin', _sys, ('tenli',)),     # «say sistemi» deyil – tənliklər sistemi
    Template('angle_adj', ('bucaq', 'qonsu'), 'asan', _angle_adj),
    Template('rect', ('sahe', 'duzbu', 'dordb', 'perim'), 'asan', _rect),
    Template('pyth', ('pifaq', 'duzbu', 'ucbuc', 'hipot'), 'orta', _pyth),
    Template('power', ('quvve', 'ustlu', 'tam'), 'orta', _power),
    Template('sets', ('coxlu',), 'orta', _sets),
    Template('sets_word', ('coxlu',), 'çətin', _sets_word),
    Template('part', ('hisse',), 'asan', _part),
    Template('part_back', ('hisse',), 'orta', _part_back),
    Template('remainder', ('qaliq',), 'asan', _remainder),
]
BY_ID = {t.id: t for t in TEMPLATES}


def matching(topic_stems: set[str]) -> list[Template]:
    """Plan mövzularının köklərinə uyğun şablonlar (açar söz köklərindən biri kifayətdir)."""
    hit = lambda k: any(k in s or s in k for s in topic_stems if len(s) >= 4)          # noqa: E731
    return [t for t in TEMPLATES if any(hit(k) for k in t.keys) and all(hit(k) for k in t.need)]


def _num(s: str) -> Fraction | None:
    try:
        return Fraction(s.replace(',', '.')) if '/' not in s else Fraction(int(s.split('/')[0]), int(s.split('/')[1]))
    except (ValueError, ZeroDivisionError):
        return None


def distractors(ans: str, rng: random.Random, k: int = 4) -> list[str] | None:
    """Düzgün cavaba yaxın, amma fərqli 4 cavab (tipik səhvlər: ±1, ±addım, işarə, ikiqat/yarı). Cütlərdə birinci ədəd dəyişir."""
    parts = ans.split(';')
    a = _num(parts[0])
    if a is None:
        return None
    step = max(Fraction(1), abs(a) / 10) if a.denominator == 1 else Fraction(1, a.denominator)
    pool = [a + 1, a - 1, a + step, a - step, -a, a * 2, a / 2 if a else a + 3, a + 2 * step, a - 2 * step, a + 10]
    out, seen = [], {fmt(a)}
    rng.shuffle(pool)
    for x in pool:
        v = ';'.join([fmt(x), *parts[1:]])
        if fmt(x) not in seen and len(v) <= 12:
            seen.add(fmt(x))
            out.append(v)
        if len(out) == k:
            return out
    return None


def mcq_instance(t: Template, rng: random.Random) -> dict | None:
    """Parametrli şablondan TEST sualı: A–E, düzgün cavabın yeri təsadüfi. Bankda test sualı çatmayanda (KSQ variantları)."""
    q = instance(t, rng)
    wrong = distractors(q['answer'], rng)
    if not wrong:
        return None
    opts = [q['answer'], *wrong]
    rng.shuffle(opts)
    return {**q, 'key': q['key'] + ':m', 'kind': 'mcq', 'options': [{'az': o} for o in opts], 'correct': opts.index(q['answer']),
            'answer': None}


def instance(t: Template, rng: random.Random) -> dict:
    text, ans, params = t.make(rng)
    return {'key': f'tpl:{t.id}:{params}', 'kind': 'open', 'text': text, 'answer': fmt(ans if not isinstance(ans, float) else Fraction(ans).limit_denominator()),
            'level': t.level, 'template': t.id, 'source': 'şablon'}
