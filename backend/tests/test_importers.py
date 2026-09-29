import glob, os
import pytest
from app.importers.plans import parse_resources, assessment_type, parse_plan
from app.importers.students import read_workbook
from app.domain.calendar import CLASSES, check_plan_dates, check_bsq

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
PLANS = os.path.join(ROOT, '01 Aktual dərs proqramları 2026-2027')
XLSX = os.path.join(ROOT, 'Şagirdlər', 'Buraxılış nəticələri - riyaziyyat (Həsənov F.).xlsx')


def test_resources_skip_qt_and_textbook():
    pages, tasks = parse_resources('TT I, s.45–46; S 1–20; E 21–35\nQT 3; D 5, 6')
    assert pages == 'TT I, s.45–46'
    assert [(t.kind, t.start, t.end) for t in tasks] == [('sinif', 1, 20), ('ev', 21, 35)]


@pytest.mark.parametrize('topic,asm,exp', [
    ('KSQ-3 – kiçik summativ', '', ('KSQ', 3)),
    ('BSQ-1 – böyük summativ qiymətləndirmə', '', ('BSQ', 1)),
    ('Mövzu sınaq imtahanı-2', '', ('KSQ', 2)),
    ('Ümumi sınaq imtahanı-4', '', ('BSQ', 4)),
    ('Böyük summativ qiymətləndirməyə hazırlıq: I yarımil', 'Formativ', ('formativ', None)),
    ('Funksiya', 'Diaqnostik – ilkin', ('diaqnostik', None)),
])
def test_assessment_type(topic, asm, exp):
    assert assessment_type(topic, asm) == exp


needs_sources = pytest.mark.skipif(not os.path.isdir(PLANS), reason='mənbə planlar yoxdur')


@needs_sources
@pytest.mark.parametrize('c', CLASSES, ids=lambda c: c.code)
def test_official_plans_parse(c):
    f = [x for x in glob.glob(os.path.join(PLANS, '*.docx')) if os.path.basename(x).startswith(c.plan_prefix)]
    assert f, c.plan_prefix
    p = parse_plan(f[0])
    assert p.lessons and not p.warnings
    if c.has_summative:
        bsq = [(l.exam_no, l.date) for l in p.lessons if l.assessment_type == 'BSQ']
        assert check_bsq(bsq, c.slots) == []
        assert sum(l.assessment_type == 'KSQ' for l in p.lessons) >= 10
    chk = check_plan_dates([l.date for l in p.lessons], c.slots)
    assert chk['ferq'] == 0 and not chk['uygunsuz_tarixler'] and not chk['tetile_dusen']


@pytest.mark.skipif(not os.path.isfile(XLSX), reason='şagird faylı yoxdur')
def test_students_workbook():
    r, w = read_workbook(XLSX, ['X b', 'X c', 'X ə', 'XI a'])   # köhnə köməkçi faylı – yalnız format yoxlaması
    assert not w
    assert {k: len(v) for k, v in r.items()} == {'X b': 20, 'X c': 20, 'X ə': 17, 'XI a': 18}
    s = r['X b'][0]
    assert not hasattr(s, 'pin') and s.birth_date and s.score_math is not None


UTIS = os.path.join(ROOT, 'Utis_siyahi (27).xlsx')
DIM = os.path.join(ROOT, 'TOM-şagirdlər buraxılış balları (1).xlsx')


@pytest.mark.skipif(not (os.path.isfile(UTIS) and os.path.isfile(DIM)), reason='UTİS/DİM faylları yoxdur')
def test_utis_roster_merges_scores_without_secrets():
    import dataclasses
    from app.importers.utis import read_utis, class_label
    u = read_utis(UTIS, DIM)
    assert sum(map(len, u.classes.values())) == 168 and len(u.without_scores) == 5
    s = u.classes['10 b'][0]
    assert s.name.endswith('qızı') and s.score_math == 65.5
    names = {f.name for f in dataclasses.fields(s)}
    assert not any(x in n for n in names for x in ('id', 'pin', 'seriya'))
    assert class_label('11 a 1') == 'XI a' and class_label('10 ə') == 'X ə'
    for c in CLASSES:
        if c.utis_class and c.code != 'xip':          # XI peşə – məktəbin öz UTİS PDF ixracından («11 p»)
            assert c.utis_class in u.classes, c.code
    assert len(u.classes['10 e']) == 18


def test_bsq_rule_dates():
    import datetime as dt
    from app.domain.calendar import bsq_due_dates, CLASS_BY_CODE
    assert bsq_due_dates(CLASS_BY_CODE['xb'].slots) == (dt.date(2027, 1, 22), dt.date(2027, 6, 11))
    assert bsq_due_dates(CLASS_BY_CODE['xia'].slots) == (dt.date(2027, 1, 25), dt.date(2027, 6, 14))
    assert bsq_due_dates(CLASS_BY_CODE['xc'].slots) == (dt.date(2027, 1, 26), dt.date(2027, 6, 14))
    assert check_bsq([(1, dt.date(2026, 12, 25)), (2, dt.date(2027, 6, 11))], CLASS_BY_CODE['xb'].slots)
