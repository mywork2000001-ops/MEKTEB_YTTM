"""docs/sinaq-tarix-sinif-tekrar-promtu.md: sınağın tarixi etiketdən, məzmuna görə təkrar yoxlaması, köhnə təkrar
paketlərin birləşdirilməsi (miqrasiya)."""
import datetime as dt

from app.api.exams_online import merge_resend_batches
from app.bank.classify import held_from_label
from app.models import AuditLog, BankFile, BankQuestion, OnlineTask, TestBatch

from .test_api_exam_audit import _two_classes
from .test_api_portal import UTC, clock  # noqa: F401 – clock fixture


def test_held_from_label():
    assert held_from_label('2026 · OTK — Buraxılış sınaq imtahanı №1 (IX sinif, 27.09.2026)') == (dt.date(2026, 9, 27), 'day')
    assert held_from_label('2026 · OBM — Çoxluqlar (Variant A) (Çoxluqlar, sentyabr 2026)') == (dt.date(2026, 9, 1), 'month')
    assert held_from_label('2022 · Riyaziyyat RF — Buraxılış MS1 (Variant A) (Buraxılış, tarix göstərilməyib)') == (dt.date(2022, 1, 1), 'year')
    assert held_from_label('ÜSİ-3') == (None, None) and held_from_label('31.02.2026')[1] == 'year'


def test_lessons_api_has_date(world, clock, monkeypatch):
    admin, ta, ta_c, st, xs, bid, tid = _two_classes(world, clock, monkeypatch)
    with world[1]() as db:
        f = db.query(BankFile).one()
        f.label = 'ÜSİ-1 (X sinif, 27.09.2026)'
        from app.bank.classify import apply
        apply(f)
        db.commit()
    les = admin.get('/api/bank/lessons', params={'source': 'p012'}).json()
    assert (les[0]['held_on'], les[0]['held_prec']) == ('2026-09-27', 'day')


def test_repeat_detected_by_content_after_file_move(world, clock, monkeypatch):
    """Viktorinada fayl yerini dəyişib (yeni fayl, eyni suallar) – əvvəl verilmiş sınaq yenə «verilib» sayılır."""
    admin, ta, ta_c, st, xs, bid, tid = _two_classes(world, clock, monkeypatch)
    with world[1]() as db:
        old = db.query(BankFile).one()
        old.kind = 'sinaq'
        long = {}                                  # real sınaq sualları uzundur (qısa mətn təsadüfən üst-üstə düşməsin)
        for q in db.query(BankQuestion).filter_by(file_id=old.id).all():
            long[q.text['az']] = {'az': f'Sual {q.n}: tənliyi həll edin və cavabı göstərin – {q.text["az"]}'}
            q.text = long[q.text['az']]
        t = db.get(OnlineTask, tid[ta])
        t.questions = [{**x, 'text': long[x['text']['az']]} for x in t.questions]
        new = BankFile(source_key='p012', lesson='2026/usi-1.html', label='ÜSİ-1 (yeni yer)', url='http://x/2026/usi-1.html',
                       grades=[10], kind='sinaq', question_count=3)
        db.add(new)
        db.flush()
        for q in db.query(BankQuestion).filter_by(file_id=old.id).all():
            db.add(BankQuestion(file_id=new.id, n=q.n, kind=q.kind, text=q.text, options=q.options, correct=q.correct,
                                answer=q.answer, content_hash=q.content_hash + 'x'))
        old.active = False
        db.commit()
        new_ids = [q.id for q in db.query(BankQuestion).filter_by(file_id=new.id).order_by(BankQuestion.n)]
    win = {'opens_at': '2026-09-30T11:00:00Z', 'closes_at': '2026-09-30T12:00:00Z'}
    r = admin.post('/api/exams-online', json={'title': 'Başqa ad', 'bank_ids': new_ids, 'targets': [{'ta_id': ta, **win}]})
    assert r.status_code == 409 and r.json()['detail']['repeat']
    given = admin.get('/api/exams-online/given', params={'ta_ids': str(ta)}).json()
    assert any(v['full'] for v in given.values())


def test_merge_old_resend_batches(world, clock, monkeypatch):
    """Köhnə «Yenidən göndər» – ayrıca paket idi; miqrasiya onu mənbə sınağına birləşdirir."""
    admin, ta, ta_c, st, xs, bid, tid = _two_classes(world, clock, monkeypatch)
    S = world[1]
    with S() as db:
        src = db.get(OnlineTask, tid[ta])
        b2 = TestBatch(kind='sinaq', title=src.title, subject='Riyaziyyat', grade=10)
        db.add(b2)
        db.flush()
        cp = OnlineTask(assignment_id=ta, title=src.title, opens_at=src.opens_at, closes_at=src.closes_at, duration_min=20,
                        questions=src.questions, kind='sinaq', batch_id=b2.id, student_ids=[st[1]['id']])
        db.add(cp)
        db.flush()
        db.add(AuditLog(entity='task', action='create', entity_id=str(cp.id), details={'copied_from': src.id}))
        db.commit()
        cid, b2id = cp.id, b2.id
    assert len(admin.get('/api/exams-online').json()) == 2
    with S() as db:
        assert merge_resend_batches(db.connection()) == 1
        db.commit()
        assert db.get(OnlineTask, cid).batch_id == bid and db.get(TestBatch, b2id) is None
    assert [x['id'] for x in admin.get('/api/exams-online').json()] == [bid]
