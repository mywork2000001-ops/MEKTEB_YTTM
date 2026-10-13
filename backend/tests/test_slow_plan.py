"""Zəif qrup tempi (docs/x-e-zeif-qrup-tempi-promtu.md)."""
import datetime as dt

from app.models import PlanLesson, PlanProgram, TeachingAssignment

from .test_api_portal import setup


def _plan(S, ta, n1=60, n2=50):
    with S() as db:
        db.query(PlanLesson).filter_by(assignment_id=ta).delete()
        seq = 0
        for sem, n in ((1, n1), (2, n2)):
            for i in range(n):
                seq += 1
                sec = f'{"I" if sem == 1 else "XIX"} BÖLMƏ – B{sem}{i // 10}'
                typ = 'KSQ' if i % 12 == 11 else 'formativ'
                db.add(PlanLesson(assignment_id=ta, seq=seq, semester=sem, section=sec, topic=f'Mövzu {sem}-{i}', standards=[],
                                  assessment_type=typ, exam_no=(i // 12 + 1) if typ == 'KSQ' else None, date=dt.date(2026, 9, 15), tasks=[]))
        db.commit()


def test_slow_plan_preview_and_apply(world):
    as_, S = world
    admin, ta, cid, st, _ = setup(world)
    _plan(S, ta, n1=24, n2=20)
    keep = dt.date(2026, 9, 30)
    r = admin.post(f'/api/programs/slow/{ta}', json={'keep_until': str(keep)})
    assert r.status_code == 200, r.text
    d = r.json()
    from app.programs import capacity
    with S() as db:
        cap = capacity(db, db.get(TeachingAssignment, ta))
        past_n = sum(1 for x, _ in cap['slots'] if x <= keep)
        old = [pl.topic for pl in db.query(PlanLesson).filter_by(assignment_id=ta).order_by(PlanLesson.seq)][:past_n]
    assert d['kept_past'] == past_n and [x['topic'] for x in d['preview'][:past_n]] == old       # keçmiş toxunulmur
    assert d['lessons'] == len(cap['slots'])                                                       # yuva = dərs
    assert d['practice'] > 0 and d['restore'] > 0 and d['bsq'] == 2
    assert d['section_review'] > 0 and d['spiral'] > 0 and d['ksq_prep'] == d['ksq'] - sum(1 for x in d['preview'][:past_n] if x['type'] == 'KSQ')
    for i, x in enumerate(d['preview']):                                            # hər yeni KSQ-dən əvvəl hazırlıq
        if i >= past_n and x['type'] == 'KSQ':
            assert d['preview'][i - 1]['topic'].startswith('KSQ-yə hazırlıq')
    types = [x['type'] for x in d['preview']]
    assert d['preview'][-1]['type'] == 'BSQ'
    ksq = [x['topic'] for x in d['preview'] if x['type'] == 'KSQ']
    assert all(t.startswith(f'KSQ-{i + 1}') or 'KSQ' in t for i, t in enumerate(ksq))
    r = admin.post(f'/api/programs/slow/{ta}', json={'keep_until': str(keep), 'apply': True})
    assert r.status_code == 200, r.text
    with S() as db:
        t = db.get(TeachingAssignment, ta)
        p1, p2 = db.get(PlanProgram, r.json()['program_id']), db.get(PlanProgram, r.json()['year2_program_id'])
        assert t.program_id == p1.id and p1.level == 'Zəif' and len(p2.data['lessons']) > 0
        n = db.query(PlanLesson).filter_by(assignment_id=ta).count()
        assert n == len(cap['slots'])
