"""«Bu KSQ əsasında sınaq» (docs/tasks/ksq-den-sinaq-2026-10-21.md): GET /api/exams/{ta}/{exam}/as-sinaq – plan_tests.analog_pick."""
import datetime as dt

from app.models import BankQuestion, ExamVariant, OnlineTask, User

from .test_ksq_scan import ksq


def _used(S, exam_id):
    with S() as db:
        vs = db.query(ExamVariant).filter_by(exam_id=exam_id).order_by(ExamVariant.code).all()
        used = {q['bank_id'] for v in vs for q in v.questions if q.get('bank_id')}
        first = [q['bank_id'] for q in sorted(vs[0].questions, key=lambda q: q['slot']) if q.get('bank_id')]
        return len(vs[0].questions), used, first


def test_analog_excludes_ksq_and_given(world):
    admin, ta, e, _ = ksq(world)
    _, S = world
    n, used, first = _used(S, e['id'])
    assert first and len(first) == n
    r = admin.get(f'/api/exams/{ta}/{e["id"]}/as-sinaq')                       # defolt – analoji
    assert r.status_code == 200, r.text
    d = r.json()
    assert d['title'].endswith('– sınaq') and d['targets'] == [{'ta_id': ta}] and d['mode'] == 'analog'
    assert len(d['bank_ids']) == n == d['total'] and d['missing'] == [] and len(d['questions']) == n
    assert not set(d['bank_ids']) & used and len(set(d['bank_ids'])) == n
    with S() as db:                                                             # alt mövzu (fayl) uyğundur
        fid = {q.file_id for q in db.query(BankQuestion).filter(BankQuestion.id.in_(first))}
        assert {q.file_id for q in db.query(BankQuestion).filter(BankQuestion.id.in_(d['bank_ids']))} == fid
        # əvvəl verilmiş sınaq sualları çıxılır
        uid = db.query(User).filter_by(login='admin').one().id
        db.add(OnlineTask(assignment_id=ta, title='x', questions=[{'bank_id': i} for i in d['bank_ids']], kind='sinaq', created_by=uid, duration_min=0,
                          opens_at=dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc), closes_at=dt.datetime(2026, 10, 2, tzinfo=dt.timezone.utc)))
        db.commit()
    d2 = admin.get(f'/api/exams/{ta}/{e["id"]}/as-sinaq', params={'mode': 'analog'}).json()
    assert len(d2['bank_ids']) == n
    assert not set(d2['bank_ids']) & (used | set(d['bank_ids']))


def test_same_and_permissions(world):
    admin, ta, e, _ = ksq(world)
    as_, S = world
    _, used, first = _used(S, e['id'])
    d = admin.get(f'/api/exams/{ta}/{e["id"]}/as-sinaq', params={'mode': 'same'}).json()
    assert d['bank_ids'] == first and d['missing'] == [] and d['mode'] == 'same'
    assert admin.get(f'/api/exams/{ta}/{e["id"]}/as-sinaq', params={'mode': 'x'}).status_code == 422
    assert as_('yad').get(f'/api/exams/{ta}/{e["id"]}/as-sinaq').status_code == 404
    assert admin.get(f'/api/exams/{ta}/999999/as-sinaq').status_code == 404


def test_analog_engine_option(world):
    """Mühərrik: Opts.analog_of → r_analog (RESOLVERS-də ilk)."""
    from app import plan_tests as E
    from app.models import TeachingAssignment
    admin, ta, e, _ = ksq(world)
    _, S = world
    with S() as db:
        c = E.TaCtx(db, db.get(TeachingAssignment, ta))
        ch = E.r_analog(c, None, E.Opts(analog_of=e['id']))
        assert ch.status == 'ok' and ch.count == len(ch.questions) > 0
        assert E.r_analog(c, None, E.Opts()) is None
