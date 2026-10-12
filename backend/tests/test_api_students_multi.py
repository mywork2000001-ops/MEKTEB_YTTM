"""Bir şagird bir neçə sinifdə + təkrar şagirdlərin birləşdirilməsi (docs/sagird-coxlu-sinif-ve-birlesme-promtu.md).
Real nümunə: Nihad – IX və XI, Hüseyn Əhmədov – X və XI (fərdi hazırlıqda hər sinifdə ayrıca qeyd yaranmışdı)."""
import datetime as dt

from app.models import Student, TaskAttempt, TeachingAssignment, User
from app.security import hash_password

from .test_api_portal import UTC, clock, mk_task, setup, student_client  # noqa: F401 – clock fixture


def _second_class(admin, S, name='X c'):
    xc = admin.post('/api/classes', json={'name': name}).json()['id']
    admin.post(f'/api/classes/{xc}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 1, 'slots': {}})
    with S() as db:
        return xc, db.query(TeachingAssignment).filter_by(class_id=xc).one().id


def _raw_student(S, name, class_id, code, birth=None):
    """Köhnə yolla yaranmış təkrar (qeydiyyat linki / idxal) – API-nin təkrar yoxlamasından keçmədən."""
    with S() as db:
        u = User(role='student', login=code, password_hash=hash_password('1234'), full_name=name, school_id=1)
        db.add(u)
        db.flush()
        s = Student(school_id=1, class_id=class_id, full_name=name, portal_code=code, user_id=u.id, birth_date=birth)
        db.add(s)
        db.commit()
        return s.id


def test_student_in_two_classes(world, clock):
    as_, S = world
    admin, ta, cid, st, ids = setup(world)                                     # X e
    xc, ta_c = _second_class(admin, S)
    nihad = st[0]
    assert admin.post(f'/api/classes/{xc}/members/add', json={'student_ids': [nihad['id']]}).json() == {'added': 1, 'members': 1}
    assert nihad['id'] in {x['id'] for x in admin.get('/api/students', params={'class_id': xc}).json()}
    assert next(c for c in admin.get('/api/classes').json() if c['id'] == xc)['students'] == 1
    g = admin.get(f'/api/classes/student/{nihad["id"]}/groups').json()
    row = next(x for x in g['groups'] if x['id'] == xc)
    assert g['class']['name'] == 'X e' and (row['kind'], row['member']) == ('əlavə sinif', True)
    # şagird iki sinfin testini görür; sinfin siyahısında (roster) da var
    t = mk_task(admin, ta_c, ids).json()
    s = student_client(nihad['portal_code'], nihad['initial_pin'])
    assert t['id'] in {x['id'] for x in s.get('/api/portal/tasks').json()}
    assert nihad['id'] in {r['student_id'] for r in admin.get(f'/api/tasks/{ta_c}/{t["id"]}').json()['rows']}
    # əsas sinfə əlavə olunmur; çıxarma – şagird əsas sinfində qalır
    assert admin.post(f'/api/classes/{cid}/members/add', json={'student_ids': [nihad['id']]}).status_code == 400
    assert admin.delete(f'/api/classes/{xc}/members/{nihad["id"]}').json() == {'ok': True}
    assert admin.get('/api/students', params={'class_id': xc}).json() == []
    assert as_('ilqar').post(f'/api/classes/{xc}/members/add', json={'student_ids': [nihad['id']]}).status_code == 403


def test_duplicates_and_merge(world, clock):
    as_, S = world
    admin, ta, cid, st, ids = setup(world)
    xc, ta_c = _second_class(admin, S)
    a = _raw_student(S, 'Nihad', cid, 'XE-090')                               # IX-dəki qeyd
    b = _raw_student(S, 'Nihad Əliyev', xc, 'XC-090')                         # XI-dəki qeyd (adı tam yazılıb)
    h1 = _raw_student(S, 'Hüseyn Əhmədov', cid, 'XE-091')
    h2 = _raw_student(S, 'Əhmədov Hüseyn', xc, 'XC-091')
    _raw_student(S, 'Nihad Quliyev', xc, 'XC-092', dt.date(2010, 1, 1))
    _raw_student(S, 'Nihad Quliyev', cid, 'XE-092', dt.date(2011, 5, 5))     # doğum tarixi fərqli – başqa uşaq
    d = admin.get('/api/students/duplicates').json()
    pairs = {frozenset((x['a']['id'], x['b']['id'])): x['level'] for x in d}
    assert pairs[frozenset((h1, h2))] == 'ad və soyad eyni' and pairs[frozenset((a, b))] == 'oxşar ad'
    assert not any({x['a']['full_name'], x['b']['full_name']} == {'Nihad Quliyev'} for x in d)
    assert as_('ilqar').get('/api/students/duplicates').status_code == 403

    # XI-dəki qeyd testi yazıb; birləşmədən sonra cəhd saxlanana keçir, şagird hər iki sinifdədir
    t = mk_task(admin, ta_c, ids).json()
    clock.t = dt.datetime(2026, 9, 29, 15, 10, tzinfo=UTC)
    sb = student_client('XC-090', '1234')
    sb.post(f'/api/portal/tasks/{t["id"]}/start')
    sb.post(f'/api/portal/tasks/{t["id"]}/submit', json={'answers': {}})
    assert admin.post('/api/students/merge', json={'keep_id': a, 'drop_id': b, 'confirm': 'yanlış'}).status_code == 400
    r = admin.post('/api/students/merge', json={'keep_id': a, 'drop_id': b, 'confirm': 'Nihad'})
    assert r.status_code == 200 and r.json()['moved'] >= 1, r.text
    with S() as db:
        assert db.query(TaskAttempt).filter_by(task_id=t['id']).one().student_id == a
        drop = db.get(Student, b)
        assert drop.archived_at is not None and 'XE-090' in drop.left_reason
        assert db.get(User, drop.user_id).archived_at is not None
    assert a in {x['id'] for x in admin.get('/api/students', params={'class_id': xc}).json()}   # IX + XI
    assert admin.get(f'/api/tasks/{ta_c}/{t["id"]}').json()['summary']['təhvil verib'] == 1
    assert not any(b in (x['a']['id'], x['b']['id']) for x in admin.get('/api/students/duplicates').json())


def test_merge_attempt_conflict_keeps_submitted(world, clock):
    """Hər iki qeyd eyni testə başlayıb: saxlananınkı boşdur, silinəninki təhvil verilib – təhvil verilmiş qalır."""
    as_, S = world
    admin, ta, cid, st, ids = setup(world)
    xc, ta_c = _second_class(admin, S)
    a = _raw_student(S, 'Hüseyn Əhmədov', cid, 'XE-095')
    b = _raw_student(S, 'Əhmədov Hüseyn', xc, 'XC-095')
    admin.post(f'/api/classes/{xc}/members/add', json={'student_ids': [a]})
    t = mk_task(admin, ta_c, ids).json()
    clock.t = dt.datetime(2026, 9, 29, 15, 10, tzinfo=UTC)
    student_client('XE-095', '1234').post(f'/api/portal/tasks/{t["id"]}/start')
    sb = student_client('XC-095', '1234')
    sb.post(f'/api/portal/tasks/{t["id"]}/start')
    sb.post(f'/api/portal/tasks/{t["id"]}/submit', json={'answers': {}})
    r = admin.post('/api/students/merge', json={'keep_id': a, 'drop_id': b, 'confirm': 'Hüseyn Əhmədov'}).json()
    assert r['conflicts'] == 1
    with S() as db:
        at = db.query(TaskAttempt).filter_by(task_id=t['id']).all()
        assert len(at) == 1 and at[0].student_id == a and at[0].submitted_at is not None


def test_merge_named_nihad_huseyn(world, clock):
    """Göstəriş: Nihad – IX və XI (əsas XI), Hüseyn Əhmədov – X və XI (əsas X); qeyri-müəyyən halda heç nə edilmir."""
    from app.api.students import merge_named
    from app.models import GroupMember
    as_, S = world
    admin = as_('admin')
    ids = {}
    for name in ('Buraxılış IX sinif', '10-cu sinif', '11A'):
        ids[name] = admin.post('/api/classes', json={'name': name}).json()['id']
    n9 = _raw_student(S, 'Nihad', ids['Buraxılış IX sinif'], 'BI-001')
    n11 = _raw_student(S, 'Nihad Əliyev', ids['11A'], '11A-001')
    h10 = _raw_student(S, 'Hüseyn Əhmədov', ids['10-cu sinif'], '10-001')
    h11 = _raw_student(S, 'Əhmədov Hüseyn', ids['11A'], '11A-002')
    with S() as db:
        log = merge_named(db, [({'Nihad'}, {11: True, 9: False}), ({'Hüseyn', 'Əhmədov'}, {10: True, 11: False})])
        db.commit()
        assert len([x for x in log if 'merged' in x]) == 2, log
        assert db.get(Student, n9).archived_at and not db.get(Student, n11).archived_at      # Nihad – əsas XI
        assert db.get(Student, h11).archived_at and not db.get(Student, h10).archived_at     # Hüseyn – əsas X
        assert db.get(GroupMember, (ids['Buraxılış IX sinif'], n11)) and db.get(GroupMember, (ids['11A'], h10))
        assert db.get(Student, n11).portal_code == '11A-001' and db.get(Student, h10).portal_code == '10-001'
    # təkrar çağırış – artıq birləşib, heç nə dəyişmir; qeyri-müəyyən (iki Nihad IX-də) – ötürülür
    _raw_student(S, 'Nihad Babayev', ids['Buraxılış IX sinif'], 'BI-002')
    _raw_student(S, 'Nihad Quliyev', ids['Buraxılış IX sinif'], 'BI-003')
    with S() as db:
        log = merge_named(db, [({'Nihad'}, {11: True, 9: False})])
        assert not any('merged' in x for x in log) and 'ambiguous' in log[0]
