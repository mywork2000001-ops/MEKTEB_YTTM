"""Məşğələ qrupları «Siniflər» bölməsində (docs/mesgele-qruplari-sinifler-promtu.md): başqa sinifdən tək şagird əlavə
etmək, çıxarmaq, şagird kartı, icazələr (başqa fənn / başqa müəllim / arxiv)."""
import datetime as dt

from app.models import TeachingAssignment

from .test_api_portal import UTC, clock, setup  # noqa: F401 – clock fixture

BODY = {'title': 'Olimpiada qrupu', 'format': 'əyani', 'schedule': [{'weekday': 5, 'start': '10:00', 'end': '11:00'}],
        'starts_on': '2026-10-03', 'ends_on': '2026-10-17'}


def test_group_members_from_classes(world, clock, monkeypatch):
    as_, S = world
    monkeypatch.setattr('app.api.extra.now', clock)
    clock.t = dt.datetime(2026, 10, 2, 8, 0, tzinfo=UTC)
    admin, ta, cid, st, ids = setup(world)                                     # X e – 3 şagird
    xc = admin.post('/api/classes', json={'name': 'X c'}).json()['id']
    admin.post(f'/api/classes/{xc}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 1, 'slots': {}})
    xs = [admin.post('/api/students', json={'full_name': f'X c Şagird{i} oğlu', 'class_id': xc}).json() for i in range(2)]
    fz = admin.post('/api/classes', json={'name': 'X f'}).json()['id']
    admin.post(f'/api/classes/{fz}/join', json={'subject': 'Fizika', 'weekly_hours': 1, 'slots': {}})
    fs = admin.post('/api/students', json={'full_name': 'Fizika Şagird oğlu', 'class_id': fz}).json()
    c = admin.post('/api/extra', json={**BODY, 'ta_ids': [ta], 'student_ids': [st[0]['id']]}).json()
    gid = c['id']

    # namizədlər: yalnız eyni fənn (Riyaziyyat) – X e və X c; üzv işarəli
    cand = admin.get(f'/api/extra/{gid}/candidates').json()
    assert [x['class_name'] for x in cand] == ['X c', 'X e']
    assert next(s for s in cand[1]['students'] if s['id'] == st[0]['id'])['member']
    with S() as db:                                                            # səviyyə (Jurnal → Səviyyə qrupları)
        from app.models import LevelOverride
        db.add(LevelOverride(assignment_id=ta, student_id=st[1]['id'], level='Zəif'))
        db.commit()
    cand = admin.get(f'/api/extra/{gid}/candidates').json()
    assert next(s for s in cand[1]['students'] if s['id'] == st[1]['id'])['level'] == 'Zəif'

    # başqa sinifdən tək şagird – sinfin qalanı gəlmir
    r = admin.post(f'/api/extra/{gid}/members', json={'student_ids': [xs[0]['id']]}).json()
    assert r == {'added': 1, 'students': 2}
    m = {x['student_id']: x['class_name'] for x in admin.get(f'/api/extra/{gid}').json()['members']}
    assert m == {st[0]['id']: 'X e', xs[0]['id']: 'X c'}
    assert admin.post(f'/api/extra/{gid}/members', json={'student_ids': [fs['id']]}).status_code == 400   # başqa fənn
    assert as_('ilqar').post(f'/api/extra/{gid}/members', json={'student_ids': [xs[1]['id']]}).status_code == 404

    # şagird kartı
    assert admin.get(f'/api/extra/student/{xs[1]["id"]}').json() == [{'id': gid, 'title': 'Olimpiada qrupu', 'subject': 'Riyaziyyat',
                                                                       'format': 'əyani', 'member': False}]
    assert admin.get(f'/api/extra/student/{xs[0]["id"]}').json()[0]['member'] is True
    assert admin.get(f'/api/extra/student/{fs["id"]}').json() == []

    # çıxarma: X e şagirdi gedir – X e sinfi də qrupdan çıxır; sonuncu şagird qalmalıdır; arxiv – dəyişmir
    assert admin.delete(f'/api/extra/{gid}/members/{st[0]["id"]}').json() == {'students': 1}
    with S() as db:
        assert db.get(TeachingAssignment, ta) is not None
    aud = admin.get(f'/api/extra/{gid}').json()['audience']
    assert aud['student_ids'] == [xs[0]['id']] and len(aud['ta_ids']) == 1
    assert admin.delete(f'/api/extra/{gid}/members/{xs[0]["id"]}').status_code == 400
    assert admin.delete(f'/api/extra/{gid}/members/{st[1]["id"]}').status_code == 404
    admin.post(f'/api/extra/{gid}/archive')
    assert admin.post(f'/api/extra/{gid}/members', json={'student_ids': [xs[1]['id']]}).status_code == 400
