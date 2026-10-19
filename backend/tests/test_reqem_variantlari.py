"""Rəqəm variantları skripti (scripts/reqem_variantlari.py): açar, determinizm, təkrarsızlıq, kart formatı."""
import copy
import json
import re
from pathlib import Path

import pytest

from scripts import reqem_variantlari as rv

NUMUNE = Path(__file__).resolve().parent.parent / 'scripts' / 'examples' / 'reqem_numune.json'


@pytest.fixture
def tpl():
    return json.loads(NUMUNE.read_text(encoding='utf-8'))


def studs(n):
    return [(str(i), f'Şagird {i}') for i in range(1, n + 1)]


def test_acar_yoxlamasi_kecir(tpl):
    rv.check_template(tpl)


def test_sehv_dustur_redd_olunur(tpl):
    bad = copy.deepcopy(tpl)
    bad['questions'][1]['answer'] = 'k^3 + b*k^2 + c*k - d'   # işarə səhvi
    with pytest.raises(rv.TemplateError) as e:
        rv.check_template(bad)
    assert 'Sual 2' in str(e.value)


def test_icazesiz_ifade_redd(tpl):
    bad = copy.deepcopy(tpl)
    bad['questions'][0]['answer'] = '__import__("os").getcwd()'
    with pytest.raises(rv.TemplateError):
        rv.check_template(bad)


def test_determinizm(tpl):
    a = rv.build(tpl, studs(10), 'K1')
    b = rv.build(tpl, studs(10), 'K1')
    assert a == b
    assert rv.build(tpl, studs(10), 'K2') != a


def test_30_sagirdde_tekrar_dest_yoxdur(tpl):
    built = rv.build(tpl, studs(30), 'K1')
    for i, q in enumerate(tpl['questions']):
        if q.get('fixed'):
            continue
        # numunədə sabit sual təkdir və sonda durur – parametrli suallar öz yerində qalır
        sets = {tuple(sorted(st['questions'][i]['params'].items())) for st in built}
        assert len(sets) == 30, f'Sual {i + 1}'


def test_kart_formati(tpl):
    for st in rv.build(tpl, studs(30), 'K1'):
        for q in st['questions']:
            if q['kind'] == 'open':
                assert rv.CARD_RE.match(q['answer']), q['answer']
                assert re.fullmatch(r'-?\d+(/\d+)?(;-?\d+(/\d+)?)*', q['answer'])


def test_kesr_ixtisar_ve_onluq():
    from sympy import Rational
    assert rv.card_one(Rational(6, 4)) == '3/2'
    assert rv.card_one(Rational(5, 2), decimal=True) == '2,5'
    assert rv.card_str([Rational(4), Rational(1)]) == '1;4'
    assert rv.card_one(Rational(-7, 4), decimal=True) == '-1,75'


def test_mcq_variantlar_ferqli_ve_duz_cavab_izlenir(tpl):
    seen_idx = set()
    for st in rv.build(tpl, studs(30), 'K1'):
        for q in st['questions']:
            if q['kind'] != 'mcq':
                continue
            az = [o['az'] for o in q['options']]
            assert len(set(az)) == len(az)
            assert 0 <= q['correct'] < len(az)
            seen_idx.add(q['correct'])
    assert len(seen_idx) > 1   # düz cavabın yeri şagirdlər arasında dəyişir


def test_mcq_duz_cavab_hesabla_uygundur(tpl):
    # 3-cü sual: -b/a; seçilmiş düzgün variantın mətni açarla üst-üstə düşür
    st = rv.build(tpl, studs(5), 'K1')[0]
    q = next(x for x in st['questions'] if x['kind'] == 'mcq' and 'x^2' in x['text']['az'] and 'cəmini' in x['text']['az'])
    p = {k: int(v) for k, v in q['params'].items()}
    from sympy import Rational
    want = rv.tex_one(Rational(-p['b'], p['a']))
    assert q['options'][q['correct']]['az'] == f'${want}$'


def test_menfi_ededler():
    from sympy import Integer
    assert rv.subst('$x + {a}$', {'a': Integer(-3)}) == '$x - 3$'
    assert rv.subst('$x - {a}$', {'a': Integer(-3)}) == '$x + 3$'
    assert rv.subst('$2 \\cdot {a}$', {'a': Integer(-3)}) == '$2 \\cdot (-3)$'
    assert rv.subst('$x = {a}$', {'a': Integer(-3)}) == '$x = -3$'
    assert rv.subst('$x - {a}$', {'a': Integer(4)}) == '$x - 4$'


def test_az_olan_sahe_xeta(tpl):
    small = copy.deepcopy(tpl)
    small['questions'][4]['params'] = {'a': {'choice': [2]}, 'b': {'choice': [1, 2]}}
    with pytest.raises(rv.TemplateError) as e:
        rv.build(small, studs(5), 'K1')
    assert 'Sual 5' in str(e.value)


def test_cixis_fayllari(tpl, tmp_path):
    tpath = tmp_path / 't.json'
    tpath.write_text(json.dumps(tpl), encoding='utf-8')
    assert rv.main([str(tpath), '--n', '4', '--lang', 'ru', '--out', str(tmp_path / 'out')]) == 0
    d = tmp_path / 'out' / 'XI-numune'
    assert len(list(d.glob('0*_*.html'))) == 4
    assert (d / 'acar.html').exists() and (d / 'key.csv').exists()
    data = json.loads((d / 'variants.json').read_text(encoding='utf-8'))
    assert data[0]['questions'][0]['slot'] == 1 and set(data[0]['questions'][0]['text']) == {'az', 'ru', 'en'}
    assert rv.main([str(tpath), '--check']) == 0
