"""Audit 19.10.2026 (docs/tasks/audit-proqram-sinif-sagird.md): server mesajları key+params, oxşar şagird (H4), qrup müəlliminin
hüquqları (H2), sinif arxiv/silmə qorumaları (M1, M2), proqram arxivi (M4), plan yoxlaması (P1), roster-health."""
import datetime as dt
from types import SimpleNamespace

from app.models import AuditLog, JournalEntry, TeachingAssignment
from app.programs import lint_plan

from .test_api_roster import join, mk_class, mk_student

SL = {'0': [1], '2': [3]}


def _detail(r):
    d = r.json()['detail']
    assert isinstance(d, dict), d
    return d


# ---------------------------------------------------------------- H3: key + params
def test_dynamic_error_has_key_and_params(world):
    as_, _ = world
    admin = as_('admin')
    cid = mk_class(admin).json()['id']
    d = _detail(mk_class(admin, 'x  C'))
    assert d['class_id'] == cid and d['key'] == '«{name}» sinfi artıq var – ona qoşulun'
    assert d['params'] == {'name': 'X c'} and d['message'] == d['key'].format(**d['params'])
    # get_or_404 – ad da parametr kimi (frontend onu da tərcümə edir)
    d2 = _detail(admin.get('/api/classes/99999/members'))
    assert d2['key'] == '{what} tapılmadı' and d2['params'] == {'what': 'Sinif'}


# ---------------------------------------------------------------- H4: oxşar şagird
def test_similar_student_soft_duplicate(world):
    as_, _ = world
    admin = as_('admin')
    a = mk_class(admin, 'IX a').json()['id']
    b = mk_class(admin, 'IX b').json()['id']
    join(admin, a)
    first = mk_student(admin, a, name='Hüseynov Əli Vüqar oğlu', birth=None).json()
    # yazılış fərqi (ü/u, ə/a) + ata adı yoxdur -> 409 possible_duplicate
    r = mk_student(admin, b, name='Huseynov Ali', birth=None)
    assert r.status_code == 409
    d = _detail(r)
    assert d['possible_duplicate'][0]['id'] == first['id'] and d['possible_duplicate'][0]['class_id'] == a
    assert d['possible_duplicate'][0]['class_name'] == 'IX a'
    # doğum tarixi ziddiyyət təşkil edirsə – başqa uşaqdır
    with_birth = mk_student(admin, a, name='Hüseynov Əli', birth='2011-01-01')
    assert with_birth.status_code == 409                      # birinin doğum tarixi yoxdur -> ziddiyyət yoxdur
    # «Bu başqa şagirddir» -> force
    assert mk_student(admin, b, name='Huseynov Ali', birth=None, force=True).status_code == 200
    # «əlavə sinif kimi əlavə et» yolu
    assert admin.post(f'/api/classes/{b}/members/add', json={'student_ids': [first['id']]}).json()['added'] == 1


# ---------------------------------------------------------------- L2: portal kodu toqquşması
def test_portal_code_retry(world, monkeypatch):
    as_, _ = world
    admin = as_('admin')
    cid = mk_class(admin).json()['id']
    first = mk_student(admin, cid, name='Birinci Şagird Vüsal oğlu', birth=None).json()
    from app.api import students as S
    real = S.next_portal_code
    calls = []

    def fake(db, c, bump=0):
        calls.append(bump)
        return first['portal_code'] if bump == 0 else real(db, c, bump)
    monkeypatch.setattr(S, 'next_portal_code', fake)
    r = mk_student(admin, cid, name='İkinci Tələbə Rəşid oğlu', birth=None)
    assert r.status_code == 200 and r.json()['portal_code'] != first['portal_code'] and calls[:2] == [0, 1]


# ---------------------------------------------------------------- H2 + 6.2: qrup müəllimi
def test_group_teacher_can_edit_and_transfer_but_not_archive(world):
    as_, S = world
    admin, ilqar = as_('admin'), as_('ilqar')
    a = mk_class(admin, 'IX a').json()['id']
    b = mk_class(admin, 'X a').json()['id']
    c3 = mk_class(admin, 'XI a').json()['id']
    for x in (a, b, c3):
        join(admin, x)
    st = mk_student(admin, a, name='Qrupov Nihad Rəşid oğlu', birth=None).json()
    admin.post(f'/api/classes/{b}/members/add', json={'student_ids': [st['id']]})
    join(ilqar, b, subject='Fizika', hours=1, slots={})
    # ilqar yalnız X a-nı tədris edir: şagirdi ümumi siyahıda görür (əsas sinfi IX a olsa da)
    assert [x['id'] for x in ilqar.get('/api/students').json()] == [st['id']]
    assert ilqar.patch(f"/api/students/{st['id']}", json={'full_name': 'Qrupov Nihad Rəşid oğlu (düz.)'}).status_code == 200
    assert ilqar.post(f"/api/students/{st['id']}/reset-pin", json={'pin': '1234'}).status_code == 200
    # arxiv / silmə / bərpa – yalnız əsas sinfin müəllimi və ya admin
    name = ilqar.get('/api/students').json()[0]['full_name']
    assert ilqar.post(f"/api/students/{st['id']}/archive", json={'confirm': name}).status_code == 403
    assert ilqar.post(f"/api/students/{st['id']}/restore").status_code == 403
    # keçirmə: ilqar XI a-nı görmür -> 403; görən sinfə keçirmək olar
    assert ilqar.patch(f"/api/students/{st['id']}", json={'class_id': c3}).status_code == 403
    assert admin.patch(f"/api/students/{st['id']}", json={'class_id': c3}).status_code == 200
    with S() as db:                                                   # L3: tarixçədə from/to
        logs = [l for l in db.query(AuditLog).filter_by(entity='student', entity_id=str(st['id']), action='update')
                if l.details and 'from_class' in l.details]
        assert logs and logs[-1].details['from_class'] == a and logs[-1].details['to_class'] == c3
    # yad məktəbin müəllimi toxuna bilmir
    assert as_('yad').patch(f"/api/students/{st['id']}", json={'full_name': 'Başqa Ad Soyad'}).status_code == 403


# ---------------------------------------------------------------- M1 / M2 / M3
def test_archive_and_delete_class_guards(world):
    as_, S = world
    admin, ilqar = as_('admin'), as_('ilqar')
    cid = mk_class(admin, 'X e').json()['id']
    join(admin, cid)
    mk_student(admin, cid, name='Aktiv Şagird Murad oğlu', birth=None)
    r = admin.post(f'/api/classes/{cid}/archive', json={'confirm': 'X e'})
    d = _detail(r)
    assert r.status_code == 409 and d['params'] == {'n': 1} and 'aktiv şagird' in d['message']
    # admin force
    assert admin.post(f'/api/classes/{cid}/archive', json={'confirm': 'X e', 'force': True}).status_code == 200
    # arxivdəki sinfi silmə: şagird var -> 409
    assert admin.request('DELETE', f'/api/classes/{cid}', json={'confirm': 'X e'}).status_code == 409

    # başqa müəllimin bağlılığı + jurnal yazısı olan sinif silinmir
    c2 = mk_class(admin, 'X f').json()['id']
    join(admin, c2)
    join(ilqar, c2, subject='Fizika', hours=1, slots={})
    with S() as db:
        ta = db.query(TeachingAssignment).filter_by(class_id=c2, subject='Riyaziyyat').one()
        db.add(JournalEntry(assignment_id=ta.id, date=dt.date(2026, 10, 5), period=1))
        db.commit()
    assert admin.post(f'/api/classes/{c2}/archive', json={'confirm': 'X f'}).status_code == 200
    r = admin.request('DELETE', f'/api/classes/{c2}', json={'confirm': 'X f'})
    d = _detail(r)
    assert r.status_code == 409 and d['params'] == {'t': 1, 'j': 1, 'e': 0}

    # boş, bağlılıqsız sinif silinir
    c3 = mk_class(admin, 'X g').json()['id']
    assert admin.post(f'/api/classes/{c3}/archive', json={'confirm': 'X g'}).status_code == 200
    assert admin.request('DELETE', f'/api/classes/{c3}', json={'confirm': 'X g'}).status_code == 200


def test_class_list_counts_without_archived_group_members(world):
    as_, _ = world
    admin = as_('admin')
    a = mk_class(admin, 'IX a').json()['id']
    join(admin, a)
    s1 = mk_student(admin, a, name='Biri Şagird Aydın oğlu', birth=None).json()
    s2 = mk_student(admin, a, name='İkisi Şagird Aydın oğlu', birth=None, force=True).json()
    g = admin.post('/api/classes', json={'name': 'Olimpiada', 'kind': 'qrup'}).json()['id']
    assert admin.put(f'/api/classes/{g}/members', json={'student_ids': [s1['id'], s2['id']]}).status_code == 200
    n = lambda: {c['name']: c['students'] for c in admin.get('/api/classes').json()}
    assert n() == {'IX a': 2, 'Olimpiada': 2}
    assert admin.post(f"/api/students/{s2['id']}/archive", json={'confirm': s2['full_name']}).status_code == 200
    assert n() == {'IX a': 1, 'Olimpiada': 1}


# ---------------------------------------------------------------- M4 / L1 / P2
def test_program_archive_guard_grade_and_hours(world):
    as_, _ = world
    t = as_('ilqar')
    cid = t.post('/api/classes', json={'name': 'X e', 'kind': 'TOM'}).json()['id']
    j = t.post(f'/api/classes/{cid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 3, 'slots': {'0': [1], '2': [3, 4]}}).json()
    ta = j['mine']['ta_id']
    body = {'title': 'Mənim kursum', 'outline': '# Bölmə\nMövzu 1\nMövzu 2\nMövzu 3', 'grade': 10}
    p = t.post('/api/programs/course', json=body).json()
    assert t.post(f"/api/programs/{p['id']}/attach/{ta}", json={}).status_code == 200
    r = t.delete(f"/api/programs/{p['id']}")
    d = _detail(r)
    assert r.status_code == 409 and d['params'] == {'names': 'X e'}
    # L1: sinif 12 olur, 13 olmur
    ok = {'title': 'Mənim kursum', 'grade': 12}
    assert t.patch(f"/api/programs/{p['id']}", json=ok).status_code == 200
    assert t.patch(f"/api/programs/{p['id']}", json={**ok, 'grade': 13}).status_code == 422
    # P2: həftəlik saat uyğunsuzluğu (proqram 3 saat, cədvəl 1 saat)
    from app.models import PlanProgram
    # estimate yalnız oxuyur
    est = t.post(f"/api/programs/{p['id']}/estimate", json={'class_id': cid, 'slots': {'0': [1]}}).json()
    assert est['hours_mismatch'] is False and est['lint'] == [] and est['class_hours'] == 1      # kursda weekly_hours yoxdur
    _ = PlanProgram


def test_hours_mismatch_in_estimate_and_list(world):
    as_, S = world
    t = as_('ilqar')
    cid = t.post('/api/classes', json={'name': 'X e', 'kind': 'TOM'}).json()['id']
    j = t.post(f'/api/classes/{cid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 3, 'slots': {'0': [1], '2': [3, 4]}}).json()
    ta = j['mine']['ta_id']
    with S() as db:
        from app.models import PlanProgram
        from app.programs import ensure_builtin
        ensure_builtin(db)
        p = db.query(PlanProgram).filter(PlanProgram.key == 'dim-sinif-testleri-10').one()
        p.weekly_hours = 2
        db.commit()
        pid = p.id
    row = next(x for x in t.get('/api/programs', params={'ta_id': ta}).json() if x['id'] == pid)
    assert row['hours_mismatch'] is True and row['class_hours'] == 3
    est = t.post(f'/api/programs/{pid}/estimate', json={'class_id': cid, 'slots': {'0': [1], '2': [3, 4]}}).json()
    assert est['hours_mismatch'] is True and est['program_hours'] == 2 and est['class_hours'] == 3
    assert isinstance(est['lint'], list)
    pv = t.get(f'/api/programs/{pid}/preview/{ta}').json()
    assert 'lint' in pv and pv['hours_mismatch'] is True


# ---------------------------------------------------------------- P1: lint_plan
YEAR = SimpleNamespace(start=dt.date(2026, 9, 15), sem1_end=dt.date(2027, 1, 26), sem2_start=dt.date(2027, 2, 1), end=dt.date(2027, 6, 14))


def L(sem, typ='formativ', topic='Mövzu', date=None):
    return {'semester': sem, 'assessment_type': typ, 'topic': topic, 'date': date}


def keys(w):
    return [x['key'] for x in w]


def test_lint_clean_plan():
    d = lambda m, day: dt.date(2026 if m > 8 else 2027, m, day)
    plan = ([L(1, date=d(9, 16)), L(1, date=d(9, 20))] + [L(1, date=d(10, 5)) for _ in range(3)] + [L(1, 'KSQ', date=d(10, 30))]
            + [L(1, topic='Təkrar: yarımil', date=d(12, 20)), L(1, 'BSQ', date=d(1, 20))]
            + [L(2, date=d(2, 3))] + [L(2, 'KSQ', date=d(3, 10)), L(2, topic='İllik təkrar', date=d(6, 1)), L(2, 'BSQ', date=d(6, 10))])
    assert lint_plan(plan, YEAR) == []


def test_lint_rules():
    d = dt.date
    plan = [L(1, 'KSQ', date=d(2026, 9, 20)), L(1, 'KSQ', date=d(2026, 10, 1)), L(1, 'BSQ', date=d(2026, 11, 1)),
            L(1, 'BSQ', date=d(2026, 11, 2)), L(1, 'formativ', date=d(2027, 2, 5)),
            L(2, 'formativ', date=d(2027, 3, 1)), L(2, 'BSQ', date=d(2027, 6, 1)), L(2, 'formativ', date=d(2027, 6, 2))]
    w = lint_plan(plan, YEAR)
    ks = keys(w)
    assert '{sem}-ci yarımildə {n} BSQ var – 1 olmalıdır' in ks                          # 1-ci yarımildə 2 BSQ
    assert '{sem}-ci yarımildə iki KSQ ardıcıl gəlir (dərs № {a} və {b})' in ks
    assert '{sem}-ci yarımildə KSQ ilk 2 həftədə planlaşdırılıb (dərs № {seq})' in ks
    assert '{sem}-ci yarımildə {n} dərs yarımilin tarixlərindən kənardadır' in ks         # 5.02.2027 1-ci yarımildə
    assert '{sem}-ci yarımildə KSQ yoxdur – ən azı 1 KSQ olmalıdır' in ks                 # 2-ci yarımildə KSQ yoxdur
    assert '{sem}-ci yarımildə BSQ yarımilin son dərsi deyil' in ks
    assert all(x['level'] == 'warn' and x['message'] and 'params' in x for x in w)
    # BSQ-dan əvvəlki dərs təkrar deyil
    one = lint_plan([L(1, 'KSQ', date=d(2026, 11, 1)), L(1, topic='Yeni mövzu'), L(1, 'BSQ')], YEAR)
    assert '{sem}-ci yarımildə BSQ-dan əvvəlki dərs (№ {seq}) təkrar dərsi deyil' in keys(one)
    # summativ yoxdursa yoxlanmır
    assert lint_plan(plan, YEAR, summative=False) == []


# ---------------------------------------------------------------- roster-health
def test_roster_health(world):
    as_, S = world
    admin, ilqar = as_('admin'), as_('ilqar')
    assert ilqar.get('/api/admin/roster-health').status_code == 403
    empty = mk_class(admin, 'XI boş').json()['id']
    cid = mk_class(admin, 'X e').json()['id']
    join(admin, cid)
    mk_student(admin, cid, name='Birinci Şagird Vüsal oğlu', birth=None)
    mk_student(admin, cid, name='Birinci Şagird', birth='2011-01-01', force=True)           # təkrar cüt
    r = admin.get('/api/admin/roster-health')
    assert r.status_code == 200
    c = r.json()['categories']
    assert {x['name'] for x in c['classes_no_students']['examples']} == {'XI boş'}
    assert {x['name'] for x in c['classes_no_teacher']['examples']} == {'XI boş'}
    assert c['students_no_birth_date']['count'] == 1
    assert c['duplicate_pairs']['count'] == 1
    assert c['assignments_no_program']['count'] == 1
    assert c['students_no_account']['count'] == 0
    assert c['students_pin_unknown']['count'] == 0                                         # ilkin PIN saxlanılıb
    assert set(c) >= {'classes_no_grade', 'lessons_attendance_incomplete', 'students_no_recent_mark'}
    _ = empty


def test_roster_health_attendance_and_stale_marks(world):
    as_, S = world
    admin = as_('admin')
    cid = mk_class(admin, 'X e').json()['id']
    ta = join(admin, cid).json()['mine']['ta_id']
    s1 = mk_student(admin, cid, name='Birinci Şagird Vüsal oğlu', birth=None).json()['id']
    s2 = mk_student(admin, cid, name='İkinci Tələbə Rəşid oğlu', birth=None).json()['id']
    from app.models import Attendance, Mark
    with S() as db:
        e = JournalEntry(assignment_id=ta, date=dt.date.today() - dt.timedelta(days=30), period=1)
        db.add(e)
        db.flush()
        db.add(Attendance(entry_id=e.id, student_id=s1, status='var'))                    # s2 üçün davamiyyət yoxdur
        db.add(Mark(entry_id=e.id, student_id=s1, kind='şifahi', grade=5))
        db.commit()
    c = admin.get('/api/admin/roster-health').json()['categories']
    assert c['lessons_attendance_incomplete']['count'] == 1
    stale = {x['id'] for x in c['students_no_recent_mark']['examples']}
    assert stale == {s1, s2}                                                                # hər ikisinin son qiyməti ≥ 14 gün əvvəldir
