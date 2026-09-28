"""Onlayn tapşırıqlar (vaxt, avtomatik təhvil, cavabların gizliliyi), şagird portalı, çat məxfiliyi."""
import datetime as dt

import pytest
from fastapi.testclient import TestClient

from app.domain.answers import check_open
from app.main import app
from app.models import BankFile, BankQuestion, BankSource, PlanLesson, TeachingAssignment

UTC = dt.timezone.utc


class Clock:
    def __init__(self):
        self.t = dt.datetime(2026, 9, 29, 14, 0, tzinfo=UTC)

    def __call__(self):
        return self.t


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    for mod in ('app.api.tasks', 'app.api.portal', 'app.api.chat'):
        monkeypatch.setattr(f'{mod}.now', c)
    return c


def student_client(code, pin):
    c = TestClient(app)
    c.__enter__()
    assert c.post('/api/auth/login', json={'login': code, 'password': pin}).status_code == 200
    return c


def setup(world):
    as_, S = world
    admin = as_('admin')
    cid = admin.post('/api/classes', json={'name': 'X e'}).json()['id']
    admin.post(f'/api/classes/{cid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 2,
                                                 'slots': {'1': [1, 5]}})
    st = [admin.post('/api/students', json={'full_name': f'Şagird Test{i} qızı', 'class_id': cid}).json()
          for i in range(3)]
    with S() as db:
        ta = db.query(TeachingAssignment).filter_by(class_id=cid).one()
        # Ç.a. 1, 5-ci saat: 15.09 (2), 22.09 (2), 29.09 1-ci saat = 5-ci dərs
        for i in range(8):
            db.add(PlanLesson(assignment_id=ta.id, seq=i + 1, semester=1, assessment_type='formativ',
                              topic='Kvadrat tənliklər' if i == 4 else f'Mövzu {i + 1}', date=dt.date(2026, 9, 15)))
        db.add(BankSource(key='p012', label='P012'))
        db.flush()
        f = BankFile(source_key='p012', lesson='usi-1.html', label='ÜSİ-1', url='http://x/usi-1.html')
        db.add(f)
        db.flush()
        qs = [BankQuestion(file_id=f.id, n=1, kind='mcq', text={'az': '2+2=?'}, options=[{'az': '3'}, {'az': '4'}],
                           correct=1, content_hash='a', explanation={'az': '2+2=4'}),
              BankQuestion(file_id=f.id, n=2, kind='open', text={'az': 'x²=9, x>0'}, answer='3', content_hash='b'),
              BankQuestion(file_id=f.id, n=3, kind='mcq', text={'az': '5·2=?'}, options=[{'az': '10'}, {'az': '7'}],
                           correct=0, content_hash='c')]
        db.add_all(qs)
        db.commit()
        return admin, ta.id, cid, st, [q.id for q in qs]


def mk_task(admin, ta, ids, **kw):
    body = {'title': 'Test 1', 'opens_at': '2026-09-29T15:00:00Z', 'closes_at': '2026-09-29T16:00:00Z',
            'duration_min': 40, 'bank_ids': ids, 'shuffle': True, **kw}
    return admin.post(f'/api/tasks/{ta}', json=body)


def test_open_answer_normalization():
    assert check_open(' 2,5 ', '2.5') and check_open('X=3', 'x=3|3')
    assert check_open('2: d, 1: b,a', '1:a,b, 2:d')                # uyğunluq – sıra fərq etmir
    assert not check_open('', '3') and not check_open('4', '3')


def test_timed_task_flow(world, clock):
    admin, ta, cid, st, ids = setup(world)
    assert mk_task(admin, ta, ids, duration_min=90).status_code == 422       # müddət aralıqdan uzun
    t = mk_task(admin, ta, ids).json()
    s = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    lst = s.get('/api/portal/tasks').json()
    assert lst[0]['status'] == 'gözlənilir'
    assert s.post(f'/api/portal/tasks/{t["id"]}/start').status_code == 409  # hələ açılmayıb
    clock.t = dt.datetime(2026, 9, 29, 15, 40, tzinfo=UTC)
    r = s.post(f'/api/portal/tasks/{t["id"]}/start').json()
    assert r['deadline'].startswith('2026-09-29T16:00')                       # bağlanma vaxtı ilə məhdud (40 dəq yox)
    assert all('correct' not in q and 'answer' not in q for q in r['questions'])   # cavablar gizlidir
    by_text = {q['text']['az']: q['index'] for q in r['questions']}
    s.put(f'/api/portal/tasks/{t["id"]}/answers', json={'answers': {str(by_text['2+2=?']): 1,
                                                                    str(by_text['x²=9, x>0']): ' 3 '}})
    assert s.get(f'/api/portal/tasks/{t["id"]}/review').status_code == 403
    clock.t = dt.datetime(2026, 9, 29, 16, 0, 1, tzinfo=UTC)
    rr = s.put(f'/api/portal/tasks/{t["id"]}/answers', json={'answers': {str(by_text['5·2=?']): 0}})
    assert rr.status_code == 409                                              # vaxt bitdi – avtomatik təhvil
    res = s.get('/api/portal/tasks').json()[0]
    assert res['status'] == 'təhvil verilib' and res['result'] == {'correct': 2, 'total': 3, 'grade': 4}
    rev = s.get(f'/api/portal/tasks/{t["id"]}/review').json()               # bağlandıqdan sonra açılır
    assert sum(q['ok'] for q in rev['questions']) == 2
    teacher = admin.get(f'/api/tasks/{ta}/{t["id"]}').json()
    rows = {x['student_id']: x for x in teacher['rows']}
    assert rows[st[0]['id']]['auto_submitted'] and rows[st[1]['id']]['status'] == 'başlamayıb'
    mist = s.get('/api/portal/results').json()['mistakes']
    assert [m['text']['az'] for m in mist] == ['5·2=?']


def test_student_sees_only_own_data(world, clock):
    as_, _ = world
    admin, ta, cid, st, ids = setup(world)
    s1 = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    for path in ('/api/classes', '/api/students', f'/api/journal/{ta}/day', f'/api/tasks/{ta}', '/api/bank/status'):
        assert s1.get(path).status_code in (403, 404), path
    admin.put(f'/api/journal/{ta}/entry', json={
        'date': '2026-09-29', 'period': 1, 'homework': 'S 1–5',
        'attendance': {st[0]['id']: 'var', st[1]['id']: 'yox'},
        'marks': [{'student_id': st[0]['id'], 'kind': 'şifahi', 'grade': 5}]})
    day = s1.get('/api/portal/day', params={'date': '2026-09-29'}).json()['lessons']
    assert day[0]['topic'] == 'Kvadrat tənliklər' and day[0]['homework'] == 'S 1–5'
    assert day[0]['marks'] == [{'kind': 'şifahi', 'grade': 5, 'test_correct': None, 'test_total': None}]
    assert day[0]['teacher'] == 'Həsənov Fərid'
    an = s1.get('/api/portal/analytics').json()['subjects'][0]
    assert an['me']['avg_grade'] == 5 and an['class_avg']['attendance_pct'] == 50.0
    assert 'students' not in an                                                # yoldaşların adları yoxdur
    me = s1.get('/api/portal/me').json()
    assert me['class_name'] == 'X e' and me['motivation']
    s1.patch('/api/auth/prefs', json={'language': 'en', 'theme': 'forest'})
    assert s1.get('/api/auth/me').json()['language'] == 'en'


def test_chat_privacy(world, clock):
    as_, _ = world
    admin, ta, cid, st, ids = setup(world)
    ilqar = as_('ilqar')
    a = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    b = student_client(st[1]['portal_code'], st[1]['initial_pin'])
    # sinif otağı: şagird və sinfin müəllimi görür, dərs deməyən müəllim görmür
    room = next(r for r in a.get('/api/chat/rooms').json() if r['kind'] == 'class')
    a.post(f'/api/chat/rooms/{room["id"]}/messages', data={'text': 'Salam, sinif!'})
    assert [m['text'] for m in admin.get(f'/api/chat/rooms/{room["id"]}/messages').json()] == ['Salam, sinif!']
    assert ilqar.get(f'/api/chat/rooms/{room["id"]}/messages').status_code == 404
    # şəxsi yazışma: şagird–şagird; müəllim (admin da) görmür
    b_uid = next(c['id'] for c in a.get('/api/chat/contacts').json() if c['full_name'] == 'Şagird Test1 qızı')
    dm = a.post('/api/chat/dm', json={'user_id': b_uid}).json()
    msg = b.post(f'/api/chat/rooms/{dm["id"]}/messages', data={'text': 'pis söz'}).json()
    assert admin.get(f'/api/chat/rooms/{dm["id"]}/messages').status_code == 404
    assert ilqar.get(f'/api/chat/rooms/{dm["id"]}/messages').status_code == 404
    # «!» – bildirilən mesajı YALNIZ sinfin müəllimi görür
    assert a.post(f'/api/chat/messages/{msg["id"]}/report', json={'reason': 'təhqir'}).status_code == 200
    assert b.post(f'/api/chat/messages/{msg["id"]}/report', json={}).status_code == 400    # öz mesajı
    reps = admin.get('/api/chat/reports').json()
    assert len(reps) == 1 and reps[0]['message']['text'] == 'pis söz' and reps[0]['reporter'] == 'Şagird Test0 qızı'
    assert ilqar.get('/api/chat/reports').json() == []
    # şagird dərs deməyən müəllimə yaza bilməz; müəllimlər öz aralarında yaza bilər
    ilqar_id = next(t['id'] for t in admin.get('/api/teachers').json() if t['login'] == 'ilqar')
    assert a.post('/api/chat/dm', json={'user_id': ilqar_id}).status_code == 403
    assert admin.post('/api/chat/dm', json={'user_id': ilqar_id}).status_code == 200
    staff = [r for r in ilqar.get('/api/chat/rooms').json() if r['kind'] == 'staff']
    assert len(staff) == 1 and staff[0]['title'] == 'Müəllim otağı'
    assert not any(r['kind'] == 'staff' for r in a.get('/api/chat/rooms').json())


def test_chat_files(world, clock, tmp_path, monkeypatch):
    monkeypatch.setattr('app.api.chat.upload_dir', lambda: tmp_path)
    admin, ta, cid, st, ids = setup(world)
    a = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    room = next(r for r in a.get('/api/chat/rooms').json() if r['kind'] == 'class')
    bad = a.post(f'/api/chat/rooms/{room["id"]}/messages', files={'file': ('x.exe', b'MZ', 'application/x-msdownload')})
    assert bad.status_code == 400
    ok = a.post(f'/api/chat/rooms/{room["id"]}/messages', files={'file': ('səs.webm', b'\x1aE\xdf\xa3', 'audio/webm')})
    assert ok.status_code == 200 and ok.json()['file']['type'] == 'audio/webm'
    got = admin.get(ok.json()['file']['url'])
    assert got.status_code == 200 and got.content == b'\x1aE\xdf\xa3'
    assert TestClient(app).get(ok.json()['file']['url']).status_code == 401


def test_chat_upload_limit_streams_and_cleans(tmp_path):
    """Limit keçiləndə 413 və yarımçıq fayl diskdə qalmır (2 GB əvəzinə kiçik limitlə yoxlanılır)."""
    import io as _io
    from fastapi import HTTPException, UploadFile
    from app.api.chat import MAX_BYTES, save_stream
    assert MAX_BYTES == 2 * 1024 ** 3
    dest = tmp_path / 'f'
    assert save_stream(UploadFile(_io.BytesIO(b'x' * 3000)), dest, limit=5000) == 3000 and dest.exists()
    with pytest.raises(HTTPException) as e:
        save_stream(UploadFile(_io.BytesIO(b'x' * 3_000_000)), tmp_path / 'g', limit=2_000_000)
    assert e.value.status_code == 413 and not (tmp_path / 'g').exists()


def test_chat_files_in_database_storage(world, clock, monkeypatch):
    """MK_STORAGE=db: fayl bazada saxlanılır (hostinq yenidən başlayanda silinmir) və axınla qaytarılır."""
    from app.config import settings
    monkeypatch.setattr(settings(), 'storage', 'db')
    admin, ta, cid, st, ids = setup(world)
    a = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    room = next(r for r in a.get('/api/chat/rooms').json() if r['kind'] == 'class')
    blob = bytes(range(256)) * 9000                                  # ~2,3 MB – bir neçə hissə
    ok = a.post(f'/api/chat/rooms/{room["id"]}/messages', files={'file': ('şəkil.png', blob, 'image/png')})
    assert ok.status_code == 200 and ok.json()['file']['size'] == len(blob)
    got = admin.get(ok.json()['file']['url'])
    assert got.status_code == 200 and got.content == blob
    from app.storage import upload_limit
    assert upload_limit() == 50 * 1024 ** 2
