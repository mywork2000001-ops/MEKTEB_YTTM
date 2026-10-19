"""«Hər şagirdə öz rəqəmləri» API: yazılı iş (same_numbers), KSQ own_numbers, retake. Domain testi – test_own_numbers.py."""
import datetime as dt

from app.domain.ksq_scan import grade
from app.models import BankFile, BankQuestion, BankSource, ExamVariant, OnlineTask, PlanLesson

from .test_api_portal import as_topic, mk_task, setup
from .test_avto_reqem import QUAD, tr


def _quad_bank(S, key='pq', n=60):
    """Yarısı – sabit mətnli test, yarısı – kvadrat tənlik (müxtəlif köklər)."""
    with S() as db:
        db.add(BankSource(key=key, label=key.upper()))
        db.flush()
        f = BankFile(source_key=key, lesson=f'{key}/q.html', label='Kvadrat fayl', url='http://x', kind='movzu', question_count=n)
        db.add(f)
        db.flush()
        for i in range(n):
            if i % 2 == 0:
                db.add(BankQuestion(file_id=f.id, n=i + 1, kind='mcq', text={'az': f'Sabit sual {i}: paytaxt hansıdır?'}, content_hash=f'q{key}{i}',
                                    options=[{'az': 'Bakı'}, {'az': 'Gəncə'}, {'az': 'Şəki'}], correct=i % 3, diff_auto=['asan', 'orta', 'çətin'][i % 3]))
            else:
                a, b = 1 + i % 5, 6 + i % 7
                db.add(BankQuestion(file_id=f.id, n=i + 1, kind='open', content_hash=f'q{key}{i}', answer=f'{a};{b}',
                                    text={'az': f'$x^2 - {a + b}x + {a * b} = 0$ tənliyinin köklərini artan sırada ";" ilə yazın.'},
                                    diff_auto=['asan', 'orta', 'çətin'][i % 3]))
        db.commit()
        return f.id


def test_paper_same_numbers_free_work(world):
    admin, ta, cid, st, ids = setup(world)
    _, S = world
    fid = _quad_bank(S)
    r = admin.post(f'/api/paper-exams/{ta}', json={'file_ids': [fid], 'n': 10, 'date': '2026-10-05', 'variant_mode': 'same_numbers'})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d['exam']['variant_mode'] == 'numbers' and d['own_numbers']['changed'] >= 1
    pr = admin.get(f'/api/exams/{ta}/{d["exam"]["id"]}/variants/print').json()
    sheets = pr['sheets']
    assert len(sheets) == 3
    quad = [i for i, q in enumerate(sheets[0]['questions']) if 'tənliyinin' in str(q['text'])]
    fixed = [i for i, q in enumerate(sheets[0]['questions']) if 'Sabit sual' in str(q['text'])]
    assert quad and fixed
    for i in quad:                                                   # hər şagirdin öz ədədləri və öz açarı
        assert len({s['questions'][i]['text']['az'] if isinstance(s['questions'][i]['text'], dict) else s['questions'][i]['text']
                    for s in sheets}) == 3
    keys = {k['code']: k['answers'] for k in pr['key']}
    vals = [[a['value'] for a in keys[s['code']]] for s in sheets]
    assert len({v[quad[0]] for v in vals}) == 3
    for i in fixed:                                                  # sabit sual – hamıda eyni mətn
        assert len({str(s['questions'][i]['text']) for s in sheets}) == 1
    # skan qiymətləndirməsi şagirdin öz açarı ilə
    with S() as db:
        vs = {v.student_id: v for v in db.query(ExamVariant).filter_by(exam_id=d['exam']['id'])}
        sids = sorted(vs)
        a, b = vs[sids[0]].questions, vs[sids[1]].questions
        read_a = [{'slot': q['slot'], 'value': (q['answer'] if q['kind'] == 'open' else 'ABCDE'[q['correct']]), 'confidence': 1} for q in a]
        assert grade(a, read_a)['points'] == 100
        assert grade(b, read_a)['points'] < 100                      # başqasının cavabı bu açarla uyğun gəlmir
    assert admin.get(f'/api/exams/{ta}/{d["exam"]["id"]}/variants').json()['own_numbers']['changed'] == d['own_numbers']['changed']


def test_paper_same_numbers_from_task(world):
    admin, ta, cid, st, ids = setup(world)
    _, S = world
    t = mk_task(admin, ta, ids).json()
    as_topic(S, t['id'])
    with S() as db:
        task = db.get(OnlineTask, t['id'])
        task.questions = [dict(task.questions[0]), {'bank_id': None, 'kind': 'open', 'text': QUAD['text'], 'answer': '1;4', 'points': None}]
        db.commit()
    r = admin.post(f'/api/paper-exams/{ta}', json={'task_id': t['id'], 'date': '2026-10-05', 'variant_mode': 'same_numbers'})
    assert r.status_code == 200, r.text
    assert r.json()['own_numbers']['changed'] == 1
    pr = admin.get(f'/api/exams/{ta}/{r.json()["exam"]["id"]}/variants/print').json()
    assert len({str(s['questions'][1]['text']) for s in pr['sheets']}) == 3
    assert len({str(s['questions'][0]['text']) for s in pr['sheets']}) == 1


def _ksq(world):
    admin, ta, cid, st, _ = setup(world)
    _, S = world
    fid = _quad_bank(S, key='p003', n=60)
    with S() as db:
        pl = db.query(PlanLesson).filter_by(assignment_id=ta, seq=3).one()
        pl.topic = 'Kvadrat tənliklər'
        db.add(PlanLesson(assignment_id=ta, seq=9, semester=1, assessment_type='KSQ', exam_no=1, topic='KSQ-1', date=dt.date(2026, 10, 20)))
        db.commit()
    e = admin.post(f'/api/exams/{ta}', json={'kind': 'KSQ', 'no': 1, 'semester': 1, 'date': '2026-10-20', 'max_points': 20}).json()
    return admin, ta, e, fid


def test_ksq_own_numbers_and_retake(world):
    admin, ta, e, fid = _ksq(world)
    r = admin.post(f'/api/exams/{ta}/{e["id"]}/variants', json={'n': 10, 'file_ids': [fid], 'only_mine': True, 'own_numbers': True})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d['own_numbers']['changed'] >= 1 and d['exam']['variant_mode'] == 'numbers'
    vs = d['variants']
    quad = [q['slot'] for q in vs[0]['questions'] if q.get('own_numbers')]
    assert quad
    sl = quad[0]
    txt = lambda v: next(q['text']['az'] for q in v['questions'] if q['slot'] == sl)       # noqa: E731
    assert len({txt(v) for v in vs}) == 3
    assert len({q['key'] for q in vs[0]['questions']} & {q['key'] for q in vs[1]['questions']}) == 10      # eyni suallar
    # retake: eyni suallar, yeni ədədlər, yeni kod
    sid = vs[0]['student_id']
    r2 = admin.post(f'/api/exams/{ta}/{e["id"]}/variants/{sid}/retake')
    assert r2.status_code == 200, r2.text
    new = next(v for v in admin.get(f'/api/exams/{ta}/{e["id"]}/variants').json()['variants'] if v['student_id'] == sid)
    assert new['code'].endswith('R1') and txt(new) != txt(vs[0]) and txt(new) not in {txt(v) for v in vs[1:]}
    assert [q['key'] for q in new['questions']] == [q['key'] for q in sorted(vs[0]['questions'], key=lambda q: q['slot'])]
    # adi rejim dəyişmir
    d2 = admin.post(f'/api/exams/{ta}/{e["id"]}/variants', json={'n': 10, 'file_ids': [fid], 'only_mine': True}).json()
    assert d2['own_numbers'] is None and d2['exam']['variant_mode'] is None
