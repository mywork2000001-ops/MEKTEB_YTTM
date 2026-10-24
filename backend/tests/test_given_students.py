"""Sınaq təkrarsızlığı şagird səviyyəsində: sinif + qrup, eyni məzmunlu fayllar, əl ilə yaratma (domain/given.py)."""
import datetime as dt

from sqlalchemy import select

from app.domain.given import given_students, same_as
from app.models import BankFile, BankQuestion, ExamSeries, GroupMember, OnlineTask

from .test_api_portal import clock, setup  # noqa: F401 – clock fixture
from .test_exam_series_daily import _body, _tick


def _file(S, label, texts):
    with S() as db:
        f = BankFile(source_key='p012', lesson=f'{label}.html', label=label, url='http://x/' + label, grades=[10], kind='sinaq',
                     question_count=len(texts))
        db.add(f)
        db.flush()
        for n, tx in enumerate(texts):
            db.add(BankQuestion(file_id=f.id, n=n + 1, kind='mcq', text={'az': tx}, options=[{'az': '1'}, {'az': '2'}],
                                correct=0, content_hash=f'{label}{n}'))
        db.commit()
        return f.id


def _group(admin, S, cid, members):
    g = admin.post('/api/classes', json={'name': 'X e (riyaziyyat qrupu)', 'kind': 'qrup', 'parent_id': cid}).json()['id']
    admin.post(f'/api/classes/{g}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 1, 'slots': {}})
    with S() as db:
        db.add_all([GroupMember(group_id=g, student_id=m) for m in members])
        db.commit()
    return next(l['id'] for l in admin.get('/api/my/lessons').json() if l['class_id'] == g)


def test_group_and_class_get_file_once(world, clock):
    _, S = world
    admin, ta, cid, st, ids = setup(world)
    ta_g = _group(admin, S, cid, [st[0]['id'], st[1]['id']])
    f1 = _file(S, 'A-1', ['aaa 1+1 hesabla', 'bbb 2+2 hesabla', 'ccc 3+3 hesabla', 'ddd 4+4 hesabla', 'eee 5+5 hesabla'])
    f2 = _file(S, 'A-1-kopya', ['AAA 1+1  hesabla', 'bbb 2+2 hesabla', 'ccc 3+3 hesabla', 'ddd 4+4 hesabla', 'eee 5+5 hesabla'])
    f3 = _file(S, 'A-1-yarim', ['aaa 1+1 hesabla', 'bbb 2+2 hesabla', 'ccc 3+3 hesabla', 'xxx yeni 1', 'yyy yeni 2'])
    with S() as db:
        assert f2 in same_as(db, f1) and f3 not in same_as(db, f1)               # 100% eyni / 60% eyni
    sid = admin.post('/api/exam-series', json=_body(ta_g, [f1], targets=[{'ta_id': ta_g}, {'ta_id': ta}])).json()['id']
    clock.t = dt.datetime(2026, 9, 29, 12, 0, tzinfo=dt.timezone.utc)
    _tick(S, sid)
    with S() as db:
        tasks = {t.assignment_id: t for t in db.scalars(select(OnlineTask).where(OnlineTask.kind == 'sinaq'))}
        assert tasks[ta_g].student_ids is None                                   # qrup – bütün üzvlər
        assert tasks[ta].student_ids == [st[2]['id']]                            # sinif – qrupda olmayan şagird
        g = given_students(db, [f1, f2, f3], {s['id'] for s in st})
        assert g[f1] == g[f2] == {s['id'] for s in st} and g[f3] == set()
    # məzmunu eyni fayl: hamı artıq alıb – atlanır; 60% eyni fayl – atlanmır
    sid2 = admin.post('/api/exam-series', json=_body(ta, [f2, f3], title='İkinci')).json()['id']
    _tick(S, sid2)
    with S() as db:
        done = [d['file_id'] for d in db.get(ExamSeries, sid2).done]
        assert done == [f3]                                                      # f2 atlandı, 60% eyni f3 göndərildi


def test_manual_exam_student_level_409(world, clock, monkeypatch):
    monkeypatch.setattr('app.api.exams_online.now', clock)
    _, S = world
    admin, ta, cid, st, ids = setup(world)
    ta_g = _group(admin, S, cid, [st[0]['id'], st[1]['id']])
    clock.t = dt.datetime(2026, 9, 29, 10, 0, tzinfo=dt.timezone.utc)
    win = {'opens_at': '2026-09-29T11:00:00Z', 'closes_at': '2026-09-29T14:00:00Z'}
    assert admin.post('/api/exams-online', json={'title': 'S1', 'bank_ids': ids, 'targets': [{'ta_id': ta, **win}]}).status_code == 200
    body = {'title': 'S1 qrup', 'bank_ids': ids, 'targets': [{'ta_id': ta_g, **win}]}
    r = admin.post('/api/exams-online', json=body)
    assert r.status_code == 409 and '2 şagirdinə' in r.json()['detail']['message']        # qrup üzvləri sinifdə artıq alıb
    assert admin.post('/api/exams-online', json={**body, 'allow_repeat': True}).status_code == 200
