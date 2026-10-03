"""Perspektiv plan proqramları: kitabxana, uyğunlaşan proqramın sinfin cədvəlinə açılması, tətbiq, geri qaytarma."""
import datetime as dt

from app.models import JournalEntry, PlanLesson, TeachingAssignment
from app.programs import expand

from .test_api_analytics import setup

TPL = {'variants': 'A–D', 'summative_variants': 8, 'annual_test': True, 'semesters': [
    [{'section': '1. Natural ədədlər', 'topics': ['A', 'B']}, {'section': '2. Kəsrlər', 'topics': ['C']}],
    [{'section': '3. Onluq kəsrlər', 'topics': ['D', 'E']}]]}


def test_expand_fills_slots_exactly():
    les, warn = expand(TPL, 5, 20, 15, True)
    s1 = [l for l in les if l['semester'] == 1]
    s2 = [l for l in les if l['semester'] == 2]
    assert len(s1) == 20 and len(s2) == 15 and not warn
    assert s1[0]['assessment_type'] == 'diaqnostik' and s1[-1]['assessment_type'] == 'BSQ' and s2[-1]['assessment_type'] == 'BSQ'
    assert [l['exam_no'] for l in les if l['assessment_type'] == 'KSQ'] == [1, 2, 3]
    assert any('Sinif testi' in l['topic'] for l in s1)
    # summativ olmayan qrup – KSQ/BSQ yoxdur
    les2, _ = expand(TPL, 5, 20, 15, False)
    assert not any(l['assessment_type'] in ('KSQ', 'BSQ') for l in les2) and len(les2) == 35
    # yuva az – köməkçi dərslər çıxır, sonra xəbərdarlıq
    les3, warn3 = expand(TPL, 5, 3, 2, True)
    assert len([l for l in les3 if l['semester'] == 1]) >= 4 and warn3


def test_library_apply_and_restore(world, monkeypatch):
    as_, S = world
    c, ta, good, weak, new = setup(world)
    lib = c.get('/api/programs').json()
    builtin = [p for p in lib if p['builtin']]
    assert [p['grade'] for p in builtin] == [5, 6, 7, 8, 9, 10, 11]
    cur = next(p for p in lib if p['mine'] and 'X c' in p['used_by'])          # cari plan avtomatik proqram oldu
    assert cur['kind'] == 'fixed' and cur['lessons'] == 40
    x10 = next(p for p in builtin if p['grade'] == 10)
    d = c.get(f"/api/programs/{x10['id']}").json()
    assert d['outline'][0]['sections'][0]['topics'][0] == 'Funksiya anlayışı'
    pv = c.get(f"/api/programs/{x10['id']}/preview/{ta}").json()
    assert pv['lessons'] == pv['sem1_slots'] + pv['sem2_slots'] and pv['written_lessons'] == 10
    with S() as db:                                      # jurnalda yazılmış dərsin mövzusu
        e = db.query(JournalEntry).filter_by(assignment_id=ta, date=dt.date(2026, 9, 15)).one()
        old_topic = db.get(PlanLesson, e.plan_lesson_id).topic if e.plan_lesson_id else None
        first_id = db.query(PlanLesson).filter_by(assignment_id=ta, seq=1).one().id
    r = c.post(f"/api/programs/{x10['id']}/apply/{ta}").json()
    assert r['previous_program_id'] and r['frozen_topics'] >= 1
    with S() as db:
        e = db.query(JournalEntry).filter_by(assignment_id=ta, date=dt.date(2026, 9, 15)).one()
        assert e.topic == old_topic                       # keçmiş dəyişmədi
        assert db.query(PlanLesson).filter_by(assignment_id=ta, seq=1).one().id == first_id   # id qorundu
        assert db.get(TeachingAssignment, ta).program_id == x10['id']
        assert db.query(PlanLesson).filter_by(assignment_id=ta).count() == pv['lessons']
    lib = c.get('/api/programs').json()
    assert 'X c' in next(p for p in lib if p['id'] == x10['id'])['used_by']
    prev = next(p for p in lib if p['id'] == r['previous_program_id'])
    assert 'əvvəlki plan' in prev['title'] and prev['lessons'] == 40
    # geri qaytarma: əvvəlki planı yenidən tətbiq et
    c.post(f"/api/programs/{prev['id']}/apply/{ta}")
    with S() as db:
        assert db.query(PlanLesson).filter_by(assignment_id=ta).count() == 40
    # başqa müəllim: başqasının sinfinə tətbiq edə bilməz, başqasının proqramını görmür
    ilqar = as_('ilqar')
    assert ilqar.post(f"/api/programs/{x10['id']}/apply/{ta}").status_code == 404
    assert not any(p['id'] == prev['id'] for p in ilqar.get('/api/programs').json())
    # istifadədə olan öz proqramı arxivlənmir, ümumi proqram silinmir
    assert c.delete(f"/api/programs/{prev['id']}").status_code == 409
    assert c.delete(f"/api/programs/{x10['id']}").status_code == 403


def test_level_fit_and_extra_programs(world):
    as_, S = world
    c, ta, good, weak, new = setup(world)
    lib = c.get('/api/programs', params={'ta_id': ta}).json()
    fits = [p['grade'] for p in lib if p['builtin'] and p['fits']]
    assert fits == [10] and lib[0]['fits']                                   # X sinif – uyğun olanlar öndə
    x10 = next(p for p in lib if p['builtin'] and p['grade'] == 10)
    x9 = next(p for p in lib if p['builtin'] and p['grade'] == 9)
    with S() as db:
        before = db.query(PlanLesson).filter_by(assignment_id=ta).count()
    # əlavə proqram: zəif qrup üçün IX sinif proqramı (təkrar) – jurnala qarışmır
    f = c.post(f"/api/programs/{x9['id']}/attach/{ta}", json={'level': 'Zəif', 'note': 'təkrar'}).json()
    assert f['extra'][0]['level'] == 'Zəif' and f['extra'][0]['program']['grade'] == 9 and f['main']['kind'] == 'fixed'
    c.post(f"/api/programs/{x10['id']}/attach/{ta}", json={})
    assert c.post(f"/api/programs/{x10['id']}/attach/{ta}", json={}).status_code == 409
    with S() as db:
        assert db.query(PlanLesson).filter_by(assignment_id=ta).count() == before       # əsas plan dəyişmədi
    aid = f['extra'][0]['id']
    d = c.get(f'/api/programs/attached/{aid}').json()
    assert d['lessons'] == len(d['lessons_list']) and d['lessons_list'][0]['date'] and d['level'] == 'Zəif'
    assert 'X c (əlavə – Zəif)' in next(p for p in c.get('/api/programs').json() if p['id'] == x9['id'])['used_by']
    assert as_('ilqar').get(f'/api/programs/attached/{aid}').status_code == 404
    left = c.delete(f'/api/programs/attached/{aid}').json()
    assert len(left['extra']) == 1 and left['extra'][0]['program']['grade'] == 10
    # öz proqramına səviyyə və sinif yazmaq
    mine = next(p for p in c.get('/api/programs').json() if p['mine'])
    r = c.patch(f"/api/programs/{mine['id']}", json={'title': 'X c – güclü qrup proqramı', 'level': 'Güclü', 'grade': 10}).json()
    assert r['level'] == 'Güclü' and [p['id'] for p in c.get('/api/programs', params={'level': 'Güclü'}).json()] == [mine['id']]
