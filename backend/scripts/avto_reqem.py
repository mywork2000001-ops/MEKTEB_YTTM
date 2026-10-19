"""Avtomatik «öz rəqəmləri»: istənilən testin suallarından, süni intellektsiz şablon (docs/reqem-variantlari-promtu.md, mərhələ 1b).

DB-yə toxunmur, LLM çağırışı yoxdur: yalnız Python + sympy, deterministik. İstifadə (backend qovluğundan):
    py -m scripts.avto_reqem suallar.json --n 25 [--students csv] [--lang az|ru|en] [--report-only] [--code KOD] [--out out]

GİRİŞ (ikisindən biri):
 1. Bank sualları siyahısı (BankQuestion-ə bənzər; və ya {"questions": [...]}):
      [{"kind": "mcq"|"open", "text": {"az","ru","en"}, "options": [{"az",..}, ...], "correct": 2,
        "answer": "1;4" (open: «a|b» – ilk ifadə götürülür), "points": 1, "image": null}, ...]
 2. Generatorun variants.json faylı: [{"student_id", "name", "code", "questions": [{slot, kind, text, options,
      correct, answer, points, explanation}, ...]}, ...] – ilk şagirdin sualları götürülür (onların ədədləri «mənbə» sayılır).

ÇIXIŞ: out/<kod>/avto_sablon.json (mərhələ 1 şablonu – müəllim baxıb düzəldə bilər), hesabat.txt (hər sual: «🔢 sympy»,
«🔢 düstur …» və ya «⛔ dəyişmir (səbəb)») və (--report-only olmasa) reqem_variantlari generatorunun vərəqləri, açarı, variants.json.

ÜSULLAR (birinci uğurlu): (1) $…$ düsturu sympy-yə çevrilir (öz LaTeX çeviricisi) və açar sözlə əməliyyat seçilir:
kvadrat/çoxhədli kökləri, köklərin cəmi/hasili, ən böyük/kiçik kök, qiymət, Bezu qalığı, P(a), törəmənin qiyməti, ƏBOB/ƏKOB;
(2) mətn məsələsi: mətndəki ədədlərdən ≤3 əməllik (+ − × ÷, kvadrat, faiz; lazım olsa 1, 2, 100 sabiti) ifadə axtarılır,
mənbə cavabını verən ən az əməlli ifadə TƏK olmalıdır; (3) olmadı – «dəyişmir» (yalnız yerlər qarışır).
Məcburi: mənbə ədədləri ilə düstur mənbə cavabını verməlidir (yoxsa fixed). Yeni ədəd: eyni işarə, eyni rəqəm sayı,
tam tam qalır, 0 və 1 yaranmır (mənbədəki 0/1 ədədləri dəyişmir), izahat (explanation) atılır.
Məhdudiyyət: inteqral/limit, naməlumu axtarılan («m-i tapın»), şəkilli suallar avtomatik dəyişmir."""
import argparse
import json
import random
import re
import sys
from fractions import Fraction
from pathlib import Path

import sympy as sp

from . import reqem_variantlari as rv

LANGS = rv.LANGS


class Unsup(Exception):
    """Sual avtomatik parametrləşmir (səbəb mesajda, azərbaycanca)."""


# ---------- kök tapma (şablonda PROOT(i, say, əmsallar…) kimi çağırılır) ----------
def rational_roots(c):
    """Əmsallar (yüksək dərəcədən) → artan sıralı rasional həqiqi köklər; hamısı rasional olmalıdır."""
    c = [sp.Rational(x) for x in c]
    while c and c[0] == 0:
        c = c[1:]
    deg = len(c) - 1
    if deg < 1:
        raise rv.TemplateError('çoxhədli deyil')
    if deg == 1:
        return [-c[1] / c[0]]
    if deg == 2:
        d = c[1] ** 2 - 4 * c[0] * c[2]
        if d < 0:
            raise rv.TemplateError('həqiqi kök yoxdur')
        r = sp.sqrt(d)
        if not r.is_Rational:
            raise rv.TemplateError('kök rasional deyil')
        return sorted({(-c[1] - r) / (2 * c[0]), (-c[1] + r) / (2 * c[0])})
    rts = sp.roots(sp.Poly(c, sp.Symbol('x')))
    if sum(rts.values()) != deg or not all(r.is_Rational for r in rts):
        raise rv.TemplateError('kökləri rasional deyil')
    return sorted(rts)


def _proot(i, cnt, *c):
    roots = rational_roots(c)
    if len(roots) != int(cnt):
        raise rv.TemplateError('kök sayı dəyişdi')
    return roots[int(i)]


def _gcd_n(*a):
    r = a[0]
    for x in a[1:]:
        r = sp.gcd(r, x)
    return r


def _lcm_n(*a):
    r = a[0]
    for x in a[1:]:
        r = sp.lcm(r, x)
    return r


rv.SAFE.update({'PROOT': _proot, 'GCDN': _gcd_n, 'LCMN': _lcm_n})

# ---------- ədədlərin mətndə tapılması ----------
_MASK = re.compile(r'\^\s*\{[^{}]*\}|\^\s*-?\d+|\^\s*[A-Za-z]|_\s*\{[^{}]*\}|_\s*\w|\\sqrt\s*\[[^\]]*\]')
_NUM_M = re.compile(r'(?<![\w.\\])\d+(?:\.\d+|\{,\}\d+)?')
_NUM_T = re.compile(r'(?<![\w.\\])\d+(?:[.,]\d+(?!,\d))?(?!-[A-Za-zəıöüçşğƏİÖÜÇŞĞа-яА-Я]{1,4}\b)')


class Tok:
    def __init__(self, start, end, val, math, pct, dec):
        self.start, self.end, self.val, self.math, self.pct, self.dec = start, end, val, math, pct, dec


def tokenize(text):
    """Mətndəki ədədlər (üstlər/indekslər xaric), unar minus ədədə daxildir."""
    toks = []
    off = 0
    for i, seg in enumerate(text.split('$')):
        math = i % 2 == 1
        masked = [(m.start(), m.end()) for m in _MASK.finditer(seg)] if math else []
        for m in (_NUM_M if math else _NUM_T).finditer(seg):
            s, e = m.span()
            if any(a <= s < b for a, b in masked):
                continue
            lit = m.group().replace('{,}', '.').replace(',', '.')
            neg, st = False, s
            j = s - 1
            if math:
                while j >= 0 and seg[j] == ' ':
                    j -= 1
                if j >= 0 and seg[j] in '-−':
                    k = j - 1
                    while k >= 0 and seg[k] == ' ':
                        k -= 1
                    if k < 0 or seg[k] in '(=,[{<>&+-*/^' or seg[:k + 1].endswith(('\\cdot', '\\times')):
                        neg, st = True, j
            elif j >= 0 and seg[j] in '-−' and (j == 0 or seg[j - 1] in ' ('):
                neg, st = True, j
            val = sp.Rational(lit) * (-1 if neg else 1)
            after = seg[e:e + 12].lower().lstrip()
            pct = after.startswith(('%', '\\%', 'faiz', 'процент', 'percent', 'per cent'))
            toks.append(Tok(off + st, off + e, val, math, pct, len(lit.split('.')[1]) if '.' in lit else 0))
        off += len(seg) + 1
    return toks


def eligible(t):
    return 2 <= abs(t.val) <= 10 ** 6


def align(az, other):
    """Başqa dilin ədədləri → az ədədlərinin indeksi (ardıcıllıq eynidirsə – sıra ilə, yoxsa dəyərlə)."""
    if [t.val for t in az] == [t.val for t in other]:
        return list(range(len(az)))
    first = {}
    for j, t in enumerate(az):
        first.setdefault(t.val, j)
    return [first.get(t.val) for t in other]


def render(text, toks, idx, symname, used, ph='{%s}'):
    out, pos = [], 0
    for t, j in zip(toks, idx):
        nm = symname.get(j) if j is not None else None
        if nm in used:
            out += [text[pos:t.start], ph % nm]
            pos = t.end
    out.append(text[pos:])
    return ''.join(out)


# ---------- LaTeX → sympy ----------
def _grp(s, i):
    while i < len(s) and s[i] == ' ':
        i += 1
    if i >= len(s) or s[i] != '{':
        raise Unsup('LaTeX oxunmadı')
    d = 0
    for j in range(i, len(s)):
        d += (s[j] == '{') - (s[j] == '}')
        if d == 0:
            return s[i + 1:j], j + 1
    raise Unsup('mötərizə bağlanmayıb')


def tex2py(s):
    s = re.sub(r'\\(?:left|right|displaystyle|quad)\s?|\\[,;!]', ' ', s)
    s = re.sub(r'@(n\d+)@', r' \1 ', s)
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == '\\':
            m = re.match(r'\\([A-Za-z]+)', s[i:])
            if not m:
                if s[i:i + 2] == '\\ ':
                    out.append(' ')
                    i += 2
                    continue
                raise Unsup('naməlum LaTeX işarəsi')
            cmd = m.group(1)
            i += 1 + len(cmd)
            if cmd in ('frac', 'dfrac', 'tfrac'):
                a, i = _grp(s, i)
                b, i = _grp(s, i)
                out.append(f'(({tex2py(a)})/({tex2py(b)}))')
            elif cmd == 'sqrt':
                if i < len(s) and s[i] == '[':
                    j = s.index(']', i)
                    n = tex2py(s[i + 1:j])
                    a, i = _grp(s, j + 1)
                    out.append(f'(({tex2py(a)})**(1/({n})))')
                else:
                    a, i = _grp(s, i)
                    out.append(f'sqrt({tex2py(a)})')
            elif cmd in ('cdot', 'times'):
                out.append('*')
            elif cmd == 'div':
                out.append('/')
            elif cmd == 'pi':
                out.append(' pi ')
            else:
                raise Unsup(f'dəstəklənməyən \\{cmd}')
        elif c == '^':
            i += 1
            while i < len(s) and s[i] == ' ':
                i += 1
            if i < len(s) and s[i] == '{':
                a, i = _grp(s, i)
                out.append('**(' + tex2py(a) + ')')
            else:
                m = re.match(r'-?\d+(?:\.\d+)?|[A-Za-z]', s[i:])
                if not m:
                    raise Unsup('üst oxunmadı')
                out.append('**(' + m.group() + ')')
                i += len(m.group())
        elif c in '_}':
            raise Unsup('indeks/artıq mötərizə')
        elif c == '{':
            a, i = _grp(s, i)
            out.append('(' + tex2py(a) + ')')
        else:
            out.append(c)
            i += 1
    return ''.join(out)


_PYTOK = re.compile(r'\s*(\d+(?:\.\d+)?|n\d+|\*\*|[A-Za-z]+|[-+*/()=<>,])')


def tex2sympy(s):
    py = tex2py(s)
    toks, pos = [], 0
    while pos < len(py.rstrip()):
        m = _PYTOK.match(py, pos)
        if not m:
            raise Unsup('ifadə oxunmadı')
        w = m.group(1)
        pos = m.end()
        if re.fullmatch(r'[A-Za-z]+', w) and w not in ('sqrt', 'pi'):
            toks += [(c, 'sym') for c in w]
        elif w in ('sqrt',):
            toks.append((w, 'func'))
        elif re.fullmatch(r'\d+(?:\.\d+)?', w):
            toks.append((w, 'num'))
        elif re.fullmatch(r'n\d+|pi', w):
            toks.append((w, 'sym'))
        else:
            toks.append((w, 'op'))
    if not toks:
        raise Unsup('boş ifadə')
    res = []
    for k, (w, kind) in enumerate(toks):
        if k:
            pw, pk = toks[k - 1]
            left = pk in ('num', 'sym') or pw == ')'
            right = kind in ('num', 'sym', 'func') or w == '('
            if left and right:
                res.append('*')
        res.append(w)
    loc = {w: sp.Symbol(w) for w, k in toks if k == 'sym' and w != 'pi'}
    loc.update({'sqrt': sp.sqrt, 'pi': sp.pi})
    try:
        return sp.sympify(' '.join(res), locals=loc, rational=True)
    except Exception as e:
        raise Unsup(f'sympy oxumadı: {e}')


# ---------- üsul 1: sympy düsturu ----------
_FN_DEF = re.compile(r'\s*[A-Za-z]\s*\(\s*[a-z]\s*\)\s*$')
_CALL = re.compile(r"\s*[A-Za-z]\s*(')?\s*\((.+)\)\s*$")
_NSYM = re.compile(r'n\d+$')


def _fs(e):
    return {s for s in e.free_symbols if not _NSYM.match(s.name)}


def _s(e):
    return sp.sstr(sp.cancel(sp.together(e)))


def _expr_of(seg):
    """'P(x) = …' → sağ tərəf; tənlik olmayan ifadə → özü."""
    if '=' in seg:
        lhs, rhs = seg.split('=', 1)
        if _FN_DEF.match(lhs):
            return tex2sympy(rhs)
        if not rhs.strip():
            return tex2sympy(lhs)
    return tex2sympy(seg)


def _poly(e):
    fs = _fs(e)
    if len(fs) != 1:
        raise Unsup('naməlum dəyişən 1 deyil')
    x = next(iter(fs))
    p = sp.Poly(sp.expand(e), x)
    if p.degree() < 1 or p.degree() > 4:
        raise Unsup('çoxhədlinin dərəcəsi dəstəklənmir')
    return x, p


def _roots_expr(coefs, cnt, i):
    return f"PROOT({i}, {cnt}, {', '.join(sp.sstr(c) for c in coefs)})"


def method_formula(segs, kw, src, symvals, alltoks):
    """(cavab ifadələri, əlavə şərtlər, təsvir). Uyğun tip yoxdursa Unsup."""
    has = lambda *w: any(x in kw for x in w)  # noqa: E731
    mathsegs = [s for s in segs if s.strip()]
    # törəmə
    if has('törəm', 'производн', 'derivativ'):
        defn = next((s for s in mathsegs if '=' in s and _FN_DEF.match(s.split('=', 1)[0])), None)
        pt = next((m.group(2) for s in mathsegs if '=' not in s and (m := _CALL.match(s)) and m.group(1)), None)
        if defn is None or pt is None:
            raise Unsup('törəmə: funksiya və ya nöqtə tapılmadı')
        f = _expr_of(defn)
        x = next(iter(_fs(f)), None)
        if x is None:
            raise Unsup('törəmə: dəyişən yoxdur')
        return [_s(sp.diff(f, x).subs(x, tex2sympy(pt)))], [], 'törəmənin qiyməti'
    # Bezu qalığı
    if has('qalıq', 'остаток', 'remainder') and not has('qalıqsız', 'без остатка', 'no remainder', 'without remainder'):
        if len(mathsegs) < 2:
            raise Unsup('qalıq: bölən tapılmadı')
        f = _expr_of(mathsegs[0])
        x, _ = _poly(f)
        d = _expr_of(mathsegs[-1])
        if _fs(d) != {x} or sp.Poly(sp.expand(d), x).degree() != 1:
            raise Unsup('qalıq: bölən xətti deyil')
        c1, c0 = sp.Poly(sp.expand(d), x).all_coeffs()
        return [_s(f.subs(x, -c0 / c1))], [], 'Bezu qalığı'
    # P(a)
    call = next((s for s in mathsegs if (m := _CALL.match(s)) and not m.group(1) and '=' not in s
                 and re.match(r'\s*[A-Za-z]\s*\(', s)), None)
    defn = next((s for s in mathsegs if '=' in s and _FN_DEF.match(s.split('=', 1)[0])), None)
    if call and defn and not has('kök', 'корн', 'root'):
        f = _expr_of(defn)
        x = next(iter(_fs(f)), None)
        if x is None:
            raise Unsup('funksiya dəyişəni yoxdur')
        return [_s(f.subs(x, tex2sympy(_CALL.match(call).group(2))))], [], 'funksiyanın qiyməti'
    # ƏBOB / ƏKOB
    gcd_kw, lcm_kw = has('əbob', 'нод', 'gcd', 'greatest common', 'наибольший общий'), has('əkok', 'нок', 'lcm', 'least common', 'наименьшее общее')
    if gcd_kw or lcm_kw:
        names = [n for n, v in symvals if v.q == 1 and v > 1]
        if len(names) < 2:
            raise Unsup('ƏBOB/ƏKOB: ədəd çatmır')
        if gcd_kw:
            return [f"GCDN({', '.join(names)})"], [f"GCDN({', '.join(names)}) > 1"], 'ƏBOB'
        return [f"LCMN({', '.join(names)})"], [], 'ƏKOB'
    # tənlik / kök
    eqs = [s for s in mathsegs if '=' in s and s.split('=', 1)[1].strip() and not _FN_DEF.match(s.split('=', 1)[0])]
    if eqs and has('kök', 'корн', 'root', 'həll', 'реши', 'solve', 'tənliy', 'уравнени', 'equation'):
        lhs, rhs = eqs[0].split('=', 1)
        x, p = _poly(tex2sympy(lhs) - tex2sympy(rhs))
        co = p.all_coeffs()
        deg = p.degree()
        extra = []
        if deg == 2 and has('cəm', 'сумм', 'sum', 'hasil', 'произведен', 'product'):
            extra = [f"({sp.sstr(co[1])})**2 - 4*({sp.sstr(co[0])})*({sp.sstr(co[2])}) > 0"]
        if has('cəm', 'сумм', 'sum of'):
            return [_s(-co[1] / co[0])], extra, 'köklərin cəmi (Viyet)'
        if has('hasil', 'произведен', 'product'):
            return [_s((-1) ** deg * co[-1] / co[0])], extra, 'köklərin hasili (Viyet)'
        ncoef = [c.subs({sp.Symbol(n): v for n, v in symvals}) for c in co]
        try:
            cnt = len(rational_roots(ncoef))
        except rv.TemplateError as e:
            raise Unsup(f'tənliyin mənbə kökləri: {e}')
        if has('ən böyük', 'наибольш', 'largest', 'greatest', 'biggest'):
            return [_roots_expr(co, cnt, cnt - 1)], [], 'ən böyük kök', (co, 'max')
        if has('ən kiçik', 'наименьш', 'smallest', 'least'):
            return [_roots_expr(co, cnt, 0)], [], 'ən kiçik kök', (co, 'min')
        return [_roots_expr(co, cnt, i) for i in range(cnt)], [], 'tənliyin kökləri', (co, 'all')
    # qiymət / sadələşdirmə
    if has('hesabla', 'вычисл', 'calculate', 'evaluate', 'compute', 'qiymət', 'значени', 'value', 'sadələşdir', 'упрост', 'simplify', 'tapın', 'найдите', 'find'):
        for s in mathsegs:
            s2 = s.strip()
            if s2.endswith('='):
                s2 = s2[:-1]
            if '=' in s2:
                continue
            e = tex2sympy(s2)
            if not _fs(e):
                return [_s(e)], [], 'ifadənin qiyməti'
    raise Unsup('düstur tipi tanınmadı')


# ---------- üsul 2: mətn məsələsi – düstur axtarışı ----------
def _fpv(v):
    return tuple(Fraction(x) for x in v)


def _search(items, maxops=3, maxleaves=4):
    """items = [(ad, fp, ədəddir)] → {fp: (əməl sayı, ifadə)} (içində ≥1 ədəd olanlar)."""
    k = len(items)
    R = [None] * (1 << k)
    nummask = sum(1 << i for i, it in enumerate(items) if it[2])

    def add(res, fp, o, e):
        if any(abs(x) > 10 ** 12 for x in fp):
            return
        if fp not in res or o < res[fp][0]:
            res[fp] = (o, e)

    def squares(res):
        for fp, (o, e) in list(res.items()):
            if o + 1 <= maxops:
                add(res, tuple(x * x for x in fp), o + 1, f'({e})**2')

    for i, (nm, fp, _) in enumerate(items):
        R[1 << i] = {fp: (0, nm)}
        squares(R[1 << i])
    final = {}
    for M in range(1, 1 << k):
        pc = bin(M).count('1')
        if pc > maxleaves:
            continue
        if pc > 1:
            res = {}
            S = (M - 1) & M
            while S:
                T = M ^ S
                for fa, (oa, ea) in R[S].items():
                    for fb, (ob, eb) in R[T].items():
                        o = oa + ob + 1
                        if o > maxops:
                            continue
                        if S < T:
                            add(res, tuple(a + b for a, b in zip(fa, fb)), o, f'({ea}+{eb})')
                            add(res, tuple(a * b for a, b in zip(fa, fb)), o, f'({ea}*{eb})')
                        add(res, tuple(a - b for a, b in zip(fa, fb)), o, f'({ea}-{eb})')
                        if all(b != 0 for b in fb):
                            add(res, tuple(a / b for a, b in zip(fa, fb)), o, f'({ea}/{eb})')
                S = (S - 1) & M
            squares(res)
            R[M] = res
        if M & nummask:
            for fp, (o, e) in R[M].items():
                if fp not in final or o < final[fp][0]:
                    final[fp] = (o, e)
    return final


def method_word(symvals, pcts, target):
    """Mətndəki ədədlərdən tək ən az əməlli ifadə; (ifadə, təsvir). Tapılmadı/çox: Unsup."""
    if not symvals:
        raise Unsup('mətndə dəyişdirilə bilən ədəd yoxdur')
    if len(symvals) > 6:
        raise Unsup('ədəd çoxdur (>6)')
    rng = random.Random(7)
    probes = [[rng.randint(3, 60) for _ in symvals] for _ in range(3)]
    base = []
    for i, (nm, v) in enumerate(symvals):
        pc = nm in pcts
        vec = [sp.Rational(v)] + [sp.Rational(p) for p in (pr[i] for pr in probes)]
        if pc:
            vec = [x / 100 for x in vec]
        base.append((f'({nm}/100)' if pc else nm, _fpv(vec), True))
    tgt = Fraction(int(target.p), int(target.q))
    for consts in ((), (1, 2, 100)):
        items = base + [(str(c), _fpv([c] * 4), False) for c in consts]
        hits = {fp: oe for fp, oe in _search(items).items() if fp[0] == tgt}
        if hits:
            m = min(o for o, _ in hits.values())
            best = [e for o, e in hits.values() if o == m]
            if consts:   # sabitli ifadə (məs. 1 + p) təsadüfi uyğunluq olmasın deyə ≥2 ədəd işlətməlidir
                best = [e for e in best if len(set(re.findall(r'n\d+', e))) >= 2]
                if not best:
                    break
            if len(best) > 1:   # bərabərlikdə bütün ədədləri işlədən ifadə üstündür
                top = max(len(set(re.findall(r'n\d+', e))) for e in best)
                best = [e for e in best if len(set(re.findall(r'n\d+', e))) == top]
            if len(best) != 1:
                raise Unsup(f'düstur birqiymətli deyil ({len(best)} namizəd)')
            return best[0], f'düstur {best[0]}'
    raise Unsup('düstur tapılmadı')


# ---------- mənbə cavabı və variantlar ----------
_FRAC = re.compile(r'(-?)\s*\\[dt]?frac\{(-?\d+)\}\{(\d+)\}')
_RAT = re.compile(r'-?\d+\s*/\s*\d+')
_DEC = re.compile(r'-?\d+(?:\{,\}\d+|[.,]\d+)?')
_BAD = re.compile(r'\\(?:sqrt|pi|log|sin|cos|tan|ln|lg)|\^|_')


def num_in(s):
    """Mətndə TƏK ədəd (kəsr daxil) → (qiymət, (a, b) aralığı, onluqdur). Başqa halda Unsup."""
    s = s.replace('−', '-')
    if _BAD.search(s):
        raise Unsup('cavabda kök/üst/funksiya var')
    dec = False
    m = _FRAC.search(s)
    if m:
        v = sp.Rational(int(m.group(2)), int(m.group(3))) * (-1 if m.group(1) else 1)
    else:
        m = _RAT.search(s)
        if m:
            a, b = m.group().split('/')
            v = sp.Rational(int(a), int(b))
        else:
            m = _DEC.search(s)
            if not m:
                raise Unsup('cavabda ədəd yoxdur')
            lit = m.group().replace('{,}', '.').replace(',', '.')
            dec = '.' in lit
            v = sp.Rational(lit)
    if re.search(r'\d', s[:m.start()] + s[m.end():]):
        raise Unsup('cavabda bir neçə ədəd var')
    return v, m.span(), dec


def _loc(x, lg):
    return x.get(lg) if isinstance(x, dict) else x


def source_answer(q, base):
    """(mənbə cavabları [Rational], onluq?)"""
    if q['kind'] == 'mcq':
        opts = q.get('options') or []
        ci = q.get('correct')
        if ci is None or not (0 <= ci < len(opts)) or len(opts) < 2:
            raise Unsup('mcq: seçimlər/düz cavab yoxdur')
        v, _, dec = num_in(_loc(opts[ci], base) or '')
        return [v], dec
    ans = str(q.get('answer') or '')
    last = 'cavab oxunmadı'
    for alt in ans.split('|'):
        try:
            vals, dec = [], False
            for part in alt.split(';'):
                v, _, d = num_in(part)
                vals.append(v)
                dec = dec or d
            return vals, dec
        except Unsup as e:
            last = str(e)
    raise Unsup(last)


def param_spec(t, relax):
    """Mənbə ədədinə uyğun aralıq: eyni işarə, eyni rəqəm sayı, 0/1 yoxdur; (spec, ölçü)."""
    sign = -1 if t.val < 0 else 1
    a = abs(t.val)
    if a.q == 1:
        a = int(a)
        d = len(str(a))
        lo, hi = (10 ** (d - 1) if d > 1 else 2), 10 ** d - 1
        step = 1 if relax else (10 if a % 10 == 0 and a >= 10 else 5 if a % 5 == 0 and a >= 10 else 1)
        if step == 1:
            return ({'min': -hi, 'max': -lo} if sign < 0 else {'min': lo, 'max': hi}), hi - lo + 1
        vals = [sign * x for x in range(lo, hi + 1) if x % step == 0]
        return {'choice': vals}, len(vals)
    k = t.dec
    d = len(str(int(a)))
    lo, hi = (10 ** (d - 1) if d > 1 else 2), 10 ** d - 1
    ms = [m for m in range(lo * 10 ** k, (hi + 1) * 10 ** k) if m % 10]
    ms = ms[::max(1, len(ms) // 120)]
    ch = [('-' if sign < 0 else '') + f'{m // 10 ** k}.{m % 10 ** k:0{k}d}' for m in ms]
    return {'choice': ch}, len(ch)


def infer_dis(dvals, c, A, syms):
    """Mənbə distraktorlarının düz cavabla əlaqəsi → yeni cavaba tətbiq olunan ifadələr (tapılmasa cavab ± addım)."""
    out, step_i = [], 0
    steps = [1, -1, 2, -2, 3, -3, 4, -4, 5, -5]
    for d in dvals:
        e = None
        if c != 0 and d == -c:
            e = f'-({A})'
        elif c != 0 and d == 1 / c:
            e = f'1/({A})'
        elif c != 0 and d == 10 * c:
            e = f'10*({A})'
        elif c != 0 and d == c / 10:
            e = f'({A})/10'
        elif c != 0 and d == 2 * c:
            e = f'2*({A})'
        elif c != 0 and d == c / 2:
            e = f'({A})/2'
        else:
            for nm, v in syms:
                if d == v:
                    e = nm
                elif d == c + v:
                    e = f'({A})+{nm}'
                elif d == c - v:
                    e = f'({A})-{nm}'
                elif d == v - c:
                    e = f'{nm}-({A})'
                elif d == c * v:
                    e = f'({A})*{nm}'
                elif v != 0 and d == c / v:
                    e = f'({A})/{nm}'
                if e:
                    break
            if e is None and (d - c).q == 1 and d != c and abs(d - c) <= 20:
                e = f'({A}){int(d - c):+d}'
        if e is None or e in out:
            e = f'({A}){steps[step_i % len(steps)]:+d}'
            step_i += 1
        out.append(e)
    return out


def quad_reparam(hint, vals0, az, inv):
    """a·x² + b·x + c = 0 (b, c ayrı ədədlərdən asılı): köklər r1<r2 parametr, b və c onlardan törəyir."""
    if not hint:
        return None
    co, mode = hint
    if len(co) != 3:
        return None
    a, c1, c0 = co
    sub = {sp.Symbol(k): v for k, v in vals0.items()}
    try:
        roots = rational_roots([c.subs(sub) for c in co])
    except rv.TemplateError:
        return None
    if len(roots) != 2 or any(r.q != 1 for r in roots):
        return None
    s1, s0, sa = ({x.name for x in e.free_symbols} for e in (c1, c0, a))
    if len(s1) != 1 or len(s0) != 1 or s1 == s0 or (s1 | s0) & sa:
        return None
    n1, n0 = next(iter(s1)), next(iter(s0))
    r1, r2 = sp.symbols('r1 r2')
    d1 = sp.solve(sp.Eq(c1, -a * (r1 + r2)), sp.Symbol(n1))
    d0 = sp.solve(sp.Eq(c0, a * r1 * r2), sp.Symbol(n0))
    if len(d1) != 1 or len(d0) != 1:
        return None
    where, derived = ['r1 < r2'], {}
    for nm, d in ((n1, d1[0]), (n0, d0[0])):
        spec, _ = param_spec(az[inv[nm]], True)
        lo, hi = spec['min'], spec['max']
        lo, hi = (lo, hi * 10 + 9) if lo > 0 else (lo * 10 - 9, hi)   # bir rəqəm artıq olmasına icazə
        where += [f'{nm} >= {lo}', f'{nm} <= {hi}']
        derived[nm] = sp.sstr(d)
    pspecs, orig = {}, {}
    for nm, r in (('r1', roots[0]), ('r2', roots[1])):
        if abs(r) >= 2:
            pspecs[nm] = param_spec(Tok(0, 0, r, False, False, 0), True)[0]
        else:
            pspecs[nm] = ({'min': -9, 'max': 9, 'not': [0, 1, -1]} if r == 0
                          else {'min': 2, 'max': 9} if r > 0 else {'min': -9, 'max': -2})
        orig[nm] = r
    for nm in sorted(sa):
        pspecs[nm] = param_spec(az[inv[nm]], True)[0]
        orig[nm] = vals0[nm]
    ans = {'all': ['r1', 'r2'], 'max': ['Max(r1, r2)'], 'min': ['Min(r1, r2)']}[mode]
    return ans, where, derived, pspecs, orig, {n1, n0} | sa


def _repro(ans, src, vals):
    got = sorted(rv._answers(ans, vals))
    return got == sorted(src)


def auto_question(q, n):
    """Bir sual → (şablon sualı, (üsul, təsvir)). Alınmasa Unsup."""
    if q.get('image'):
        raise Unsup('şəkil var')
    kind = q.get('kind')
    if kind not in ('mcq', 'open'):
        raise Unsup('sual tipi tanınmadı')
    text = q.get('text')
    text = {'az': text} if isinstance(text, str) else dict(text or {})
    langs = [lg for lg in LANGS if text.get(lg)]
    if not langs:
        raise Unsup('sual mətni yoxdur')
    base = 'az' if 'az' in langs else langs[0]
    src, dec = source_answer(q, base)
    toks = {lg: tokenize(text[lg]) for lg in langs}
    az = toks[base]
    idx = {lg: (list(range(len(az))) if lg == base else align(az, toks[lg])) for lg in langs}
    symname = {}
    for j, t in enumerate(az):
        if eligible(t):
            symname[j] = f'n{len(symname) + 1}'
    if not symname:
        raise Unsup('dəyişdirilə bilən ədəd yoxdur')
    symvals = [(symname[j], az[j].val) for j in sorted(symname)]
    pcts = {symname[j] for j in symname if az[j].pct}
    conv = render(text[base], az, idx[base], symname, set(symname.values()), ph='@%s@')
    segs = conv.split('$')[1::2]
    kw = ' '.join(' '.join(text[lg].split('$')[0::2]) for lg in langs).lower()
    vals0 = {nm: v for nm, v in symvals}
    found, reasons = None, []
    for meth in ('sympy', 'düstur'):
        try:
            if meth == 'sympy':
                ans, extra, desc, *hint = method_formula(segs, kw, src, symvals, az)
                hint = hint[0] if hint else None
            else:
                if len(src) != 1:
                    raise Unsup('cavab bir ədəd deyil')
                plain = [(symname[j], az[j].val) for j in sorted(symname) if not az[j].math]   # $…$ ədədləri məsələ sayılmır
                e, desc = method_word(plain, pcts, src[0])
                ans, extra, hint = [e], [], None
            if not _repro(ans, src, vals0):
                raise Unsup('açar uyğun deyil – düstur mənbə cavabını vermir')
            found = (meth, desc, ans, extra, hint)
            break
        except Exception as e:  # sympy müxtəlif xətalar atır
            reasons.append(f'{meth}: {e}')
    if not found:
        raise Unsup('; '.join(reasons))
    meth, desc, ans, extra, hint = found
    if kind == 'mcq' and len(ans) != 1:
        raise Unsup('mcq: cavab bir ədəd deyil')
    where = list(extra)
    if all(v.q == 1 for v in src):
        where += [f'is_int({a})' for a in ans]
    if meth == 'düstur' and src[0] > 0:
        where.append(f'({ans[0]}) > 0')
    inv = {v: k for k, v in symname.items()}
    rp = quad_reparam(hint, vals0, az, inv) if hint and meth == 'sympy' else None
    if rp:   # kvadrat tənlik: kökləri parametr, əmsalları onlardan törət (kökləri rasional olsun)
        ans, where, derived, pspecs, orig, used = rp
    else:
        used = set(re.findall(r'n\d+', ' '.join(ans + where)))
        derived = {}
    if not used:
        raise Unsup('cavab ədədlərdən asılı deyil')
    for lg in langs:
        have = set(idx[lg])
        if any(inv[u] not in have for u in used):
            raise Unsup(f'{lg} mətnində ədədlər az ilə uyğun gəlmir')
    dec = dec or any(az[inv[u]].dec for u in used)
    if not rp:
        for relax in (False, True):
            specs = {u: param_spec(az[inv[u]], relax) for u in sorted(used)}
            size = 1
            for _, sz in specs.values():
                size *= sz
            if size >= max(4 * n, 40):
                break
        pspecs = {u: specs[u][0] for u in sorted(used)}
        orig = {u: vals0[u] for u in sorted(used)}
    t = {'kind': kind, 'points': q.get('points', 1),
         'text': {lg: render(text[lg], toks[lg], idx[lg], symname, used) for lg in langs},
         'params': pspecs, 'where': where,
         'answer': ans if len(ans) > 1 else ans[0],
         'original': {u: (int(v) if v.q == 1 else str(v)) for u, v in orig.items()},
         'original_answer': [(int(v) if v.q == 1 else str(v)) for v in src] if len(src) > 1
         else (int(src[0]) if src[0].q == 1 else str(src[0]))}
    if derived:
        t['derived'] = derived
    if dec:
        t['decimal'] = True
    if kind == 'mcq':
        opts, ci = q['options'], q['correct']
        tmpl = {}
        for lg in langs:
            s = _loc(opts[ci], lg)
            if not s:
                raise Unsup(f'{lg} seçimi yoxdur')
            _, (a, b), _ = num_in(s)
            tmpl[lg] = s[:a] + '{v}' + s[b:]
        if '$' not in tmpl[base] and not (dec or all(v.q == 1 for v in src)):
            raise Unsup('seçimdə kəsr mətn daxilindədir')
        dv = [num_in(_loc(o, base) or '')[0] for k, o in enumerate(opts) if k != ci]
        t['option'] = tmpl
        t['distractors'] = infer_dis(dv, src[0], ans[0], [(u, vals0[u]) for u in sorted(used)])
    try:
        rv.check_template({'questions': [t]})
        rv._gen_one(t, 1, 'sinaq', '1', set(), n)
    except rv.TemplateError as e:
        raise Unsup(str(e).replace('Sual 1: ', '').replace('Şablon rədd olundu:\n', ''))
    t['auto'] = {'method': meth, 'formula': desc}
    return t, (meth, desc)


def fixed_question(q):
    text = q.get('text')
    f = {'kind': q.get('kind') if q.get('kind') in ('mcq', 'open') else 'open', 'points': q.get('points', 1),
         'fixed': True, 'text': {'az': text} if isinstance(text, str) else text}
    if f['kind'] == 'mcq' and q.get('options') and q.get('correct') is not None:
        f['options'] = [o if isinstance(o, dict) else {'az': o} for o in q['options']]
        f['correct'] = q['correct']
    else:
        f['kind'] = 'open'
        f['answer'] = str(q.get('answer') or '')
    return f


def convert(questions, n):
    """Suallar → (şablon sualları, hesabat siyahısı [{no, method, detail}])."""
    tq, rep = [], []
    for i, q in enumerate(questions, 1):
        try:
            t, (meth, desc) = auto_question(q, n)
            tq.append(t)
            rep.append({'no': i, 'method': meth, 'detail': desc})
        except Unsup as e:
            tq.append(fixed_question(q))
            rep.append({'no': i, 'method': 'fixed', 'detail': str(e)})
    return tq, rep


def report_lines(rep):
    out = []
    for r in rep:
        if r['method'] == 'fixed':
            out.append(f"{r['no']}. ⛔ dəyişmir ({r['detail']})")
        elif r['method'] == 'sympy':
            out.append(f"{r['no']}. 🔢 sympy ({r['detail']})")
        else:
            out.append(f"{r['no']}. 🔢 {r['detail']}")
    a = sum(1 for r in rep if r['method'] != 'fixed')
    out.append(f"Cəmi {len(rep)} sual: {a} avtomatik (sympy {sum(r['method'] == 'sympy' for r in rep)}, "
               f"düstur {sum(r['method'] == 'düstur' for r in rep)}), {len(rep) - a} dəyişmir")
    return out


def build_safe(questions, tpl, students, code, rep):
    """rv.build; generasiya xətası verən sual fixed-ə çevrilir (hesabat yenilənir)."""
    while True:
        try:
            return rv.build(tpl, students, code)
        except rv.TemplateError as e:
            m = re.search(r'Sual (\d+)', str(e))
            i = int(m.group(1)) - 1 if m else -1
            if i < 0 or tpl['questions'][i].get('fixed'):
                raise
            qi = tpl['questions'][i]
            if any(w.startswith('is_int(') for w in qi.get('where', [])):   # «gözəl cavab» şərti çox sərtdir – yumşalt
                qi['where'] = [w for w in qi['where'] if not w.startswith('is_int(')]
                continue
            tpl['questions'][i] = fixed_question(questions[i])
            rep[i] = {'no': i + 1, 'method': 'fixed', 'detail': str(e).split(': ', 1)[-1]}


def _clean(s):
    parts = s.split('$')
    return '$'.join(p.replace('{,}', ',') if k % 2 == 0 else p for k, p in enumerate(parts))


def clean_built(built):
    """Onluq vergül {,} yalnız riyazi rejimdə qalır; adi mətndə ',' olur."""
    for st in built:
        for q in st['questions']:
            q['text'] = {k: _clean(v) for k, v in q['text'].items()}
            if q.get('options'):
                q['options'] = [{k: _clean(v) for k, v in o.items()} if isinstance(o, dict) else o for o in q['options']]
    return built


def template_to_questions(tpl):
    """Şablon → adi bank sualları (şablon sahələri atılır, ədədlər `original` ilə yerinə qoyulur)."""
    out = []
    for q in tpl['questions']:
        if q.get('fixed'):
            out.append({k: v for k, v in q.items() if k != 'fixed'})
            continue
        vals, _ = rv._compute(q, {k: rv._num(v) for k, v in q['original'].items()})
        dec = bool(q.get('decimal'))
        item = {'kind': q['kind'], 'points': q.get('points', 1),
                'text': {lg: rv.subst(rv.pick(q['text'], lg), vals, dec) for lg in LANGS}}
        ans = rv._answers(q['answer'], vals)
        if q['kind'] == 'mcq':
            allv = [ans] + [rv._answers(d, vals) for d in q.get('distractors', [])]
            item['options'] = [{lg: o for lg, o in zip(LANGS, row)} for row in
                               zip(*[rv._opt_texts(q, lg, allv, dec) for lg in LANGS])]
            item['correct'] = 0
        else:
            item['answer'] = rv.card_str(ans, dec)
        out.append(item)
    return out


def load_questions(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if isinstance(data, dict):
        data = data.get('questions', data)
    if data and isinstance(data[0], dict) and 'questions' in data[0]:   # variants.json – ilk şagird
        data = data[0]['questions']
    return data


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('questions')
    ap.add_argument('--students', help='CSV: id,name')
    ap.add_argument('--n', type=int, help='şagird sayı (ad olmadan)')
    ap.add_argument('--lang', choices=LANGS, default='az')
    ap.add_argument('--code')
    ap.add_argument('--out', default='out')
    ap.add_argument('--report-only', action='store_true', help='vərəq yaratma, yalnız şablon + hesabat')
    a = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, 'reconfigure'):
            s.reconfigure(errors='replace')
    qs = load_questions(a.questions)
    code = a.code or Path(a.questions).stem
    if a.students:
        studs = rv.read_students(a.students)
    else:
        studs = [(str(i), f'Şagird {i}') for i in range(1, (a.n or 25) + 1)]
    tq, rep = convert(qs, len(studs))
    tpl = {'code': code, 'title': {lg: code for lg in LANGS}, 'questions': tq}
    built = None
    try:
        if not a.report_only:
            built = clean_built(build_safe(qs, tpl, studs, code, rep))
    except rv.TemplateError as e:
        print(e, file=sys.stderr)
        return 1
    outdir = Path(a.out) / code
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / 'avto_sablon.json').write_text(json.dumps(tpl, ensure_ascii=False, indent=1), encoding='utf-8')
    lines = report_lines(rep)
    (outdir / 'hesabat.txt').write_text('\n'.join(lines), encoding='utf-8')
    print('\n'.join(lines))
    if built:
        rv.write_out(tpl, built, outdir, a.lang)
        print(f'{len(built)} şagird → {outdir}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
