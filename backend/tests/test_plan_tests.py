"""Vahid mühərrik app/plan_tests.py (docs/plan-testleri-skripti-promtu.md §3): quru rejim, dublikatsızlıq, sinfə görə mənbə,
IX toplu (P007), əl ilə seçim, əhatə (müəllim/admin/fərdi məkan), auto_tests.run, API, skript."""
import datetime as dt

import pytest

from app import plan_tests as E
from app.models import (AuditLog, BankFile, BankQuestion, BankSource, LessonBankLink, OnlineTask, PlanLesson, School, SchoolClass,
                        TeachingAssignment, User)

from .test_api_programs_toplu import _bank_world


@pytest.fixture
def day(monkeypatch):
    d = [dt.date(2026, 10, 19)]
    for m in ('app.plan_tests', 'app.auto_tests'):
        monkeypatch.setattr(f'{m}.today', lambda: d[0])
    monkeypatch.setattr('app.plan_tests.now', lambda: dt.datetime.combine(d[0], dt.time(9, 0), tzinfo=dt.timezone.utc))
    return d


def _bank(S, rows, sources=('p001', 'p003', 'p013')):
    with S() as db:
        db.add_all([BankSource(key=k, label=k) for k in sources]); db.flush()
        for src, lesson, label, grades in rows:
            f = BankFile(source_key=src, lesson=lesson, label=label, url='http://x/' + lesson, kind='movzu', question_count=20, grades=grades)
            db.add(f); db.flush()
            for i in range(1, 21):
                db.add(BankQuestion(file_id=f.id, n=i, qid=str(i), kind='mcq', text={'az': f'S{i}'}, options=[{'az': '1'}, {'az': '2'}],
                                    correct=0, content_hash=f'{lesson}{i}'))
        db.commit()
        return {f.lesson: f.id for f in db.query(BankFile)}


def _class(admin, S, name, topics, slots=None, user=None):
    cid = admin.post('/api/classes', json={'name': name}).json()['id']
    slots = slots or {'3': [2]}
    r = admin.post(f'/api/classes/{cid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': sum(len(v) for v in slots.values()), 'slots': slots})
    assert r.status_code == 200, r.text
    with S() as db:
        ta = db.query(TeachingAssignment).filter_by(class_id=cid).one()
        for i, (t, typ, sec) in enumerate(topics):
            db.add(PlanLesson(assignment_id=ta.id, seq=i + 1, semester=1, assessment_type=typ, topic=t, section=sec, date=dt.date(2026, 9, 17)))
        db.commit()
        return ta.id


def _assign(S, tas, d1, d2, apply=False, **kw):
    with S() as db:
        return E.assign(db, None, [db.get(TeachingAssignment, t) for t in tas], d1, d2, E.Opts(**kw), apply=apply)


def _count(S):
    with S() as db:
        return db.query(OnlineTask).count()


def test_defaults_and_dry_run_no_writes(world, day):
    """0/1. Defolt 45 dəq.; quru rejim DB-yə yazmır, statuslar düzgün (ok/none/summative/past)."""
    as_, S = world
    admin = as_('admin')
    assert E.Opts().norm().duration == 0 and E.Opts(duration=20).norm().duration == 45
    _bank(S, [('p003', 'a', 'Tənliklər — Kvadrat tənliklər', None)])
    # Ç.a. 2-ci saat: 17.09, 24.09, 01.10, 08.10, 15.10 (keçib), 22.10, 29.10, 05.11
    ta = _class(admin, S, 'X a', [('Mövzu A', 'formativ', None), ('B', 'formativ', None), ('C', 'formativ', None), ('D', 'formativ', None),
                                  ('E', 'formativ', None), ('Kvadrat tənliklər', 'formativ', None), ('KSQ-1: x', 'KSQ', None),
                                  ('Loqarifm funksiyası', 'formativ', None)])
    before = _count(S)
    rep = _assign(S, [ta], dt.date(2026, 10, 19), dt.date(2026, 12, 31))
    assert _count(S) == before and not rep.applied
    st = {r['topic']: r for r in rep.rows}
    assert st['Kvadrat tənliklər']['status'] == 'ok' and st['Kvadrat tənliklər']['will_create'] and st['Kvadrat tənliklər']['questions'] == 15
    assert st['KSQ-1: x']['status'] == 'summative' and st['Loqarifm funksiyası']['status'] == 'none'
    assert not st['Loqarifm funksiyası']['will_create']
    assert _assign(S, [ta], dt.date(2026, 9, 1), dt.date(2026, 10, 18)).rows[0]['status'] == 'past'


def test_apply_twice_no_duplicates_and_times(world, day):
    """2. --apply iki dəfə: ikinci dəfə 0 yeni test. Test dərsin sonunda açılır, ertəsi gün 22:00 bağlanır, 45 dəq."""
    as_, S = world
    admin = as_('admin')
    _bank(S, [('p003', 'a', 'Tənliklər — Kvadrat tənliklər', None)])
    ta = _class(admin, S, 'X b', [('A', 'formativ', None), ('B', 'formativ', None), ('C', 'formativ', None), ('D', 'formativ', None),
                                  ('E', 'formativ', None), ('F', 'formativ', None), ('Kvadrat tənliklər', 'formativ', None)])
    r1 = _assign(S, [ta], dt.date(2026, 10, 19), dt.date(2026, 12, 31), apply=True)
    assert sum(r['created'] for r in r1.rows) == 1
    r2 = _assign(S, [ta], dt.date(2026, 10, 19), dt.date(2026, 12, 31), apply=True)
    assert sum(r['created'] for r in r2.rows) == 0 and any(r['status'] == 'has_test' for r in r2.rows)
    with S() as db:
        t = db.query(OnlineTask).one()
        assert t.duration_min == 0 and t.closes_at.year == 2100 and t.kind == 'movzu' and t.journal_auto and len(t.questions) == 15 and t.shuffle
        assert t.show_answers == 'after_submit'                   # müddətsiz mövzu testi: izah təhvildən dərhal sonra
        pl = db.get(PlanLesson, t.plan_lesson_id)
        assert pl.topic == 'Kvadrat tənliklər'
        assert db.query(AuditLog).filter_by(entity='plan_tests').count() == 1


def test_topic_group_one_test_on_last_lesson(world, day):
    """Fərdi görüş planı: 1-ci saat «Nəzəri xülasə», 2-ci saat «Sinif testi və təhlil» – bir mövzuya bir test, sonuncu dərsə."""
    as_, S = world
    admin = as_('admin')
    _bank(S, [('p003', 'a', 'Tənliklər — Kvadrat tənliklər', None)])
    ta = _class(admin, S, 'X c', [('X sinif: Kvadrat tənliklər. Nəzəri xülasə və nümunə məsələlər', 'formativ', '2. Tənliklər'),
                                  ('X sinif: Kvadrat tənliklər. Sinif testi və təhlil', 'formativ', '2. Tənliklər')], {'3': [2, 3]})
    rep = _assign(S, [ta], dt.date(2026, 9, 1), dt.date(2026, 12, 31), apply=True, missing=True)
    made = [r for r in rep.rows if r['created']]
    assert len(rep.rows) == 1 and len(made) == 1 and made[0]['seq'] == 2 and made[0]['topic_no'] == '2.1'


def test_missing_mode(world, day):
    """0. --missing: keçilmiş testsiz dərsə «indi → +3 gün 22:00» testi; testi olan keçilmiş dərsə toxunulmur."""
    as_, S = world
    admin = as_('admin')
    _bank(S, [('p003', 'a', 'Tənliklər — Kvadrat tənliklər', None), ('p003', 'b', 'Funksiya — Funksiya anlayışı', None)])
    ta = _class(admin, S, 'X d', [('Kvadrat tənliklər', 'formativ', None), ('Funksiya anlayışı', 'formativ', None)])
    with S() as db:
        pl2 = db.query(PlanLesson).filter_by(assignment_id=ta, seq=2).one().id
        db.add(OnlineTask(assignment_id=ta, title='əl ilə', opens_at=dt.datetime(2026, 9, 20, tzinfo=dt.timezone.utc),
                          closes_at=dt.datetime(2026, 9, 21, tzinfo=dt.timezone.utc), duration_min=45, questions=[], kind='movzu',
                          plan_lesson_id=pl2, created_by=1))
        db.commit()
    rep = _assign(S, [ta], None, dt.date(2026, 10, 19), apply=True, missing=True, missing_close_days=3, duration=45)
    by = {r['seq']: r for r in rep.rows}
    assert by[1]['status'] == 'missing' and by[1]['created'] and by[2]['status'] == 'has_test'
    with S() as db:
        t = db.query(OnlineTask).filter_by(plan_lesson_id=db.query(PlanLesson).filter_by(assignment_id=ta, seq=1).one().id).one()
        assert t.opens_at.replace(tzinfo=None) == dt.datetime(2026, 10, 19, 9, 0)
        assert t.closes_at.replace(tzinfo=None) == dt.datetime(2026, 10, 22, 18, 0)           # 22:00 Bakı = 18:00 UTC
        assert t.duration_min == 45 and t.show_answers == 'after_close'     # müddətli test: dəyişmir


def test_low_grade_uses_own_bank_and_pending(world, day):
    """3. V sinif öz sinfinin faylından test alır (T2 düzəlişi); faylı olmayan mövzu VII-də 'pending'; X-də 'none'."""
    as_, S = world
    admin = as_('admin')
    _bank(S, [('p001', 'v', 'Natural ədədlər', [5])])
    t5 = _class(admin, S, 'V a', [('Natural ədədlər', 'formativ', None)])
    t7 = _class(admin, S, 'VII a', [('Natural ədədlər', 'formativ', None)])
    t10 = _class(admin, S, 'X e', [('Loqarifm', 'formativ', None)])
    rep = _assign(S, [t5, t7, t10], None, dt.date(2026, 12, 31), apply=True, missing=True)
    st = {r['class_name']: r['status'] for r in rep.rows}
    assert st == {'V a': 'missing', 'VII a': 'pending', 'X e': 'none'} and sum(r['created'] for r in rep.rows) == 1
    assert next(s for s in rep.summary() if s['class_name'] == 'VII a')['pending'] == 1


def test_toplu_p007_regression(world, day):
    """4. IX «Test toplusu» dərsi – P007 aralığı (köhnə davranış)."""
    admin, ta, pls = _bank_world(world)
    as_, S = world
    day[0] = dt.date(2026, 9, 14)
    rep = _assign(S, [ta], dt.date(2026, 9, 14), dt.date(2026, 12, 31), apply=True)
    r1 = next(r for r in rep.rows if r['plan_lesson_id'] == pls[0])
    assert r1['status'] == 'ok' and r1['source'] == 'p007' and r1['created'] and r1['questions'] == 26      # S 1–14 + E 15–24 + M 25–27 (16 deaktiv)
    with S() as db:
        t = db.query(OnlineTask).filter_by(plan_lesson_id=pls[0]).one()
        assert all('qid' not in q for q in t.questions) and t.duration_min == 0


def test_manual_wins_and_none_choice(world, day):
    day[0] = dt.date(2026, 9, 14)
    """5. Əl ilə seçilmiş fayl üstündür; «Test yoxdur» seçimi – test yaranmır; əl ilə yaradılmış test – has_test."""
    as_, S = world
    admin = as_('admin')
    ids = _bank(S, [('p003', 'a', 'Tənliklər — Kvadrat tənliklər', None), ('p003', 'b', 'Funksiya — Funksiya anlayışı', None)])
    ta = _class(admin, S, 'X f', [('Kvadrat tənliklər', 'formativ', None), ('Funksiya anlayışı', 'formativ', None)])
    with S() as db:
        p1, p2 = (db.query(PlanLesson).filter_by(assignment_id=ta, seq=i).one().id for i in (1, 2))
        db.add_all([LessonBankLink(plan_lesson_id=p1, file_id=ids['b'], set_by=1), LessonBankLink(plan_lesson_id=p2, file_id=None, set_by=1)])
        db.commit()
    rep = _assign(S, [ta], None, dt.date(2026, 12, 31), apply=True, missing=True)
    by = {r['seq']: r for r in rep.rows}
    assert by[1]['status'] == 'manual' and by[1]['source'] == 'p003' and by[1]['created'] and by[1]['file'] == 'Funksiya — Funksiya anlayışı'
    assert by[2]['status'] == 'none' and not by[2]['created']


def test_scope_teacher_admin_private(world):
    """6. Müəllim yalnız öz dərslərini, admin məktəbin dərslərini görür; fərdi məkan admin 'hamısı'na düşmür."""
    as_, S = world
    admin, ilqar = as_('admin'), as_('ilqar')
    ta_a = _class(admin, S, 'X g', [('A', 'formativ', None)])
    ta_i = _class(ilqar, S, 'X h', [('A', 'formativ', None)])
    with S() as db:
        a, i, y = (db.query(User).filter_by(login=x).one() for x in ('admin', 'ilqar', 'yad'))
        priv = School(name='Fərdi', kind='private', owner_id=i.id)
        db.add(priv); db.flush()
        yr = db.query(SchoolClass).first().year_id
        pc = SchoolClass(school_id=priv.id, year_id=yr, name='Fərdi sinif', code='FS', kind='adi')
        db.add(pc); db.flush()
        db.add(TeachingAssignment(teacher_id=i.id, class_id=pc.id, subject='Riyaziyyat', weekly_hours=1, slots={'3': [1]}))
        db.commit()
        ids = lambda tas: sorted(t.id for t in tas)
        assert ids(E.scope_tas(db, i, everything=True)) == [ta_i]
        assert ids(E.scope_tas(db, a, everything=True)) == sorted([ta_a, ta_i])
        assert E.scope_tas(db, a) == [] and len(E.scope_system(db, everything=True)) == 2
        assert len(E.scope_system(db, ta_ids=[t.id for t in db.query(TeachingAssignment).all()])) == 3
        assert ids(E.scope_tas(db, a, teacher_id=i.id, everything=True)) == [ta_i]


def test_auto_tests_run_uses_engine(world, day):
    """7. auto_tests.run mühərrik vasitəsilə: yalnız auto_tests açıq sinif; ikinci çağırış 0."""
    from app.auto_tests import run
    as_, S = world
    admin = as_('admin')
    _bank(S, [('p003', 'a', 'Tənliklər — Kvadrat tənliklər', None)])
    ta = _class(admin, S, 'X i', [('A', 'formativ', None)] * 0 + [('Kvadrat tənliklər', 'formativ', None)])
    day[0] = dt.date(2026, 9, 17)
    with S() as db:
        assert run(db, day[0]) == 0
        db.get(TeachingAssignment, ta).auto_tests = True
        db.commit()
        assert run(db, day[0]) == 1 and run(db, day[0]) == 0


def test_api_preview_assign_and_script(world, day, capsys):
    """2.2/2.3: API önbaxış yazmır, təsdiq yaradır; skript quru rejimdə yazmır, --apply --yes yaradır, CSV verir."""
    as_, S = world
    admin = as_('admin')
    _bank(S, [('p003', 'a', 'Tənliklər — Kvadrat tənliklər', None)])
    ta = _class(admin, S, 'X j', [('Kvadrat tənliklər', 'formativ', None)])
    body = {'ta_ids': [ta], 'date_from': '2026-09-01', 'date_to': '2026-12-31', 'opts': {'missing': True}}
    p = admin.post('/api/plan-tests/preview', json=body).json()
    assert p['will_create'] == 1 and p['created'] == 0 and _count(S) == 0
    assert as_('yad').post('/api/plan-tests/preview', json=body).status_code == 404
    assert admin.post('/api/plan-tests/preview', json={}).status_code == 400
    a = admin.post('/api/plan-tests/assign', json=body).json()
    assert a['created'] == 1 and _count(S) == 1 and admin.post('/api/plan-tests/assign', json=body).json()['created'] == 0

    from scripts.plan_tests import main
    ta2 = _class(admin, S, 'X k', [('Kvadrat tənliklər', 'formativ', None)])
    with S() as db:
        assert main(['--ta', str(ta2), '--missing'], db=db) == 0
        assert 'QURU REJİM: 1 test' in capsys.readouterr().out and _count(S) == 1
        assert main(['--ta', str(ta2), '--missing', '--apply', '--yes', '--out', 'plan_tests_out.csv'], db=db) == 0
    assert _count(S) == 2
    import os
    os.remove('plan_tests_out.csv')
    out = capsys.readouterr().out
    assert 'Yaradıldı: 1' in out
