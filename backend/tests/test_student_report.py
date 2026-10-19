"""Şagirdin fərdi hesabatı (docs/sagird-ferdi-hesabat-promtu.md §3): onlayn + kağız + skan nəticələr bir yerdə, təkrar yoxdur,
nəşr olunmamış skan şagirdə görünmür, sınaq adı normallaşır, mövzu nömrəsi, fərdi məkan və <5 şagird qaydaları."""
import datetime as dt

import pytest
from fastapi import HTTPException

from app.models import Exam, ExamScan, ExamScore, ExamSeries, OnlineTask, PlanLesson, Role, Student, User
from app.student_report import (lesson_numbers, my_results, no_key, parse_sinaq, sinaq_name, student_results,
                                topic_no)

from .test_api_portal import UTC, clock, setup, student_client  # noqa: F401 – clock fixture
from .test_api_results_center import ALL_OK, _answer

WIN = {'opens_at': '2026-09-29T11:00:00Z', 'closes_at': '2026-09-29T14:00:00Z'}


@pytest.fixture
def patched(monkeypatch, clock):
    for mod in ('app.api.exams_online', 'app.api.topic_tests', 'app.test_stats'):
        monkeypatch.setattr(f'{mod}.now', clock)
    return clock


def _staff(S, login='admin'):
    with S() as db:
        return db.query(User).filter_by(login=login).one()


def _mk(world, patched, sinaq_title='usi 1'):
    """3 şagird: 0-cı mövzu testi (kvadrat tənliklər) və sınaq yazır."""
    as_, S = world
    admin, ta, cid, st, ids = setup(world)
    with S() as db:
        for seq in (3, 4, 5):                                   # bölmə «2. Tənliklər»: seq 5 – bölmədə 3-cü mövzu → 2.3
            pl = db.query(PlanLesson).filter_by(assignment_id=ta, seq=seq).one()
            pl.section = '2. Tənliklər'
        db.query(PlanLesson).filter_by(assignment_id=ta, seq=6).one().topic = '3.4. Funksiya'
        pl5 = db.query(PlanLesson).filter_by(assignment_id=ta, seq=5).one().id
        db.commit()
    patched.t = dt.datetime(2026, 9, 29, 10, 0, tzinfo=UTC)
    r = admin.post(f'/api/plan/{ta}/topics/{pl5}/test', json={'title': 'Kvadrat tənliklər – test', 'duration_min': 20,
                                                              'bank_ids': ids, 'targets': [{'ta_id': ta, 'plan_lesson_id': pl5, **WIN}]})
    assert r.status_code == 200, r.text
    tt = r.json()['tasks'][0]['id']
    bid = admin.post('/api/exams-online', json={'title': sinaq_title, 'bank_ids': ids, 'targets': [{'ta_id': ta, **WIN}]}).json()['id']
    with S() as db:
        et = db.query(OnlineTask).filter_by(batch_id=bid).one().id
    patched.t = dt.datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
    _answer(st[0], tt, ALL_OK)
    _answer(st[0], et, ALL_OK)
    patched.t = dt.datetime(2026, 9, 29, 15, 0, tzinfo=UTC)
    return admin, ta, st, bid


def _paper(S, ta, sid, kind, no, pts, mx, published, scan=False, **kw):
    with S() as db:
        e = Exam(assignment_id=ta, kind=kind, no=no, semester=1, date=dt.date(2026, 10, 5), max_points=mx,
                 results_published_at=dt.datetime(2026, 10, 6, tzinfo=UTC) if published else None, **kw)
        db.add(e)
        db.flush()
        db.add(ExamScore(exam_id=e.id, student_id=sid, points=pts))
        if scan:
            db.add(ExamScan(exam_id=e.id, student_id=sid, code='A1', status='graded', source='paper', points=pts))
        db.commit()
        return e.id


# ---------------------------------------------------------------- saf funksiyalar
def test_topic_no_and_sort():
    assert topic_no('3.4. Funksiya') == '3.4' and topic_no('2.10 Ad') == '2.10'
    assert topic_no('Kvadrat tənliklər', '2. Tənliklər', 3) == '2.3'
    assert topic_no('Kvadrat tənliklər', 'Tənliklər', 3) is None and topic_no('Ad') is None
    assert sorted(['2.10', None, '2.3', '1.2'], key=no_key) == ['1.2', '2.3', '2.10', None]


def test_sinaq_name_normalized():
    assert sinaq_name('usi 1') == sinaq_name('ÜSİ-1 (yeni yer)') == sinaq_name('ÜSİ 1') == 'ÜSİ-1'
    assert sinaq_name('MSİ-2') == 'MSİ-2' and parse_sinaq('ms3') == ('MS', 3)
    assert sinaq_name('Buraxılış sınağı (dəmir)') == 'Buraxılış sınağı'


# ---------------------------------------------------------------- 1. üç mənbə, təkrar yoxdur
def test_all_sources_no_duplicates(world, patched):
    as_, S = world
    admin, ta, st, bid = _mk(world, patched)
    sid = st[0]['id']
    # kağız KSQ (skansız, əl ilə bal) + kağız sınaq (skan, nəşr olunmuş), həmin sınaq onlayn paketə də bağlıdır
    _paper(S, ta, sid, 'KSQ', 1, 24, 30, published=False)
    _paper(S, ta, sid, 'SINAQ', 1, 80, 100, published=True, scan=True, batch_id=bid, title='usi 1')
    with S() as db:
        r = student_results(db, _staff(S), sid)
    assert [t['pct'] for t in r['topic_tests']] == [100.0] and r['topic_tests'][0]['source'] == 'onlayn'
    assert [(k['kind'], k['pct'], k['published']) for k in r['summatives']] == [('KSQ', 80.0, True)]
    # onlayn sınaq və kağız sınaq eyni testdir – bir dəfə (kağız nəşr olunmuş balı üstündür)
    assert [(m['name'], m['pct'], m['source']) for m in r['mocks']] == [('ÜSİ-1', 80.0, 'kağız')]
    assert r['summary']['avg_pct'] == round((100 + 80 + 80) / 3, 1)


# ---------------------------------------------------------------- 2. nəşr olunmamış skan
def test_unpublished_scan_hidden_from_student(world, patched):
    as_, S = world
    admin, ta, st, bid = _mk(world, patched)
    sid = st[0]['id']
    _paper(S, ta, sid, 'BSQ', 1, 27, 30, published=False, scan=True)
    with S() as db:
        teacher = student_results(db, _staff(S), sid)
        mine = my_results(db, db.get(Student, sid))
    assert [(x['kind'], x['published']) for x in teacher['summatives']] == [('BSQ', False)]
    assert mine['summatives'] == []
    assert teacher['summary']['summative_avg'] is None            # nəşr olunmamış yekuna girmir
    with S() as db:                                               # müəllim «göstər» dedi
        db.get(Exam, db.query(Exam).one().id).results_published_at = dt.datetime(2026, 10, 7, tzinfo=UTC)
        db.commit()
        assert [x['pct'] for x in my_results(db, db.get(Student, sid))['summatives']] == [90.0]


# ---------------------------------------------------------------- 3. sınaq adı
def test_mock_name_and_series(world, patched):
    as_, S = world
    admin, ta, st, bid = _mk(world, patched, sinaq_title='ÜSİ-1 (yeni yer)')
    sid = st[0]['id']
    with S() as db:
        assert [m['name'] for m in student_results(db, _staff(S), sid)['mocks']] == ['ÜSİ-1']
        db.add(ExamSeries(created_by=_staff(S).id, title='Buraxılış sınağı', subject='Riyaziyyat', targets=[], sources=[],
                          period='week', open_time='15:00', next_at=dt.datetime(2026, 11, 1, tzinfo=UTC),
                          done=[{'file_id': 1, 'batch_id': 999}, {'file_id': 2, 'batch_id': bid}]))
        db.commit()
        m = student_results(db, _staff(S), sid)['mocks'][0]
    assert (m['name'], m['series'], m['no_in_series']) == ('Buraxılış sınağı №2', 'Buraxılış sınağı', 2)   # seriya adı üstündür


# ---------------------------------------------------------------- 4. mövzu nömrəsi
def test_topic_numbers_from_plan(world, patched):
    as_, S = world
    admin, ta, st, bid = _mk(world, patched)
    with S() as db:
        r = student_results(db, _staff(S), st[0]['id'])
        nums = lesson_numbers(list(db.query(PlanLesson).filter_by(assignment_id=ta)))
    t = r['topic_tests'][0]
    assert (t['no'], t['topic'], t['section']) == ('2.3', 'Kvadrat tənliklər', '2. Tənliklər')
    assert sorted(nums.values(), key=no_key)[:3] == ['2.1', '2.2', '2.3'] and '3.4' in nums.values()


# ---------------------------------------------------------------- 5. fərdi məkan
def test_private_workspace_student_is_404(world):
    as_, S = world
    admin, ilqar = as_('admin'), as_('ilqar')
    cid = ilqar.post('/api/classes', json={'name': 'IX hazırlıq', 'kind': 'adi', 'private': True}).json()['id']
    ilqar.post(f'/api/classes/{cid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 2, 'has_summative': False,
                                                 'slots': {'0': [7], '2': [7]}})
    st = ilqar.post('/api/students', json={'full_name': 'Fərdi Şagird oğlu', 'class_id': cid}).json()
    with S() as db:
        for login in ('admin', 'yad'):
            with pytest.raises(HTTPException) as e:
                student_results(db, _staff(S, login), st['id'])
            assert e.value.status_code == 404


# ---------------------------------------------------------------- 6. <5 şagird
def test_class_avg_hidden_below_five(world, patched):
    as_, S = world
    admin, ta, st, bid = _mk(world, patched)
    sid = st[0]['id']
    eid = _paper(S, ta, sid, 'KSQ', 1, 24, 30, published=True)
    adm = _staff(S)
    with S() as db:
        r = student_results(db, _staff(S), sid)
        assert r['topic_tests'][0]['class_avg'] is None and r['mocks'][0]['class_avg'] is None
        assert r['summatives'][0]['class_avg'] is None
        # sinifdə 5 nəticə olanda ortası göstərilir
        for i in range(4):
            x = Student(school_id=adm.school_id, class_id=db.get(Student, sid).class_id, full_name=['Quliyev Rəşad oğlu', 'Məmmədova Aynur qızı', 'Bayramov Tural oğlu', 'Əliyeva Sevil qızı'][i],
                        portal_code=f'ZZ-{i}')
            db.add(x)
            db.flush()
            db.merge(ExamScore(exam_id=eid, student_id=x.id, points=15))
        db.commit()
        r = student_results(db, _staff(S), sid)
    assert r['summatives'][0]['class_avg'] == round((80 + 4 * 50) / 5, 1)


# ---------------------------------------------------------------- API (§2.2)
def test_report_api(world, patched):
    as_, S = world
    admin, ta, st, bid = _mk(world, patched)
    sid = st[0]['id']
    _paper(S, ta, sid, 'BSQ', 1, 27, 30, published=False, scan=True)
    r = admin.get(f'/api/results-center/student/{sid}/report')
    assert r.status_code == 200, r.text
    rep = r.json()
    assert rep['topic_tests'][0]['no'] == '2.3' and rep['mocks'][0]['name'] == 'ÜSİ-1'
    assert [(x['kind'], x['published']) for x in rep['summatives']] == [('BSQ', False)]
    assert admin.get(f'/api/results-center/student/{sid}/report', params={'from': '2026-12-01'}).json()['topic_tests'] == []
    # geriyə uyğun: köhnə profil yeni bölmələri də qaytarır
    prof = admin.get(f'/api/results-center/student/{sid}').json()
    assert prof['mocks'][0]['name'] == 'ÜSİ-1' and prof['topic_tests'][0]['no'] == '2.3' and 'parts' in prof
    # Word + valideyn nüsxəsi (RU) / rəsmi (AZ)
    d = admin.get(f'/api/results-center/student/{sid}/report', params={'format': 'docx', 'lang': 'ru', 'parent': True})
    assert d.status_code == 200 and d.content[:2] == b'PK'
    from app.student_report_print import report_html
    assert 'Şagirdin fərdi hesabatı' in report_html(rep, 'az') and 'Краткий отчёт' in report_html(rep, 'ru', parent=True)
    assert 'не опубликовано' in report_html(rep, 'ru', parent=True) and 'ÜSİ-1' in report_html(rep, 'ru', parent=True)
    # şagird portalı: nəşr olunmamış BSQ görünmür, qalanı görünür
    s = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    mine = s.get('/api/portal/my/report').json()
    assert mine['summatives'] == [] and mine['mocks'][0]['name'] == 'ÜSİ-1' and mine['viewer'] == 'student'
    assert s.get(f'/api/results-center/student/{sid}/report').status_code in (401, 403)


def test_report_api_private_workspace(world):
    as_, S = world
    admin, ilqar = as_('admin'), as_('ilqar')
    cid = ilqar.post('/api/classes', json={'name': 'IX hazırlıq', 'kind': 'adi', 'private': True}).json()['id']
    ilqar.post(f'/api/classes/{cid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 2, 'has_summative': False,
                                                 'slots': {'0': [7], '2': [7]}})
    st = ilqar.post('/api/students', json={'full_name': 'Fərdi Şagird oğlu', 'class_id': cid}).json()
    assert admin.get(f"/api/results-center/student/{st['id']}/report").status_code == 404
    assert as_('yad').get(f"/api/results-center/student/{st['id']}/report").status_code == 404
    r = ilqar.get(f"/api/results-center/student/{st['id']}/report")
    assert r.status_code == 200 and r.json()['student']['full_name'] == 'Fərdi Şagird oğlu'
