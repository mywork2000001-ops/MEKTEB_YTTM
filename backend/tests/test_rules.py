import pytest
from app.domain.rules import round_half_up, summative_grade, semester_grade, grade_from_points


@pytest.mark.parametrize('x,exp', [(2.5, 3), (3.5, 4), (2.49, 2), (4.5, 5), (0.5, 1)])
def test_round_half_up(x, exp):
    assert round_half_up(x) == exp


@pytest.mark.parametrize('pct,g', [(0, 2), (30, 2), (30.4, 2), (30.5, 3), (31, 3), (60, 3), (61, 4), (80, 4), (81, 5), (100, 5)])
def test_summative_bands(pct, g):
    assert summative_grade(pct) == g


def test_grade_from_points_no_double_rounding():
    assert grade_from_points(6, 20) == 2        # 30%
    assert grade_from_points(12.2, 20) == 4     # 61%
    with pytest.raises(ValueError):
        grade_from_points(5, 0)


def test_semester_formula():
    # (4+5+3)/3 = 4 → 4*0,4 + 5*0,6 = 4,6 → 5
    assert semester_grade([4, 5, 3], 5) == 5
    # (3+4)/2 = 3,5 → 1,4 + 1,8 = 3,2 → 3
    assert semester_grade([3, 4], 3) == 3
    # (3+4+4+4)/4 = 3,75 → 1,5 + 3,0 = 4,5 → 5 (adi yuvarlaqlaşdırma, bank üsulu 4 verərdi)
    assert semester_grade([3, 4, 4, 4], 5) == 5
    assert semester_grade([], 5) is None
    assert semester_grade([4], None) is None


def test_timetable_no_conflicts_with_class_bells():
    from app.domain.calendar import CLASSES, CLASS_BY_CODE, bell_time, teacher_conflicts
    xip = CLASS_BY_CODE['xip']
    assert bell_time(xip, 1) == '08:00–08:45' and bell_time(xip, 2) == '08:50–09:35'
    assert bell_time(CLASS_BY_CODE['xe'], 1) == '08:50–09:35'
    assert teacher_conflicts(CLASSES) == []
    # 32 saat TOM + 4 saat XI peşə
    assert sum(len(p) for c in CLASSES for p in c.slots.values()) == 36


def test_conflict_detected_without_own_bells():
    import dataclasses
    from app.domain.calendar import CLASSES
    wrong = [dataclasses.replace(c, bells=None) if c.code == 'xip' else c for c in CLASSES]
    from app.domain.calendar import teacher_conflicts
    found = teacher_conflicts(wrong)
    assert any('XI peşə' in x and 'X e' in x for x in found)      # Ç.a. 08:50 X e ilə


def test_xb_split_with_biology():
    from app.domain.calendar import CLASS_BY_CODE
    q = CLASS_BY_CODE['xb_q']
    assert q.parent == 'xb' and q.slots == {0: [3, 5], 1: [3, 6, 7]} and 'Biologiya' in q.split_with
    assert CLASS_BY_CODE['xb'].slots == {2: [3, 7], 3: [1, 4], 4: [2]}


def test_today_uses_baku_time(monkeypatch):
    import datetime as dt
    from app import services

    class FakeDT(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            # UTC 22.09 21:30 = Bakı 23.09 01:30
            return dt.datetime(2026, 9, 22, 21, 30, tzinfo=dt.timezone.utc).astimezone(tz)
    monkeypatch.setattr(services.dt, 'datetime', FakeDT)
    assert services.today() == dt.date(2026, 9, 23)
