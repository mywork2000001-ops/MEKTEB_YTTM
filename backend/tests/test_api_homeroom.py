"""Dərs sayı, müvəffəqiyyət (müvəffəqiyyət/keyfiyyət/SOU) və sinif rəhbəri."""
import datetime as dt

from app.performance import category, metrics

from .test_api_analytics import setup


def test_metrics_and_category():
    m = metrics([5, 4, 3, 2, None])
    assert m['graded'] == 4 and m['not_graded'] == 1
    assert m['success_pct'] == 75.0 and m['quality_pct'] == 50.0
    assert m['sou'] == 54.0 and m['avg'] == 3.5
    assert metrics([None])['success_pct'] is None
    assert category([5, 5, None]) == 'Əlaçı'
    assert category([5, 4]) == 'Zərbəçi'
    assert category([5, 3, 4]) == 'Bir «3»-lü'
    assert category([3, 3]) == '«3»-lü'
    assert category([5, 2]) == 'Geridə qalan'
    assert category([None]) is None


def test_lesson_counts(world, monkeypatch):
    monkeypatch.setattr('app.api.homeroom.today', lambda: dt.date(2026, 9, 30))
    c, ta, good, weak, new = setup(world)
    r = c.get(f'/api/analytics/{ta}/lessons').json()
    y = r['year']
    assert y['plan_total'] == 40 and y['weekly_hours'] == 5
    assert y['due'] == 12                              # 15.09–30.09 iş günləri
    assert y['written'] == 10 and y['missing'] == 2    # 29 və 30 sentyabr yazılmayıb
    assert [m['date'] for m in y['missing_list']] == ['2026-09-29', '2026-09-30']
    assert y['covered'] == 12 and y['remaining'] == 28
    assert r['semesters'][0]['plan_total'] == 40 and r['semesters'][1]['plan_total'] == 0
    assert y['date_mismatch'] == 39 and y['mismatch_list'][0]['seq'] == 2   # planda hamısı 15.09 yazılıb


def test_performance(world):
    c, ta, good, weak, new = setup(world)
    p = c.get(f'/api/analytics/{ta}/performance', params={'semester': 1}).json()
    rows = {r['student_id']: r for r in p['students']}
    assert rows[good]['grade'] == 5 and rows[good]['source'] == 'formativ'
    assert rows[weak]['grade'] == 2 and rows[new]['grade'] is None
    s = p['summary']
    assert s['graded'] == 2 and s['success_pct'] == 50.0 and s['quality_pct'] == 50.0


def test_homeroom_assign_and_summary(world, monkeypatch):
    as_, _ = world
    monkeypatch.setattr('app.api.homeroom.today', lambda: dt.date(2026, 9, 16))
    c, ta, good, weak, new = setup(world)
    ilqar = as_('ilqar')
    cid = c.get('/api/classes').json()[0]['id']
    # İlqar – rəhbəri olmayan sinfi özü götürür; sonra admin başqasına verə bilər, İlqar isə başqasının sinfini ala bilməz
    assert ilqar.get(f'/api/homeroom/{cid}').status_code == 403
    me = ilqar.get('/api/auth/me').json()['id']
    assert ilqar.put(f'/api/classes/{cid}/homeroom', json={'teacher_id': me}).status_code == 200
    assert c.get('/api/classes').json()[0]['homeroom']['name'] == 'Nəcəfov İlqar'
    assert [x['id'] for x in ilqar.get('/api/homeroom').json()] == [cid]
    admin_id = c.get('/api/auth/me').json()['id']
    assert ilqar.put(f'/api/classes/{cid}/homeroom', json={'teacher_id': admin_id}).status_code == 403

    h = ilqar.get(f'/api/homeroom/{cid}', params={'semester': 1}).json()
    assert h['class']['homeroom']['id'] == me
    assert [s['subject'] for s in h['subjects']] == ['Riyaziyyat'] and h['subjects'][0]['teacher'] == 'Həsənov Fərid'
    rows = {r['student_id']: r for r in h['students']}
    assert rows[good]['category'] == 'Əlaçı' and rows[weak]['category'] == 'Geridə qalan' and rows[new]['category'] is None
    assert rows[weak]['absence_warning'] and rows[weak]['missed'] == 5
    assert h['summary']['success_pct'] == 50.0 and h['summary']['quality_pct'] == 50.0
    assert h['summary']['absent_today'] == []           # 16.09 zəif şagird gəlib (tək günlər «var»)
    # rəhbər başqa müəllimin jurnalını aça bilmir – yalnız yekun göstəricilər
    assert ilqar.get(f'/api/journal/{ta}/summary').status_code == 404

    # valideyn məlumatı – yalnız rəhbər/admin
    r = ilqar.put(f'/api/homeroom/{cid}/students/{weak}/guardians',
                  json=[{'name': 'Anası Leyla', 'relation': 'ana', 'phone': '+994 50 000 00 00'}])
    assert r.status_code == 200 and r.json()['guardians'][0]['phone'] == '+994 50 000 00 00'
    assert ilqar.put(f'/api/homeroom/{cid}/students/{weak}/guardians', json=[{'name': 'X', 'phone': 'abc'}]).status_code == 422

    # rəhbərin jurnalı
    e = ilqar.post(f'/api/homeroom/{cid}/events', json={'date': '2026-09-20', 'kind': 'valideyn iclası',
                                                         'title': 'I rüb', 'absent_ids': [weak]})
    assert e.status_code == 200 and e.json()['absent'] == ['Zəif Şagird qızı']
    assert ilqar.post(f'/api/homeroom/{cid}/events', json={'date': '2026-09-20', 'kind': 'tədbir', 'title': 'Konsert',
                                                            'absent_ids': [99999]}).status_code == 400
    assert len(c.get(f'/api/homeroom/{cid}/events').json()['events']) == 1       # admin görür
    assert ilqar.delete(f'/api/homeroom/{cid}/events/{e.json()["id"]}').status_code == 200

    # özünü çıxarır
    assert ilqar.put(f'/api/classes/{cid}/homeroom', json={'teacher_id': None}).status_code == 200
    assert ilqar.get('/api/homeroom').json() == []
    assert c.get('/api/homeroom').json() == []                                   # admin: yalnız özününkü
    assert [x['id'] for x in c.get('/api/homeroom', params={'all': 1}).json()] == [cid]   # «bütün siniflər»


def test_homeroom_other_school(world):
    as_, _ = world
    c, ta, *_ = setup(world)
    cid = c.get('/api/classes').json()[0]['id']
    yad = as_('yad')
    assert yad.get(f'/api/homeroom/{cid}').status_code == 404
    assert yad.put(f'/api/classes/{cid}/homeroom', json={'teacher_id': None}).status_code == 404
