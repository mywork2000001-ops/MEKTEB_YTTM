"""Yazılı «Viktorina»: bütün viktorina bazasından (bir neçə mənbə) yazılı iş, Exam.kind = VIK + /api/bank/viktorina-topics."""
from app.models import BankFile, BankQuestion, BankSource

from .test_api_portal import setup


def _vik_bank(S):
    """İki mənbə (py, pz) + sinfi göstərilməyən fayl + söndürülmüş mənbə; a və b fayllarında ilk 4 sual eynidir (content_hash)."""
    ids = {}
    with S() as db:
        for key, enabled in (('py', True), ('pz', True), ('pd', False)):
            db.add(BankSource(key=key, label=key.upper(), enabled=enabled))
        db.flush()
        spec = [('py', 'a', [9], 'movzu'), ('pz', 'b', [9, 10], 'movzu'), ('py', 'c', [5], 'movzu'), ('pz', 'n', [], 'movzu'),
                ('pd', 'd', [9], 'movzu'), ('py', 's', [9], 'sinaq')]
        for src, name, grades, kind in spec:
            f = BankFile(source_key=src, lesson=f'{name}.html', label=f'Mövzu {name}', url='http://x', kind=kind, grades=grades,
                         question_count=30)
            db.add(f)
            db.flush()
            ids[name] = f.id
            for i in range(30):
                qk = 'mcq' if i % 2 == 0 else 'open'
                h = f'shared{i}' if i < 4 and name in ('a', 'b') else f'{name}{i}'
                db.add(BankQuestion(file_id=f.id, n=i + 1, kind=qk, text={'az': f'Sual {h}'}, content_hash=h,
                                    options=[{'az': '1'}, {'az': '2'}, {'az': '3'}] if qk == 'mcq' else None,
                                    correct=i % 3 if qk == 'mcq' else None, answer=None if qk == 'mcq' else str(i + 1),
                                    diff_auto=['asan', 'orta', 'çətin'][i % 3]))
        db.commit()
    return ids


def test_viktorina_topics_filters(world):
    admin, ta, cid, st, ids = setup(world)
    _, S = world
    f = _vik_bank(S)
    r = admin.get('/api/bank/viktorina-topics', params={'grade': 9})
    assert r.status_code == 200, r.text
    d = r.json()
    got = {(g['source_key'], g['no_grade']): [x['id'] for x in g['files']] for g in d}
    # 5-ci sinif faylı, söndürülmüş mənbə və sınaq faylı çıxmır; sinfi göstərilməyən – ayrıca qrup, sonda
    assert got == {('py', False): [f['a']], ('pz', False): [f['b']], ('pz', True): [f['n']]}
    assert d[-1]['no_grade'] is True
    allk = admin.get('/api/bank/viktorina-topics', params={'grade': 9, 'kind': 'all'}).json()
    assert f['s'] in {x['id'] for g in allk for x in g['files']}
    assert {g['source_key'] for g in admin.get('/api/bank/viktorina-topics', params={'grade': 5}).json()} == {'py', 'pz'}


def test_viktorina_paper_two_sources(world):
    admin, ta, cid, st, ids = setup(world)
    _, S = world
    f = _vik_bank(S)
    body = {'file_ids': [f['a'], f['b']], 'viktorina': True, 'n': 20, 'date': '2026-10-05'}
    r = admin.post(f'/api/paper-exams/{ta}', json={**body, 'variant_mode': 'same'})
    assert r.status_code == 200, r.text
    e = r.json()['exam']
    assert e['kind'] == 'VIK' and e['title'] == 'Viktorina'
    pr = admin.get(f'/api/exams/{ta}/{e["id"]}/variants/print').json()
    assert len({tuple(q['text'] for q in s['questions']) for s in pr['sheets']}) == 1 and len(pr['sheets'][0]['questions']) == 20
    # hər şagirdə fərqli: vərəq daxilində təkrar sual yoxdur (ortaq suallar bir dəfə sayılır)
    r2 = admin.post(f'/api/paper-exams/{ta}', json={**body, 'variant_mode': 'different', 'n': 10, 'title': 'Vik 2'})
    assert r2.status_code == 200, r2.text
    e2 = r2.json()['exam']
    assert e2['kind'] == 'VIK' and e2['title'] == 'Vik 2' and e2['no'] == e['no'] + 1
    pr2 = admin.get(f'/api/exams/{ta}/{e2["id"]}/variants/print').json()
    for s in pr2['sheets']:
        ts = [q['text'] for q in s['questions']]
        assert len(ts) == len(set(ts)) == 10
    assert len({tuple(q['text'] for q in s['questions']) for s in pr2['sheets']}) == 3
    assert {x['kind'] for x in admin.get(f'/api/paper-exams/{ta}').json()} == {'VIK'}
    assert admin.post(f'/api/paper-exams/{ta}', json={**body, 'variant_mode': 'same_numbers'}).status_code == 200
