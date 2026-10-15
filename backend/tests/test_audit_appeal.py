"""Audit (docs/tasks/audit-apelyasiya-sual-altmovzu.md): şagird nəşrdən sonra altmövzu adını görür (texniki kod yox),
müəllim eyni sualı/altmövzunu görür; apelyasiya şagirdin öz variantındakı slota bağlıdır."""
import json

from app.appeals import topic_of
from app.models import BankFile, BankQuestion, ExamAppeal, ExamScan, ExamVariant
from .test_api_portal import student_client
from .test_exam_appeal import _setup


def _label(S, eid, sid, slot=1):
    with S() as db:
        q = next(x for x in db.get(ExamVariant, (eid, sid)).questions if x['slot'] == slot)
        return q, db.get(BankFile, db.get(BankQuestion, q['bank_id']).file_id).label


def test_student_sees_topic_not_code_teacher_sees_same(world, monkeypatch):
    admin, ta, e, pr, who, a, b, c, bid, S = _setup(world, monkeypatch)
    ca = student_client(who[a]['portal_code'], who[a]['initial_pin'])
    assert ca.get(f'/api/portal/exams/{e["id"]}/card').status_code == 403            # nəşrdən əvvəl – heç nə
    admin.put(f'/api/exams/{ta}/{e["id"]}/publish', json={'published': True})
    card = ca.get(f'/api/portal/exams/{e["id"]}/card').json()
    q1, label = _label(S, e['id'], a)
    assert label
    got = next(q for q in card['questions'] if q['slot'] == 1)
    assert got['topic'] == label                                                   # altmövzu adı
    raw = json.dumps(card, ensure_ascii=False)
    assert f'B{bid}' not in raw and 'file_id' not in raw and '"ref"' not in raw and '№' not in raw   # texniki kod yoxdur
    assert all(q['topic'] for q in card['questions'])
    # apelyasiya: şagirdin öz variantındakı slot; müəllim eyni sual + altmövzu + bankdakı №
    assert ca.post(f'/api/portal/exams/{e["id"]}/appeals', json={'slot': 1, 'source': 'paper', 'reason': 'Düzdür'}).status_code == 200
    ap = admin.get(f'/api/exam-appeals/{ta}/{e["id"]}').json()['appeals'][0]
    assert ap['student_id'] == a and ap['slot'] == 1 and ap['topic'] == label
    assert ap['question']['text'] == q1['text'] and ap['bank_id'] == bid
    assert ap['bank_ref']['text'].startswith(label) and f'B{bid}' in ap['bank_ref']['text'] and '№' in ap['bank_ref']['text']
    # b də eyni bank sualını alıb, amma apelyasiya a-nındır: b-nin kartında apelyasiya yoxdur
    cb = student_client(who[b]['portal_code'], who[b]['initial_pin'])
    assert cb.get(f'/api/portal/exams/{e["id"]}/card').json()['appeals'] == []
    with S() as db:
        assert db.query(ExamAppeal).filter_by(exam_id=e['id']).one().student_id == a


def test_lost_slot_no_appeal_and_old_variant_topic(world, monkeypatch):
    admin, ta, e, pr, who, a, b, c, bid, S = _setup(world, monkeypatch)
    admin.put(f'/api/exams/{ta}/{e["id"]}/publish', json={'published': True})
    ca = student_client(who[a]['portal_code'], who[a]['initial_pin'])
    with S() as db:
        sc = db.query(ExamScan).filter_by(exam_id=e['id'], student_id=a, source='paper').one()
        sc.lost = [1]
        v = db.get(ExamVariant, (e['id'], a))
        v.questions = [{k: x for k, x in q.items() if k != 'ref'} for q in v.questions]   # köhnə variant: ref yoxdur
        db.commit()
    assert ca.post(f'/api/portal/exams/{e["id"]}/appeals', json={'slot': 1, 'source': 'paper', 'reason': 'Düzdür'}).status_code == 400
    card = ca.get(f'/api/portal/exams/{e["id"]}/card')
    assert card.status_code == 200 and next(q for q in card.json()['questions'] if q['slot'] == 1)['topic']


def test_topic_of_template_and_missing(world):
    _, S = world
    with S() as db:
        assert topic_of(db, {'template': 'T7', 'lesson': 'Çoxhədlilər'}) == 'Çoxhədlilər'
        assert topic_of(db, {'topic_actual': 'Funksiya'}) == 'Funksiya'
        assert topic_of(db, {}) is None
