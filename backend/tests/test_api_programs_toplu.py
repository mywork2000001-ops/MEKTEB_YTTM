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


# ---------------------------------------------------------------- P007 sualları plan dərsinə (§4)
def _bank_world(world):
    from app.models import BankFile, BankQuestion, BankSource, PlanLesson, TeachingAssignment
    as_, S = world
    admin = as_('admin')
    cid = admin.post('/api/classes', json={'name': 'IX a'}).json()['id']
    admin.post(f'/api/classes/{cid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 2, 'slots': {'1': [1, 5]}})
    c1, c17 = SRC['chapters'][0], SRC['chapters'][16]
    f1 = c1['p007']['lesson'].split('/', 1)[0]
    with S() as db:
        ta = db.query(TeachingAssignment).filter_by(class_id=cid).one()
        rows = [('1. Natural ədədlər', 'Natural ədədlər (2/7): tapşırıqlar 1–27',
                 f'TT 2025 (IX), s.4–8; S 1–14; E 15–24; M 25–27; P007: {f1}',
                 [{'kind': 'sinif', 'label': '', 'start': 1, 'end': 14}, {'kind': 'ev', 'label': '', 'start': 15, 'end': 24},
                  {'kind': 'mustaqil', 'label': '', 'start': 25, 'end': 27}]),
                ('Diaqnostika', 'Diaqnostik test', 'TT 2025 (IX); P007: hər fəsildən 1 sual', None),
                ('Sınaq', 'Sınaq: Cəbr (fəsil 1–14)', 'TT 2025 (IX); P007: Cəbr fəsilləri', None),
                (f'{c17["num"]}. {c17["title"]}', f'{c17["title"]} (1/5): tapşırıqlar 1–20',
                 f'TT 2025 (IX), s.1–2; S 1–20; P007: {c17["p007"]["lesson"].split("/", 1)[0]}',
                 [{'kind': 'sinif', 'label': '', 'start': 1, 'end': 20}]),
                ('Mövzu', 'Adi mövzu', 'Dərslik', None)]
        pls = []
        for i, (sec, topic, res, tasks) in enumerate(rows, 1):
            pl = PlanLesson(assignment_id=ta.id, seq=i, semester=1, assessment_type='formativ', section=sec,
                            topic=f'IX sinif: {topic}', resources=res, tasks=tasks, date=dt.date(2026, 9, 15))
            db.add(pl)
            pls.append(pl)
        db.add(BankSource(key='p007', label='P007'))
        db.flush()
        f = BankFile(source_key='p007', lesson=c1['p007']['lesson'], label='Natural ədədlər', url='http://x/n.html',
                     question_count=31)
        db.add(f)
        db.flush()
        for i in range(1, 31):
            db.add(BankQuestion(file_id=f.id, n=i, qid=str(i), kind='mcq' if i <= 20 else 'open', text={'az': f'S{i}'},
                                options=[{'az': '1'}, {'az': '2'}] if i <= 20 else None, correct=0 if i <= 20 else None,
                                answer=None if i <= 20 else '1', content_hash=f'h{i}', active=i != 16))
        db.add(BankQuestion(file_id=f.id, n=31, qid='a', kind='mcq', text={'az': 'nömrəsiz'}, options=[{'az': '1'}],
                            correct=0, content_hash='hx'))
        db.commit()
        return admin, ta.id, [p.id for p in pls]


def test_toplu_questions_lesson_and_ev(world):
    admin, ta, (les, diag, mock, geo, plain) = _bank_world(world)
    r = admin.get(f'/api/programs/toplu/questions?lesson_id={les}').json()
    assert r['mode'] == 'chapter' and r['in_bank'] and r['has_ev']
    assert [q['qid'] for q in r['questions']] == [i for i in range(1, 28) if i != 16]     # deaktiv və nömrəsiz – yox
    assert r['missing'] == [16] and r['title'] == 'Natural ədədlər · tapşırıqlar 1–27'
    assert all('correct' in q and q['bank_id'] for q in r['questions'])
    r = admin.get(f'/api/programs/toplu/questions?lesson_id={les}&scope=ev').json()
    assert [q['qid'] for q in r['questions']] == [i for i in range(15, 25) if i != 16] and r['title'].endswith('(ev)')
    r = admin.get(f'/api/programs/toplu/questions?lesson_id={les}&scope=chapter&n=9').json()
    kinds = [q['kind'] for q in r['questions']]
    assert len(kinds) == 9 and kinds.count('mcq') == 6 and len({q['qid'] for q in r['questions']}) == 9


def test_toplu_questions_not_in_bank_and_access(world):
    admin, ta, (les, diag, mock, geo, plain) = _bank_world(world)
    r = admin.get(f'/api/programs/toplu/questions?lesson_id={geo}').json()
    assert r['in_bank'] is False and r['questions'] == [] and r['url'].startswith('https://')
    assert admin.get(f'/api/programs/toplu/questions?lesson_id={plain}').status_code == 400
    as_, _ = world
    assert as_('yad').get(f'/api/programs/toplu/questions?lesson_id={les}').status_code == 404


def test_toplu_mock_does_not_repeat(world):
    from app.models import OnlineTask
    admin, ta, (les, diag, mock, geo, plain) = _bank_world(world)
    r = admin.get(f'/api/programs/toplu/questions?lesson_id={diag}').json()
    assert r['mode'] == 'diag' and len(r['questions']) == 1 and len(r['absent']) == 21
    seen = set()
    _, S = world
    for _ in range(5):                                         # 29 sual, hər dəfə 2 – təkrar yoxdur
        r = admin.get(f'/api/programs/toplu/questions?lesson_id={mock}').json()
        assert r['mode'] == 'mock' and len(r['questions']) == 2
        ids = {q['bank_id'] for q in r['questions']}
        assert not ids & seen
        seen |= ids
        with S() as db:
            db.add(OnlineTask(assignment_id=ta, title='s', opens_at=dt.datetime(2026, 9, 15), closes_at=dt.datetime(2026, 9, 16),
                              duration_min=10, questions=r['questions']))
            db.commit()
