"""Dəftər yoxlaması: AI (mock) və əl ilə işarə – ai_check, icazələr, check-all, CSV, şagird görünüşü."""
import json

import pytest

from app import defter as D
from tests.test_api_materials import setup, student

JPG = b'\xff\xd8jpg'
SUBS = ['Tənliklər', 'Bərabərsizliklər']


@pytest.fixture
def env(world, monkeypatch, tmp_path):
    monkeypatch.setattr('app.api.defter.R.key_pool', lambda db, tid: [{'provider': 'gemini', 'key': 'k', 'model': 'm', 'label': 'x'}])
    c, ta, st = setup(world, monkeypatch, tmp_path)
    task = c.post(f'/api/materials/{ta}', data={'kind': 'task', 'title': 'Tənliklər ev işi', 'body': 'Tapşırıqlar 1-10'}).json()['id']
    return world, c, ta, st, task


def fake(monkeypatch, out=None, fail=None):
    calls = []

    def v(cfg, images, system, text):
        calls.append(len(images))
        if fail and len(calls) in fail:
            raise RuntimeError('boom')
        return out if out is not None else json.dumps({
            'legible': True, 'items': [{'subtopic': 'Tənliklər', 'status': 'done', 'wrong': [], 'note': ''},
                                       {'subtopic': 'Bərabərsizliklər', 'status': 'weird', 'wrong': ['3', '5'], 'note': 'x'}],
            'summary_az': 'Yaxşı', 'student_comment': {'az': 'Əla', 'ru': 'Отлично', 'en': 'Great'}})
    monkeypatch.setattr(D, 'vision_json', v)
    return calls


def submit(st, task, name='cavab.jpg'):
    s = student(st)
    assert s.post(f'/api/portal/materials/{task}/submit', data={'text': 'x'}, files={'file': (name, JPG, 'image/jpeg')}).status_code == 200
    return s


def sid_of(c, ta, task, stu):
    rows = c.get(f'/api/materials/{ta}/{task}/submissions').json()['rows']
    return next(r for r in rows if r['student_id'] == stu['id'])['submission']['id']


def test_normalize_statuses():
    r = D.normalize({'items': [{'subtopic': 'A', 'status': 'DONE'}, {'subtopic': 'B', 'status': 'bad'}], 'student_comment': {'az': 'x'}}, ['A', 'B', 'C'])
    assert [i['status'] for i in r['items']] == ['done', 'missing', 'missing']
    r = D.normalize({'legible': False, 'items': [], 'student_comment': {'az': 'x'}}, ['A'])
    assert r['items'][0]['status'] == 'illegible'
    with pytest.raises(D.DefterError):
        D.normalize({}, ['A'])
    with pytest.raises(D.DefterError):
        D.normalize('x', ['A'])


def test_check_writes_ai_check_and_student_sees_own_lang(env, monkeypatch):
    world, c, ta, st, task = env
    calls = fake(monkeypatch)
    s = submit(st[0], task)
    s.patch('/api/auth/prefs', json={'language': 'ru', 'theme': 'forest'})
    sid = sid_of(c, ta, task, st[0])
    r = c.post(f'/api/materials/{task}/submissions/{sid}/check', json={'subtopics': SUBS})
    assert r.status_code == 200 and calls == [1]
    ai = r.json()
    assert [i['status'] for i in ai['items']] == ['done', 'missing'] and ai['source'] == 'ai' and ai['model'] == 'm'
    mine = next(m for m in s.get('/api/portal/materials').json() if m['id'] == task)['defter']
    assert mine['comment'] == 'Отлично' and {i['status'] for i in mine['items']} == {'done', 'missing'}
    assert 'wrong' not in json.dumps(mine) and 'summary' not in json.dumps(mine)
    # müəllim siyahısında ai_check var
    row = next(x for x in c.get(f'/api/materials/{ta}/{task}/submissions').json()['rows'] if x['student_id'] == st[0]['id'])
    assert row['submission']['ai_check']['summary_az'] == 'Yaxşı'


def test_other_teacher_404_and_bad_json(env, monkeypatch):
    world, c, ta, st, task = env
    fake(monkeypatch, out='not json at all')
    submit(st[0], task)
    sid = sid_of(c, ta, task, st[0])
    assert c.post(f'/api/materials/{task}/submissions/{sid}/check', json={'subtopics': SUBS}).status_code == 502
    yad = world[0]('yad')
    assert yad.post(f'/api/materials/{task}/submissions/{sid}/check', json={'subtopics': SUBS}).status_code == 404
    assert yad.get(f'/api/materials/{task}/check.csv').status_code == 404
    assert yad.get(f'/api/materials/{task}/subtopics').status_code == 404
    assert yad.put(f'/api/materials/{task}/mark', json={'student_id': st[0]['id'], 'subtopic': 'A', 'status': 'done'}).status_code == 404
    assert c.post(f'/api/materials/{task}/submissions/{sid}/check', json={'subtopics': []}).status_code == 422


def test_text_only_submission_cannot_be_checked(env, monkeypatch):
    world, c, ta, st, task = env
    fake(monkeypatch)
    student(st[0]).post(f'/api/portal/materials/{task}/submit', data={'text': 'x=3'})
    sid = sid_of(c, ta, task, st[0])
    assert c.post(f'/api/materials/{task}/submissions/{sid}/check', json={'subtopics': SUBS}).status_code == 400


def test_check_all_continues_on_error(env, monkeypatch):
    world, c, ta, st, task = env
    fake(monkeypatch, fail={1})
    submit(st[0], task)
    submit(st[1], task)
    assert c.post(f'/api/materials/{task}/check-all', json={'subtopics': SUBS}).json() == {'started': 2}
    state = c.get(f'/api/materials/{task}/check-all').json()
    assert state['ready'] == 1 and state['failed'] == 1 and state['done'] == 1 and state['running'] is False
    assert c.post(f'/api/materials/{task}/check-all', json={'subtopics': SUBS}).json() == {'started': 1}   # yalnız yoxlanmamış


def test_manual_marks_all_class_without_submission(env, monkeypatch):
    world, c, ta, st, task = env
    a, b = st
    def mk(stu, sub, status, note=None):
        return c.put(f'/api/materials/{task}/mark', json={'student_id': stu['id'], 'subtopic': sub, 'status': status, 'note': note})
    assert mk(a, 'Tənliklər', 'done').status_code == 200            # cavab göndərməyib – yenə də olur
    assert mk(b, 'Tənliklər', 'partial', 'nömrə 3, 5').status_code == 200
    assert mk(b, 'Bərabərsizliklər', 'missing').status_code == 200
    assert mk(b, 'Bərabərsizliklər', None).status_code == 200       # boşaltma
    assert c.put(f'/api/materials/{task}/mark', json={'student_id': a['id'], 'subtopic': 'T', 'status': 'ok'}).status_code == 422
    assert c.put(f'/api/materials/{task}/mark', json={'student_id': 99999, 'subtopic': 'T', 'status': 'done'}).status_code == 404
    t = c.get(f'/api/materials/{task}/defter', params={'extra': 'Yeni alt mövzu'}).json()
    assert t['subtopics'] == ['Tənliklər', 'Bərabərsizliklər', 'Yeni alt mövzu']
    assert t['percent']['Tənliklər'] == 50 and t['percent']['Bərabərsizliklər'] == 0
    rb = next(r for r in t['rows'] if r['student_id'] == b['id'])
    assert rb['items']['Tənliklər']['note'] == 'nömrə 3, 5' and rb['items']['Tənliklər']['source'] == 'manual'
    # placeholder «təhvil verib» sayılmır
    lst = c.get(f'/api/materials/{ta}').json()
    assert next(m for m in lst if m['id'] == task)['submitted'] == 0
    assert all(r['submission'] is None for r in c.get(f'/api/materials/{ta}/{task}/submissions').json()['rows'])
    # şagird yalnız öz statusunu görür
    sa = student(a)
    mat = next(m for m in sa.get('/api/portal/materials').json() if m['id'] == task)
    assert mat['submission'] is None and mat['defter']['items'] == [{'subtopic': 'Tənliklər', 'status': 'done'}]
    # sonra cavab göndərə bilər
    assert sa.post(f'/api/portal/materials/{task}/submit', data={'text': 'x'}).status_code == 200
    # CSV
    csv = c.get(f'/api/materials/{task}/check.csv')
    assert csv.status_code == 200 and 'şagird;alt_mövzu;status' in csv.text and 'qismən' in csv.text and 'SİNİF;Tənliklər;50%' in csv.text


def test_manual_overrides_ai_and_survives_recheck(env, monkeypatch):
    world, c, ta, st, task = env
    fake(monkeypatch)
    submit(st[0], task)
    sid = sid_of(c, ta, task, st[0])
    c.post(f'/api/materials/{task}/submissions/{sid}/check', json={'subtopics': SUBS})
    assert c.put(f'/api/materials/{task}/mark', json={'student_id': st[0]['id'], 'subtopic': 'Tənliklər', 'status': 'missing'}).status_code == 200
    ai = c.post(f'/api/materials/{task}/submissions/{sid}/check', json={'subtopics': SUBS}).json()   # təkrar AI
    it = next(i for i in ai['items'] if i['subtopic'] == 'Tənliklər')
    assert it['status'] == 'missing' and it['source'] == 'manual'
    assert next(i for i in ai['items'] if i['subtopic'] == 'Bərabərsizliklər')['source'] == 'ai'


def test_subtopics_suggest(env):
    world, c, ta, st, task = env
    r = c.get(f'/api/materials/{task}/subtopics')
    assert r.status_code == 200 and r.json()['subtopics'] == [] and r.json()['saved'] == []
