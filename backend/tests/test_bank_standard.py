"""M8: bank sualında standart – miqrasiya, doldurma skripti (quru rejim / --apply), «Standartlar üzrə» hesabatda sualın standartı."""
import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

from app.models import BankFile, BankQuestion, BankSource, Mark, OnlineTask, PlanLesson, TaskAttempt
from tools import fill_bank_standards as fbs

from .test_api_portal import as_topic, mk_task, setup
from .test_journal_audit import _now, _put

BACKEND = Path(__file__).resolve().parent.parent


def test_migration_adds_and_drops_column(tmp_path):
    """alembic upgrade head → sütun var; downgrade -1 → yoxdur; yenidən upgrade → var (məlumat itmir)."""
    url = f'sqlite:///{(tmp_path / "m.db").as_posix()}'
    env = {**os.environ, 'MK_DATABASE_URL': url, 'MK_BANK_SYNC_MINUTES': '0'}

    def run(*args):
        r = subprocess.run([sys.executable, '-m', 'alembic', *args], cwd=BACKEND, env=env, capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
        assert r.returncode == 0, r.stderr[-800:]

    def cols():
        return {c['name'] for c in inspect(create_engine(url)).get_columns('bank_questions')}
    run('upgrade', 'head')
    assert 'standard' in cols()
    run('downgrade', 'c4e8a2f6b1d9')      # d5a9c3e7b1f4-dən əvvəlki (sonrakı miqrasiyalar da geri qayıdır)
    assert 'standard' not in cols()
    run('upgrade', 'head')
    assert 'standard' in cols()


def _bank(db):
    if db.get(BankSource, 'sx') is None:
        db.add(BankSource(key='sx', label='SX'))
    files = []
    for lesson in ('a', 'b', 'c', 'd'):
        f = BankFile(source_key='sx', lesson=lesson, label=lesson, url='u', question_count=2)
        db.add(f)
        db.flush()
        for n in (1, 2):
            db.add(BankQuestion(file_id=f.id, n=n, kind='open', text={'az': 'q'}, answer='1', content_hash=f'{lesson}{n}'))
        files.append(f)
    db.commit()
    return [f.id for f in files]


def test_fill_dry_run_and_apply(world):
    with world[1]() as db:
        fa, fb, fc, fd = _bank(db)
        db.query(BankQuestion).filter_by(file_id=fd, n=1).one().standard = '7.7.7'      # artıq dolu – toxunulmaz
        db.commit()
        mapping = {fa: {'1.1.1'}, fb: {'1.1.2', '1.1.3'}, fd: {'4.4.4'}}                # fc – uyğunluq yoxdur
        p = fbs.plan(db, mapping)
        assert (p['filled'], p['ambiguous'], p['no_mapping']) == (2 + 1, 2, 2) and p['fill'] == {fa: '1.1.1', fd: '4.4.4'}
        # quru rejim: plan() yazmır
        assert db.query(BankQuestion).filter(BankQuestion.standard.is_not(None)).count() == 1
        assert fbs.apply(db, p['fill']) == 3
        got = {(q.file_id, q.n): q.standard for q in db.query(BankQuestion)}
        assert got[(fa, 1)] == got[(fa, 2)] == '1.1.1' and got[(fb, 1)] is None and got[(fc, 2)] is None
        assert got[(fd, 1)] == '7.7.7' and got[(fd, 2)] == '4.4.4'
        p2 = fbs.plan(db, mapping)                                                      # təkrar – idempotent
        assert p2['filled'] == 0 and fbs.apply(db, p2['fill']) == 0


def test_fill_main_default_is_dry(world, monkeypatch, capsys):
    with world[1]() as db:
        fa, *_ = _bank(db)
    monkeypatch.setattr(fbs, 'collect', lambda db: {fa: {'1.1.1'}})
    monkeypatch.setattr('app.db.SessionLocal', world[1])
    assert fbs.main([]) == 0
    assert 'QURU REJİM' in capsys.readouterr().out
    with world[1]() as db:
        assert db.query(BankQuestion).filter(BankQuestion.standard.is_not(None)).count() == 0
    assert fbs.main(['--apply']) == 0
    with world[1]() as db:
        assert db.query(BankQuestion).filter(BankQuestion.standard == '1.1.1').count() == 2


def test_report_prefers_question_standard(world, monkeypatch):
    """Sualın öz standartı hesabatda dərsin standartından üstündür; standartsız suallar – köhnə yol (dərs)."""
    _now(monkeypatch)
    c, ta, cid, st, ids = setup(world)
    a = st[0]['id']
    with world[1]() as db:
        db.query(PlanLesson).filter_by(assignment_id=ta, seq=5).one().standards = ['2.1.1']
        for i in ids[:2]:
            db.get(BankQuestion, i).standard = '9.9.9'
        db.commit()
    t = mk_task(c, ta, ids, opens_at='2026-09-29T05:00:00Z', closes_at='2026-09-29T06:00:00Z').json()
    as_topic(world[1], t['id'])
    assert _put(c, ta, {'date': '2026-09-29', 'period': 1, 'attendance': {a: 'var'},
                        'marks': [{'student_id': a, 'kind': 'test', 'test_correct': 1, 'test_total': 3}]}).status_code == 200
    with world[1]() as db:
        for m in db.query(Mark).filter_by(kind='test'):
            m.task_id = t['id']
        task = db.get(OnlineTask, t['id'])
        order = [q['bank_id'] for q in task.questions]
        ans = {}
        for i, bid in enumerate(order):        # ilk iki (9.9.9) düz, standartsız sonuncu səhv
            q = db.get(BankQuestion, bid)
            ans[str(i)] = q.correct if q.kind == 'mcq' else q.answer
        last = next(i for i, bid in enumerate(order) if bid == ids[2])
        ans[str(last)] = 1 if db.get(BankQuestion, ids[2]).correct == 0 else 0
        db.add(TaskAttempt(task_id=t['id'], student_id=a, deadline=dt.datetime(2026, 9, 29, 6, tzinfo=dt.timezone.utc), order=list(range(3)),
                           answers=ans, submitted_at=dt.datetime(2026, 9, 29, 5, 30, tzinfo=dt.timezone.utc), correct=2, total=3))
        db.commit()
    s = c.get(f'/api/journal/{ta}/standards', params={'semester': 1}).json()
    std = {x['standard']: x for x in s['standards']}
    assert std['9.9.9']['source'] == 'question' and std['9.9.9']['students'][0]['pct'] == 100.0
    assert std['2.1.1']['source'] == 'lesson' and std['2.1.1']['students'][0]['pct'] == 0.0      # yalnız standartsız sual (səhv)
    assert s['topics'][0]['topic'] == 'Kvadrat tənliklər' and abs(s['topics'][0]['students'][0]['pct'] - 33.3) < 0.1   # mövzu – köhnə


def test_report_without_question_standard_unchanged(world, monkeypatch):
    _now(monkeypatch)
    c, ta, cid, st, ids = setup(world)
    a = st[0]['id']
    with world[1]() as db:
        db.query(PlanLesson).filter_by(assignment_id=ta, seq=5).one().standards = ['2.1.1']
        db.commit()
    t = mk_task(c, ta, ids, opens_at='2026-09-29T05:00:00Z', closes_at='2026-09-29T06:00:00Z').json()
    as_topic(world[1], t['id'])
    assert _put(c, ta, {'date': '2026-09-29', 'period': 1, 'attendance': {a: 'var'},
                        'marks': [{'student_id': a, 'kind': 'test', 'test_correct': 8, 'test_total': 10}]}).status_code == 200
    with world[1]() as db:
        for m in db.query(Mark).filter_by(kind='test'):
            m.task_id = t['id']
        db.commit()
    std = c.get(f'/api/journal/{ta}/standards', params={'semester': 1}).json()['standards']
    assert std[0]['standard'] == '2.1.1' and std[0]['source'] == 'lesson' and std[0]['students'][0]['pct'] == 80.0
