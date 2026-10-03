"""Analitika auditi (docs/analitika-cap-auditi.md): irəliləyiş ilin əvvəlində, avtomatik test yazısı «yazılmış dərs»
deyil, fənnə uyğun IX balı, az qiymətlə fənn qiyməti çıxmır, sınaq riskdə, cari yarımil."""
import datetime as dt

from app.domain.rules import RiskInput, risk_score
from app.models import JournalEntry, Mark, TeachingAssignment

from .test_api_analytics import setup


def test_progress_early_in_semester(world, monkeypatch):
    monkeypatch.setattr('app.analytics.today', lambda: dt.date(2026, 10, 3))
    c, ta, good, weak, new = setup(world)
    a = c.get(f'/api/analytics/{ta}', params={'semester': 1}).json()
    rows = {r['student_id']: r for r in a['students']}
    # I yarımilin ortası 21.11-dir, amma nəticələr 15–26.09-dadır – irəliləyiş yenə hesablanır
    assert a['progress_split'] is not None and rows[good]['progress'] is not None
    assert rows[good]['progress_place'] is not None and rows[new]['progress'] is None


def test_auto_entry_is_not_written_lesson(world, monkeypatch):
    monkeypatch.setattr('app.api.homeroom.today', lambda: dt.date(2026, 9, 30))
    monkeypatch.setattr('app.api.journal.today', lambda: dt.date(2026, 9, 30))
    c, ta, good, weak, new = setup(world)
    before = c.get(f'/api/analytics/{ta}/lessons').json()['year']
    with world[1]() as db:                      # onlayn testin yaratdığı yazı: yalnız test qiyməti, davamiyyət yox
        e = JournalEntry(assignment_id=ta, date=dt.date(2026, 9, 29), period=1, auto=True)
        db.add(e)
        db.flush()
        db.add(Mark(entry_id=e.id, student_id=good, kind='test', grade=5, test_correct=9, test_total=10))
        db.commit()
    after = c.get(f'/api/analytics/{ta}/lessons').json()['year']
    assert after['written'] == before['written'] and after['missing'] == before['missing']
    assert len(c.get(f'/api/analytics/{ta}/attendance').json()['columns']) == 10
    day = c.get(f'/api/journal/{ta}/day', params={'date': '2026-09-29'}).json()['lessons'][0]['entry']
    assert day['exists'] and day['auto']
    # müəllim saxlayır – dərs yazılmış olur
    c.put(f'/api/journal/{ta}/entry', json={'date': '2026-09-29', 'period': 1, 'attendance': {good: 'var'},
                                            'marks': [{'student_id': good, 'kind': 'test', 'test_correct': 9, 'test_total': 10}]})
    assert c.get(f'/api/analytics/{ta}/lessons').json()['year']['written'] == before['written'] + 1


def test_ix_score_matches_subject(world):
    as_, S = world
    c = as_('admin')
    cid = c.post('/api/classes', json={'name': 'X d'}).json()['id']
    c.post(f'/api/classes/{cid}/join', json={'subject': 'Azərbaycan dili', 'weekly_hours': 3, 'slots': {}})
    sid = c.post('/api/students', json={'full_name': 'Dil Şagird qızı', 'class_id': cid, 'score_math': 90.0,
                                        'score_language': 30.0}).json()['id']
    with S() as db:
        ta = db.query(TeachingAssignment).filter_by(class_id=cid).one().id
    r = c.get(f'/api/analytics/{ta}').json()
    row = next(x for x in r['students'] if x['student_id'] == sid)
    assert row['ix_score'] == 30.0 and row['baseline_level'] == 'Zəif' and row['level_source'] == 'IX sinif balı'
    f = next(x for x in row['risk']['factors'] if x['amil'] == 'ix_bal')
    assert 'Azərbaycan dili' in f['izah'] and f['bal'] > 0


def test_few_marks_not_graded(world):
    c, ta, good, weak, new = setup(world)
    c.put(f'/api/journal/{ta}/entry', json={'date': '2026-09-28', 'period': 1, 'attendance': {new: 'var'},
                                            'marks': [{'student_id': new, 'kind': 'şifahi', 'grade': 4}]})
    p = c.get(f'/api/analytics/{ta}/performance', params={'semester': 1}).json()
    rows = {r['student_id']: r for r in p['students']}
    assert rows[new]['grade'] is None and rows[new]['source'] == 'az qiymət' and rows[new]['few_marks']
    assert rows[good]['grade'] == 5 and p['summary']['few_marks'] == 1 and p['summary']['min_marks'] == 3


def test_sinaq_risk_factor_and_current_semester(world):
    r = risk_score(RiskInput(sinaq_pcts=[80.0, 20.0, 30.0]))
    f = next(x for x in r.factors if x['amil'] == 'sinaq')
    assert f['bal'] == 20 and 'Son 2 sınağın ortası' in f['izah']
    assert next(x for x in risk_score(RiskInput()).factors if x['amil'] == 'sinaq')['bal'] == 0
    c, ta, *_ = setup(world)
    assert next(x for x in c.get('/api/my/lessons').json() if x['id'] == ta)['semester'] in (1, 2)


def test_school_performance_admin_only_and_consistent(world):
    as_, _ = world
    c, ta, good, weak, new = setup(world)
    r = c.get('/api/school/performance', params={'semester': 1})
    assert r.status_code == 200
    d = r.json()
    cls = next(x for x in d['classes'] if x['class_name'] == 'X c')
    hr = c.get(f"/api/homeroom/{cls['class_id']}", params={'semester': 1}).json()['summary']
    assert cls['success_pct'] == hr['success_pct'] and cls['quality_pct'] == hr['quality_pct']
    assert cls['categories'] == hr['categories'] and d['school']['students'] >= cls['students']
    assert any(p['grade'] == 10 for p in d['parallels'])
    assert any(f['full_name'] == 'Zəif Şagird qızı' and 'Riyaziyyat' in f['subjects'] for f in d['failing'])
    assert as_('ilqar').get('/api/school/performance').status_code == 403


def test_weekly_summary(world, monkeypatch):
    monkeypatch.setattr('app.services.today', lambda: dt.date(2026, 9, 30))
    c, ta, good, weak, new = setup(world)
    w = c.get('/api/my/weekly').json()
    it = next(x for x in w['items'] if x['ta_id'] == ta)
    assert 'Zəif Şagird qızı' in it['red'] and 'Zəif Şagird qızı' in it['absence']
    assert any(m['date'] == '2026-09-29' for m in it['missing_week']) and w['week'].startswith('2026-W')
