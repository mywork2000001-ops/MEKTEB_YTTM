"""Sertifikat dərəcələri: 31–60 Mis, 61–80 Gümüş, 81–90 Qızıl, 91–100 Platin; ≤ 30 – yoxdur, köhnəsi ləğv (tidy)."""
from app.certificates import tier, tidy
from app.models import Certificate, Student


def test_tier_bounds():
    assert [tier(p) for p in (None, 0, 30, 30.4, 30.6, 31, 60, 61, 80, 81, 90, 91, 100)] == \
        [None, None, None, None, 'mis', 'mis', 'mis', 'gumus', 'gumus', 'qizil', 'qizil', 'platin', 'platin']


def test_tidy_revokes_low_and_sets_tier(world):
    _, S = world
    from .test_api_portal import setup
    setup(world)
    with S() as db:
        sid = db.query(Student).first().id
        low = Certificate(code='MK-26-LOW00001', student_id=sid, kind='sinaq', source='task:1', title='x', details={'pct': 25.0, 'place': 1})
        hi = Certificate(code='MK-26-HIGH0001', student_id=sid, kind='movzu', source='task:2', title='y', details={'pct': 85.0})
        man = Certificate(code='MK-26-MAN00001', student_id=sid, kind='manual', source='manual:1', title='z', details={})
        db.add_all([low, hi, man]); db.commit()
        assert tidy(db) == 2
        db.commit()
        assert low.revoked_at is not None and hi.details['tier'] == 'qizil' and man.revoked_at is None
        assert tidy(db) == 0                                  # idempotent
