"""IX sinif DİM «Test toplusu 2025» proqramı (docs/ix-dim-toplu-perspektiv-promtu.md): məlumat, açılma, bölmə seçimi."""
import datetime as dt
import json

import pytest

from app.importers.plans import parse_resources
from app.programs import DATA, expand_toplu, toplu_template

SRC = json.loads((DATA / 'dim_toplu_9_2025.json').read_text(encoding='utf-8'))
TPL = toplu_template(SRC)
SEM1_END = dt.date(2026, 12, 27)


def days(n):
    return [dt.date(2026, 9, 15) + dt.timedelta(days=i) for i in range(n)]


def test_data_file():
    ch = SRC['chapters']
    assert len(ch) == 22 and sum(c['tasks'] for c in ch) == 2836
    assert all(1 <= c['closed'] <= c['tasks'] and c['p007']['lesson'] for c in ch)
    pages = [c['pages'] for c in ch]
    assert all(a <= b for a, b in pages) and all(pages[i][1] < pages[i + 1][0] for i in range(len(pages) - 1))
    assert not any(k in c for c in ch for k in ('answers', 'answer', 'correct', 'key'))


def _check_cover(les, tpl=TPL):
    """Hər fəslin S/E/M aralıqları 1..tasks-ı boşluqsuz və kəsişmədən əhatə edir; son dərs – fəsil testi."""
    for s in tpl['sections']:
        mine = [l for l in les if l['section'] == s['section']]
        if not mine:
            continue
        nums = [n for l in mine for t in l['tasks'] for n in range(t['start'], t['end'] + 1)]
        assert nums == list(range(1, s['tasks'] + 1)), s['section']
        assert mine[-1]['topic'].endswith('fəsil testi')
        assert all(l['topic'].startswith('IX sinif: ') for l in mine)


@pytest.mark.parametrize('cap', [170, 136, 102, 40])
def test_expand_fills_slots(cap):
    les, warn = expand_toplu(TPL, days(cap), SEM1_END)
    assert len(les) == cap
    _check_cover(les)


def test_reference_allocation_and_reserve():
    for cap in ('170', '136', '102'):
        les, warn = expand_toplu(TPL, days(int(cap)), SEM1_END)
        assert not warn
        per = [sum(1 for l in les if l['section'] == s['section']) for s in TPL['sections']]
        ref = SRC['reference_allocation'][cap]
        assert per == ref['chapters'] and len(les) - sum(per) == ref['reserved']
        t = [l['topic'] for l in les]
        assert 'Diaqnostik' in t[0] and t[-1].endswith('təhlil') and t[-2].endswith('icra')
        assert sum('Sınaq: Cəbr' in x for x in t) == 1 and sum('Sınaq: Həndəsə' in x for x in t) == 1
        alg = t.index(next(x for x in t if 'Sınaq: Cəbr' in x))
        assert 'Çoxluqlar' not in ''.join(t[alg + 1:]) and 'fəsil testi' in ''.join(t[alg - 3:alg])


def test_drop_order():
    les, warn = expand_toplu(TPL, days(48), SEM1_END)        # 44 fəsil dərsi + 4 ehtiyat: sınaqlar çıxır, diaqnostik qalır
    t = [l['topic'] for l in les]
    assert len(les) == 48 and not any('Sınaq:' in x for x in t) and 'Diaqnostik' in t[0] and t[-1].endswith('təhlil')
    assert warn
    les, _ = expand_toplu(TPL, days(46), SEM1_END)           # diaqnostik də çıxır, imtahan (icra + təhlil) qalır
    t = [l['topic'] for l in les]
    assert 'Diaqnostik' not in t[0] and t[-1].endswith('təhlil') and len(les) == 46
    les, _ = expand_toplu(TPL, days(45), SEM1_END)           # təhlil çıxır
    assert les[-1]['topic'].endswith('icra') and len(les) == 45


def test_too_few_slots_warns():
    les, warn = expand_toplu(TPL, days(15), SEM1_END)
    assert any('azdır' in w for w in warn) and len(les) == 22
    _check_cover(les)


def test_sections_geometry_only():
    tpl = dict(TPL, sections=[s for s in TPL['sections'] if s['part'] == 'Həndəsə'])
    les, warn = expand_toplu(tpl, days(60), SEM1_END)
    secs = {l['section'] for l in les}
    assert not any(s.startswith(('1.', '14.')) for s in secs)
    assert any('Sınaq: Həndəsə (fəsil 15–22)' in l['topic'] for l in les)
    assert not any('Sınaq: Cəbr' in l['topic'] for l in les) and len(les) == 60
    _check_cover(les, tpl)


def test_resources_roundtrip():
    les, _ = expand_toplu(TPL, days(170), SEM1_END)
    for l in les:
        if not l['tasks']:
            continue
        pages, tasks = parse_resources(l['resources'])
        assert pages == l['tt_pages']
        assert [(t.kind, t.start, t.end) for t in tasks] == [(t['kind'], t['start'], t['end']) for t in l['tasks']]
    assert les[1]['resources'].startswith('TT 2025 (IX), s.4–8; S 1–') and 'P007: natural-numbers' in les[1]['resources']


def test_builtin_program_api(world):
    as_, _ = world
    t = as_('ilqar')
    lib = t.get('/api/programs').json()
    tp = [p for p in lib if p['toplu']]
    assert len(tp) == 1 and tp[0]['grade'] == 9 and tp[0]['tasks'] == 2836 and 'buraxilis9' in tp[0]['purposes']
    assert len([p for p in t.get('/api/programs').json() if p['toplu']]) == 1        # ensure_builtin idempotent
    d = t.get(f"/api/programs/{tp[0]['id']}").json()
    assert len(d['chapters']) == 22 and d['exam']['tasks'] == 25 and d['chapters'][0]['in_bank'] is False
    assert d['sections'][0] == {'name': '1. Natural ədədlər', 'part': 'Cəbr', 'count': 113}
    pid = t.post('/api/classes', json={'name': 'Fərdi IX DİM', 'kind': 'adi', 'private': True}).json()['id']
    ta = t.post(f'/api/classes/{pid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 3, 'slots': {'1': [1], '3': [1], '5': [1]},
                                                  'program_id': tp[0]['id']}).json()['mine']['ta_id']
    pv = t.get(f"/api/programs/{tp[0]['id']}/preview/{ta}").json()
    assert pv['lessons'] == pv['sem1_slots'] + pv['sem2_slots'] and pv['ksq'] == pv['bsq'] == 0
    geo = [s['name'] for s in d['sections'] if s['part'] == 'Həndəsə']
    pv = t.get(f"/api/programs/{tp[0]['id']}/preview/{ta}", params={'sections': json.dumps(geo)}).json()
    assert all(not x['section'].startswith('1.') for x in pv['list'])
