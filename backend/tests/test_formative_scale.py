"""Metodik audit M6: formativ şkala sinif üzrə (mövzu testi); defolt = KSQ şkalası, KSQ/sınaq dəyişmir."""
from sqlalchemy import select

from app.api.tasks import score
from app.domain.rules import GRADE_BANDS, formative_grade, level, normalize_scale, summative_grade, validate_scale
from app.models import OnlineTask, TaskAttempt, TeachingAssignment

from .test_api_portal import mk_task, setup  # noqa: F401


def test_default_scale_identical_to_ksq_bands():
    """Regressiya: defolt şkala bütün 0–100 faizdə summative_grade ilə eynidir."""
    for tenth in range(0, 1001):
        p = tenth / 10
        assert formative_grade(p) == summative_grade(p, GRADE_BANDS), p
        assert formative_grade(p, None) == formative_grade(p, {3: 31, 4: 61, 5: 81})


def test_custom_scale_and_normalize():
    sc = {3: 40, 4: 70, 5: 90}
    assert [formative_grade(x, sc) for x in (39, 40, 69, 70, 89, 90)] == [2, 3, 3, 4, 4, 5]
    assert normalize_scale({'3': 40, '4': 70, '5': 90}) == sc            # JSON açarları sətir
    assert normalize_scale({'3': 80, '4': 70, '5': 90}) == {3: 31, 4: 61, 5: 81}   # xarab – defolt
    assert level(70) == 'Yüksək' and level(40) == 'Orta' and level(39) == 'Zəif'


def test_validate_scale():
    assert validate_scale({3: 31, 4: 61, 5: 81}) is None
    assert validate_scale({3: 50, 4: 50, 5: 81})        # ciddi artan deyil
    assert validate_scale({3: 70, 4: 60, 5: 81})
    assert validate_scale({3: 0, 4: 60, 5: 81})         # 1–100
    assert validate_scale({3: 10, 4: 60, 5: 101})


def _grade(S, ta, kind, with_scale):
    """Test (kind) + 10 'open' sual; 6 düz cavab = 60%."""
    with S() as db:
        a = db.get(TeachingAssignment, ta)
        a.cert_rules = {'formative_scale': {'3': 20, '4': 50, '5': 90}} if with_scale else None
        t = db.scalars(select(OnlineTask).where(OnlineTask.assignment_id == ta)).first()
        t.kind = kind
        t.questions = [{'kind': 'open', 'text': str(i), 'answer': '1'} for i in range(10)]
        at = TaskAttempt(answers={str(i): '1' for i in range(6)})
        score(t, at)
        db.rollback()
        return at.points, at.grade


def test_custom_scale_only_topic_tests(world):
    admin, ta, cid, st, ids = setup(world)
    assert mk_task(admin, ta, ids).status_code == 200
    S = world[1]
    assert _grade(S, ta, 'movzu', False) == (60.0, 3)        # defolt: 60% -> 3
    assert _grade(S, ta, 'movzu', True) == (60.0, 4)         # sinif şkalası: 50+ -> 4
    assert _grade(S, ta, None, True) == (60.0, 4)            # adi tapşırıq – formativ
    assert _grade(S, ta, 'sinaq', True) == (60.0, 3)         # sınaq dəyişmir
    assert _grade(S, ta, 'ksq', True) == (60.0, 3)           # KSQ dəyişmir


def test_scale_api_validation_and_reset(world):
    admin, ta, cid, st, ids = setup(world)
    url = f'/api/tasks/formative-scale/{ta}'
    g = admin.get(url).json()
    assert (g['t3'], g['t4'], g['t5'], g['default']) == (31, 61, 81, True)
    assert admin.put(url, json={'t3': 50, 't4': 50, 't5': 90}).status_code == 422
    assert admin.put(url, json={'t3': 0, 't4': 50, 't5': 90}).status_code == 422
    assert admin.put(url, json={'t3': 40, 't4': 70, 't5': 90}).status_code == 200
    g = admin.get(url).json()
    assert (g['t3'], g['t4'], g['t5'], g['default']) == (40, 70, 90, False)
    # sertifikat hədlərini saxlamaq şkalanı silmir
    r = admin.get('/api/certificates', params={'ta_id': ta}).json()['rules']
    keep = {k: r[k] for k in ('enabled', 'movzu', 'sinaq_pct', 'sinaq_top', 'seriya')}
    assert admin.put(f'/api/certificates/rules/{ta}', json=keep).status_code == 200
    assert admin.get(url).json()['t3'] == 40
    g = admin.delete(url).json()
    assert (g['t3'], g['t4'], g['t5'], g['default']) == (31, 61, 81, True)
