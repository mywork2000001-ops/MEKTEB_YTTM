"""Hər şagirdə öz rəqəmləri: parametrli suallardan şagird variantları (docs/reqem-variantlari-promtu.md, mərhələ 1).

DB-yə toxunmur. İstifadə (backend qovluğundan):
    py -m scripts.reqem_variantlari scripts/examples/reqem_numune.json --n 25 --lang az
    py -m scripts.reqem_variantlari sablon.json --students students.csv --check
Çıxış: out/<kod>/ – şagird HTML-ləri, acar.html, key.csv, variants.json.
Hesab yalnız sympy ilə (sympify + icazəli adlar), Python eval yoxdur."""
import argparse
import csv
import hashlib
import html
import json
import random
import re
import sys
from pathlib import Path

import sympy as sp

LANGS = ('az', 'ru', 'en')
MAX_TRIES = 200
CARD_RE = re.compile(r'^[0-9,/;-]{1,8}$')
KATEX = 'https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9'
LETTERS = 'ABCDE'


class TemplateError(ValueError):
    """Şablon və ya generasiya xətası (mesajda sual nömrəsi olur)."""


# ---------- təhlükəsiz hesab ----------
def _is_int(v):
    return bool(sp.sympify(v).is_integer)


def _is_sq(v):
    v = sp.sympify(v)
    return bool(v.is_integer and v >= 0 and sp.integer_nthroot(int(v), 2)[1])


SAFE = {'sqrt': sp.sqrt, 'Rational': sp.Rational, 'gcd': sp.gcd, 'lcm': sp.lcm, 'Abs': sp.Abs, 'abs': sp.Abs,
        'floor': sp.floor, 'ceiling': sp.ceiling, 'Min': sp.Min, 'Max': sp.Max, 'min': sp.Min, 'max': sp.Max,
        'factorial': sp.factorial, 'binomial': sp.binomial, 'sign': sp.sign, 'is_int': _is_int, 'is_sq': _is_sq}
_CHARS = re.compile(r'[\w\s+\-*/^().,<>=!&|%]*')
_IDENT = re.compile(r'[A-Za-z_]\w*')


def _names(vals):
    return {**SAFE, **vals}


def sym_eval(expr, vals):
    """İfadəni yalnız icazəli adlarla (parametrlər + SAFE) hesabla."""
    ns = _names(vals)
    s = str(expr)
    if not _CHARS.fullmatch(s) or '__' in s:
        raise TemplateError(f'icazəsiz simvol: {s!r}')
    for name in _IDENT.findall(s):
        if name not in ns and name not in ('and', 'or', 'not'):
            raise TemplateError(f'naməlum ad {name!r}: {s!r}')
    try:
        return sp.sympify(s, locals=ns, rational=True)
    except Exception as e:  # sympy müxtəlif xətalar atır
        raise TemplateError(f'ifadə oxunmur {s!r}: {e}')


def _num(v):
    return sp.Rational(str(v)) if isinstance(v, (int, float, str)) else sp.sympify(v)


def _as_list(x):
    return [] if x is None else (x if isinstance(x, list) else [x])


# ---------- ədədin formatı ----------
def _decimal(r):
    """Sonlu onluq kəsr → '2,5'; deyilsə None."""
    q = int(r.q)
    a = b = 0
    while q % 2 == 0:
        q //= 2
        a += 1
    while q % 5 == 0:
        q //= 5
        b += 1
    if q != 1:
        return None
    sc = max(a, b)
    s = str(int(abs(r) * 10 ** sc)).rjust(sc + 1, '0')
    out = s[:-sc] + ',' + s[-sc:] if sc else s
    return ('-' if r < 0 else '') + out


def card_one(r, decimal=False):
    r = sp.Rational(r)
    if decimal:
        d = _decimal(r)
        if d is None:
            raise TemplateError('onluq kəsr alınmadı')
        return d
    return str(r.p) if r.q == 1 else f'{r.p}/{r.q}'


def card_str(vals, decimal=False):
    """Kart xanasına yazılan cavab: köklər artan sırada ';' ilə."""
    return ';'.join(card_one(v, decimal) for v in sorted(vals))


def tex_one(r, decimal=False):
    r = sp.Rational(r)
    if decimal:
        return card_one(r, True).replace(',', '{,}')
    if r.q == 1:
        return str(r.p)
    return ('-' if r < 0 else '') + f'\\frac{{{abs(r.p)}}}{{{r.q}}}'


def subst(tpl, vals, decimal=False):
    """{a} yerinə ədəd qoy; mənfi ədəd operatordan sonra mötərizədə, '+ -3' → '- 3'."""
    out = ''
    pos = 0
    for m in re.finditer(r'\{(\w+)\}', tpl):
        name = m.group(1)
        if name not in vals:
            continue
        v = sp.Rational(vals[name])
        out += tpl[pos:m.start()]
        nxt = tpl[m.end():m.end() + 1]
        st = out.rstrip()
        spaced = out != st
        last = st[-1:]
        neg, frac = v < 0, v.q != 1
        if neg and last in ('+', '-') and not st.endswith(('\\+', '\\-')):
            sign = '-' if last == '+' else '+'
            before = st[:-1]
            if sign == '+' and (not before.strip() or before.rstrip()[-1] in '$({=,['):
                sign = ''
            out = before + sign + (" " if sign else "") + tex_one(abs(v), decimal)
        else:
            # operatorun / hərfin birbaşa yanında (boşluqsuz) və ya qüvvət əsası ola bilərsə – mötərizə
            glued = bool(last) and (last in ')*^/' or st.endswith(('\\cdot', '\\times'))
                                    or (not spaced and last.isalnum()))
            t = tex_one(v, decimal)
            if (neg or frac) and (glued or nxt == '^'):
                t = f'({t})'
            out += t
        pos = m.end()
    return out + tpl[pos:]


def pick(d, lang):
    """{az,ru,en} → seçilmiş dilin mətni (yoxdursa az)."""
    if isinstance(d, str):
        return d
    return d.get(lang) or d.get('az') or ''


# ---------- şablon ----------
def _param_space(spec):
    if 'choice' in spec:
        return [_num(c) for c in spec['choice']]
    lo, hi, st = int(spec['min']), int(spec['max']), int(spec.get('step', 1))
    bad = {_num(x) for x in spec.get('not', [])}
    return [sp.Integer(x) for x in range(lo, hi + 1, st) if sp.Integer(x) not in bad]


def _compute(q, params):
    """params → (vals, şərtlər ödənir). derived dəyişənlər də vals-a düşür."""
    vals = dict(params)
    for k, e in (q.get('derived') or {}).items():
        vals[k] = sym_eval(e, vals)
    ok = all(bool(sym_eval(w, vals)) for w in _as_list(q.get('where')))
    return vals, ok


def _answers(exprs, vals):
    """İfadə (və ya köklər siyahısı) → rasional ədədlər."""
    res = []
    for e in _as_list(exprs):
        v = sym_eval(e, vals)
        if not getattr(v, 'is_Rational', False):
            raise TemplateError('cavab rasional ədəd deyil')
        res.append(sp.Rational(v))
    return res


def check_template(tpl):
    """original ədədləri original_answer-i verməlidir, yoxsa şablon rədd (sual nömrəsi ilə)."""
    errs = []
    for i, q in enumerate(tpl['questions'], 1):
        if q.get('fixed'):
            continue
        try:
            if q.get('kind') not in ('mcq', 'open'):
                raise TemplateError('kind mcq və ya open olmalıdır')
            if 'original' not in q or 'original_answer' not in q:
                raise TemplateError('original və original_answer yoxdur')
            vals, _ = _compute(q, {k: _num(v) for k, v in q['original'].items()})
            got = sorted(_answers(q['answer'], vals))
            want = sorted(_num(x) for x in _as_list(q['original_answer']))
            if got != want:
                raise TemplateError(f'açar uyğun deyil: düstur {[str(g) for g in got]}, mənbə {[str(w) for w in want]}')
        except Exception as e:
            errs.append(f'Sual {i}: {e}')
    if errs:
        raise TemplateError('Şablon rədd olundu:\n' + '\n'.join(errs))


def _seed(*parts):
    return int(hashlib.sha256('|'.join(map(str, parts)).encode()).hexdigest()[:16], 16)


def _gen_one(q, no, code, sid, used, nstud):
    """Bir şagird + bir sual üçün ədəd dəsti (200 cəhd, sinifdə təkrarsız)."""
    spaces = {k: _param_space(s) for k, s in q['params'].items()}
    size = 1
    for v in spaces.values():
        size *= len(v)
    if size < nstud:
        raise TemplateError(f'Sual {no}: ədəd dəsti azdır ({size} < {nstud} şagird)')
    rng = random.Random(_seed(code, sid, no))
    dec = bool(q.get('decimal'))
    for _ in range(MAX_TRIES):
        params = {k: rng.choice(v) for k, v in spaces.items()}
        sig = tuple(sorted((k, str(v)) for k, v in params.items()))
        if sig in used:
            continue
        try:
            vals, ok = _compute(q, params)
            if not ok:
                continue
            ans = _answers(q['answer'], vals)
            card = card_str(ans, dec)
            dis = []
            if q['kind'] == 'mcq':
                dis = [_answers(d, vals) for d in q.get('distractors', [])]
                cards = [card] + [card_str(d, dec) for d in dis]
                if len(set(cards)) != len(cards):
                    continue
            elif not CARD_RE.match(card):
                continue
        except (TemplateError, TypeError, ZeroDivisionError):
            continue
        return sig, vals, ans, dis, rng
    raise TemplateError(f'Sual {no}: {MAX_TRIES} cəhddə şərtlərə uyğun ədəd dəsti tapılmadı')


def _opt_texts(q, lang, shown, dec):
    t = pick(q.get('option') or '${v}$', lang)
    return [t.replace('{v}', ';\\,'.join(tex_one(v, dec) for v in sorted(x))) for x in shown]


def _fixed_item(q, rng):
    if q['kind'] == 'mcq':
        order = list(range(len(q['options'])))
        rng.shuffle(order)
        return dict(kind='mcq', text=q['text'], options=[q['options'][j] for j in order],
                    correct=order.index(q['correct']), answer=None)
    return dict(kind='open', text=q['text'], options=None, correct=None, answer=str(q['answer']))


def _param_item(q, no, code, sid, used, nstud):
    sig, vals, ans, dis, rng = _gen_one(q, no, code, sid, used, nstud)
    used.add(sig)
    dec = bool(q.get('decimal'))
    text = {lg: subst(pick(q["text"], lg), vals, dec) for lg in LANGS}
    if q['kind'] == 'mcq':
        allv = [ans] + dis
        order = list(range(len(allv)))
        rng.shuffle(order)
        shown = [allv[j] for j in order]
        optl = {lg: _opt_texts(q, lg, shown, dec) for lg in LANGS}
        return dict(kind='mcq', text=text, options=[{lg: optl[lg][k] for lg in LANGS} for k in range(len(shown))],
                    correct=order.index(0), answer=None), vals
    return dict(kind='open', text=text, options=None, correct=None, answer=card_str(ans, dec)), vals


def build(tpl, students, code):
    """students = [(id, ad)] → [{id, name, code, questions:[ExamVariant.questions formatında]}]."""
    check_template(tpl)
    qs = tpl['questions']
    used = [set() for _ in qs]
    fixed_idx = [i for i, q in enumerate(qs) if q.get('fixed')]
    result = []
    for sid, name in students:
        items = []
        for i, q in enumerate(qs):
            if q.get('fixed'):
                it = _fixed_item(q, random.Random(_seed(code, sid, i + 1)))
                vals = {}
            else:
                it, vals = _param_item(q, i + 1, code, sid, used[i], len(students))
            expl = q.get('explanation')
            it['explanation'] = {lg: subst(pick(expl, lg), vals) for lg in LANGS} if expl else None
            it['points'] = q.get('points', 1)
            it['params'] = {k: str(v) for k, v in vals.items()}
            items.append(it)
        # sabit suallar öz aralarında yerini dəyişir
        perm = fixed_idx[:]
        random.Random(_seed(code, sid, 'order')).shuffle(perm)
        ordered = items[:]
        for src, dst in zip(fixed_idx, perm):
            ordered[dst] = items[src]
        for n, it in enumerate(ordered, 1):
            it['slot'] = n
        result.append({'id': sid, 'name': name, 'code': hashlib.sha1(f'{code}|{sid}'.encode()).hexdigest()[:6].upper(),
                       'questions': ordered})
    return result


# ---------- çıxış ----------
def _head(title):
    return (f'<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title>'
            f'<link rel="stylesheet" href="{KATEX}/katex.min.css">'
            f'<script defer src="{KATEX}/katex.min.js"></script>'
            f'<script defer src="{KATEX}/contrib/auto-render.min.js" onload="renderMathInElement(document.body,'
            "{delimiters:[{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false}]})\"></script>"
            '<style>@page{size:A4;margin:15mm}body{font:14px/1.5 Arial,sans-serif;color:#111}'
            '.page{page-break-after:always;min-height:260mm}.h{display:flex;justify-content:space-between;'
            'border-bottom:2px solid #333;margin-bottom:10px;padding-bottom:4px}.q{margin:12px 0}.o{margin-left:22px}'
            '.box{display:inline-block;width:22px;height:26px;border:1px solid #333;margin-right:2px}'
            'table{border-collapse:collapse}td,th{border:1px solid #999;padding:3px 8px}</style></head><body>')


def render_student(tpl, st, lang):
    e = html.escape
    title = pick(tpl.get('title', tpl.get('code', '')), lang)
    h = [f'<div class="page"><div class="h"><b>{e(title)}</b><span>{e(st["name"])} · <b>{st["code"]}</b></span></div>']
    for q in st['questions']:
        h.append(f'<div class="q"><b>{q["slot"]}.</b> {e(pick(q["text"], lang))} <i>({q["points"]})</i>')
        if q['kind'] == 'mcq':
            h += [f'<div class="o">{LETTERS[k]}) {e(pick(o, lang))}</div>' for k, o in enumerate(q['options'])]
        else:
            h.append('<div class="o">' + '<span class="box"></span>' * 8 + '</div>')
        h.append('</div>')
    h.append('</div>')
    return _head(title) + ''.join(h) + '</body></html>'


def key_value(q):
    return LETTERS[q['correct']] if q['kind'] == 'mcq' else q['answer']


def write_out(tpl, built, outdir, lang):
    outdir.mkdir(parents=True, exist_ok=True)
    for n, st in enumerate(built, 1):
        (outdir / f'{n:02d}_{st["code"]}.html').write_text(render_student(tpl, st, lang), encoding='utf-8')
    with open(outdir / 'key.csv', 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['student_id', 'student', 'variant', 'q', 'answer'])
        w.writerows((st['id'], st['name'], st['code'], q['slot'], key_value(q)) for st in built for q in st['questions'])
    body = ''.join(
        f'<h3>{html.escape(st["name"])} · {st["code"]}</h3><table><tr>' + ''.join(f'<th>{q["slot"]}</th>' for q in st['questions'])
        + '</tr><tr>' + ''.join(f'<td>{html.escape(key_value(q))}</td>' for q in st['questions']) + '</tr></table>' for st in built)
    (outdir / 'acar.html').write_text(_head('Açar') + body + '</body></html>', encoding='utf-8')
    data = [{'student_id': st['id'], 'name': st['name'], 'code': st['code'], 'questions': [
        {k: q[k] for k in ('slot', 'kind', 'text', 'options', 'correct', 'answer', 'points', 'explanation')}
        for q in st['questions']]} for st in built]
    (outdir / 'variants.json').write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')


def read_students(path):
    out = []
    with open(path, newline='', encoding='utf-8-sig') as f:
        for row in csv.reader(f):
            if len(row) >= 2 and row[0].strip().lower() != 'id':
                out.append((row[0].strip(), row[1].strip()))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('template')
    ap.add_argument('--students', help='CSV: id,name')
    ap.add_argument('--n', type=int, help='şagird sayı (ad olmadan)')
    ap.add_argument('--lang', choices=LANGS, default='az')
    ap.add_argument('--code', help='imtahan kodu (default: şablondakı code və ya fayl adı)')
    ap.add_argument('--out', default='out')
    ap.add_argument('--check', action='store_true', help='yalnız açar yoxlaması')
    a = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):   # Windows konsolunda ə/ş xətası olmasın
        if hasattr(s, 'reconfigure'):
            s.reconfigure(errors='replace')
    p = Path(a.template)
    tpl = json.loads(p.read_text(encoding='utf-8'))
    code = a.code or tpl.get('code') or p.stem
    try:
        check_template(tpl)
        if a.check:
            print(f'OK: {len(tpl["questions"])} sual, açarlar uyğundur')
            return 0
        if a.students:
            studs = read_students(a.students)
        elif a.n:
            studs = [(str(i), f'Şagird {i}') for i in range(1, a.n + 1)]
        else:
            ap.error('--students və ya --n lazımdır')
        built = build(tpl, studs, code)
    except TemplateError as e:
        print(e, file=sys.stderr)
        return 1
    outdir = Path(a.out) / code
    write_out(tpl, built, outdir, a.lang)
    print(f'{len(built)} şagird → {outdir}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
