"""İşlənməyənlər / matris hesabatlarının sürəti (docs/tasks/islenmeyenler-suret.md): sorğu sayı + nəticənin dəyişməməsi."""
import datetime as dt
import json
import os

import pytest
from sqlalchemy import event

from app.models import PlanLesson, TeachingAssignment
from app.student_report import class_matrix, class_missing, missing_summary

from .test_api_portal import UTC, clock, setup  # noqa: F401
from .test_class_matrix import _ids, mat  # noqa: F401
from .test_student_report import WIN, _staff, patched  # noqa: F401

U = '/api/results-center'


class Counter:
    """SQLAlchemy sorğu sayğacı (before_cursor_execute)."""
    def __init__(self, S):
        self.eng, self.n = S.kw['bind'], 0

    def _hit(self, *a):
        self.n += 1

    def __enter__(self):
        event.listen(self.eng, 'before_cursor_execute', self._hit)
        return self

    def __exit__(self, *a):
        event.remove(self.eng, 'before_cursor_execute', self._hit)


@pytest.fixture
def big(mat, patched):
    """mat + 2 əlavə sinif/dərs, sınaq paketləri hamısına birdən (başqa siniflərdə də), hər dərsdə mövzu testləri."""
    admin, S, ta, st = mat
    t_keep, patched.t = patched.t, dt.datetime(2026, 9, 29, 10, 0, tzinfo=UTC)     # yaratma vaxtı pəncərədən əvvəl
    tas = [ta]
    for i in range(2):
        cid = admin.post('/api/classes', json={'name': f'X {"fg"[i]}'}).json()['id']
        admin.post(f'/api/classes/{cid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 2, 'slots': {'1': [1, 5]}})
        for j in range(3):
            admin.post('/api/students', json={'full_name': f'Şagird Sinif{i}{j} qızı', 'class_id': cid, 'force': True})
        with S() as db:
            t2 = db.query(TeachingAssignment).filter_by(class_id=cid).one().id
            for k in range(6):
                db.add(PlanLesson(assignment_id=t2, seq=k + 1, semester=1, assessment_type='formativ', topic=f'Mövzu {k + 1}',
                                  date=dt.date(2026, 9, 15)))
            db.commit()
        tas.append(t2)
    ids = _ids(S, ta)
    for n in range(3):
        r = admin.post('/api/exams-online', json={'title': f'Yoxlama {n + 1}', 'allow_repeat': True, 'bank_ids': ids, 'targets': [{'ta_id': x, **WIN} for x in tas]})
        assert r.status_code == 200, r.text
    for x in tas:
        with S() as db:
            pls = [p.id for p in db.query(PlanLesson).filter_by(assignment_id=x).order_by(PlanLesson.seq).limit(4)]
        for k, pl in enumerate(pls):
            r = admin.post(f'/api/plan/{x}/topics/{pl}/test', json={'title': f'T{x}-{k}', 'duration_min': 20, 'bank_ids': ids,
                                                                    'targets': [{'ta_id': x, 'plan_lesson_id': pl, **WIN}]})
            assert r.status_code == 200, r.text
    patched.t = t_keep
    return admin, S, tas


def test_query_counts(big):
    admin, S, tas = big
    u = _staff(S)
    with S() as db:
        with Counter(S) as c1:
            m = class_missing(db, u, tas[0], 'all', all_students=True, sort='risk')
        db.rollback()
    with Counter(S) as call:
        r = admin.get(f'{U}/missing-all?format=json')
    with Counter(S) as csum:
        r2 = admin.get(f'{U}/missing-summary')
    assert r.status_code == 200 and r2.status_code == 200
    print(f'\nSORGU: class_missing(1 dərs)={c1.n} missing-all json({len(tas)} dərs)={call.n} missing-summary={csum.n}')
    assert len(m['tests']) >= 7
    assert c1.n <= 40, c1.n
    assert call.n <= 40 * len(tas) and csum.n <= 40 * len(tas), (call.n, csum.n)


def test_results_unchanged(big):
    """Nəticənin imzası: PERF_SNAPSHOT fayl yoxdursa yazılır, varsa müqayisə olunur (optimallaşdırmadan əvvəl/sonra)."""
    admin, S, tas = big
    u = _staff(S)
    with S() as db:
        out = {'cm': [class_missing(db, u, t, 'all', all_students=True, sort='risk') for t in tas],
               'mx': [class_matrix(db, u, t, 'all') for t in tas],
               'sum': missing_summary(db, u, [db.get(TeachingAssignment, t) for t in tas])}
    p = os.environ.get('PERF_SNAPSHOT')
    if p:
        s = json.dumps(out, sort_keys=True, default=str, ensure_ascii=False)
        if os.path.exists(p):
            assert open(p, encoding='utf-8').read() == s
        else:
            open(p, 'w', encoding='utf-8').write(s)
