"""Sınaq seriyası: yaratma, siyahı/oxu, dəyişmə, silmə və icazəsiz istifadəçinin rədd edilməsi."""
from .test_api_portal import clock, setup  # noqa: F401 – clock fixture


def _body(ta, **kw):
    return {'title': 'Həftəlik sınaq', 'targets': [{'ta_id': ta}], 'sources': ['sinaqlar'], 'auto_new': True,
            'period': 'week', 'weekday': 2, 'open_time': '15:00', **kw}


def test_create_list_read(world, clock):
    admin, ta, cid, st, ids = setup(world)
    r = admin.post('/api/exam-series', json=_body(ta))
    assert r.status_code == 200, r.text
    s = r.json()
    assert s['title'] == 'Həftəlik sınaq' and s['id']
    lst = admin.get('/api/exam-series')
    assert lst.status_code == 200 and [x['id'] for x in lst.json()] == [s['id']]
    p = admin.patch(f'/api/exam-series/{s["id"]}', json={'active': False, 'title': 'Yeni ad'})
    assert p.status_code == 200 and p.json()['title'] == 'Yeni ad'
    assert admin.delete(f'/api/exam-series/{s["id"]}').json() == {'ok': True}
    assert admin.get('/api/exam-series').json() == []


def test_validation(world, clock):
    admin, ta, cid, st, ids = setup(world)
    assert admin.post('/api/exam-series', json=_body(ta, weekday=None)).status_code == 422       # həftənin günü yoxdur
    assert admin.post('/api/exam-series', json=_body(ta, queue=[], auto_new=False)).status_code == 422
    assert admin.post('/api/exam-series', json=_body(ta, sources=['yanlis'])).status_code == 422


def test_foreign_user_rejected(world, clock):
    as_, S = world
    admin, ta, cid, st, ids = setup(world)
    s = admin.post('/api/exam-series', json=_body(ta)).json()
    yad = as_('yad')                                                 # başqa məktəbin müəllimi
    assert yad.post('/api/exam-series', json=_body(ta)).status_code in (403, 404)    # özgə dərsə seriya
    assert yad.patch(f'/api/exam-series/{s["id"]}', json={'active': False}).status_code == 404
    assert yad.delete(f'/api/exam-series/{s["id"]}').status_code == 404
    assert yad.get('/api/exam-series').json() == []
    assert len(admin.get('/api/exam-series').json()) == 1
