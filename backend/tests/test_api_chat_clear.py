"""Çat: söhbəti silmək – yalnız özündə; həmsöhbətdə qalır, yeni mesajla şəxsi yazışma yenidən görünür."""
from .test_api_portal import clock, setup, student_client  # noqa: F401


def test_clear_room_only_for_me(world, clock):
    admin, ta, cid, st, ids = setup(world)
    s0 = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    s1 = student_client(st[1]['portal_code'], st[1]['initial_pin'])
    s0_uid = s0.get('/api/auth/me').json()['id']
    # müəllim ↔ şagird şəxsi yazışma
    r = admin.post('/api/chat/dm', json={'user_id': s0_uid}).json()['id']
    admin.post(f'/api/chat/rooms/{r}/messages', data={'text': 'Salam'})
    s0.post(f'/api/chat/rooms/{r}/messages', data={'text': 'Salam, müəllim'})
    assert s0.delete(f'/api/chat/rooms/{r}').status_code == 200
    assert not any(x['id'] == r for x in s0.get('/api/chat/rooms').json())        # şagirddə siyahıdan çıxdı
    assert s0.get(f'/api/chat/rooms/{r}/messages').json() == []
    assert len(admin.get(f'/api/chat/rooms/{r}/messages').json()) == 2             # müəllimdə qalır
    # yeni mesaj – yalnız o görünür, oxunmamış 1
    admin.post(f'/api/chat/rooms/{r}/messages', data={'text': 'Sabah test var'})
    dm = next(x for x in s0.get('/api/chat/rooms').json() if x['id'] == r)
    assert dm['unread'] == 1 and dm['last']['text'] == 'Sabah test var'
    assert [m['text'] for m in s0.get(f'/api/chat/rooms/{r}/messages').json()] == ['Sabah test var']
    # müəllim də öz tərəfində silə bilər
    assert admin.delete(f'/api/chat/rooms/{r}').status_code == 200
    assert admin.get(f'/api/chat/rooms/{r}/messages').json() == []
    # sinif söhbəti: tarixçə özündə təmizlənir, otaq siyahıda qalır; başqası silə bilməz (giriş yoxdursa 404)
    room = next(x for x in s0.get('/api/chat/rooms').json() if x['kind'] == 'class')['id']
    s1.post(f'/api/chat/rooms/{room}/messages', data={'text': 'Ev tapşırığı nədir?'})
    s0.delete(f'/api/chat/rooms/{room}')
    assert any(x['id'] == room and x['last'] is None for x in s0.get('/api/chat/rooms').json())
    assert len(s1.get(f'/api/chat/rooms/{room}/messages').json()) == 1
    assert s1.delete(f'/api/chat/rooms/{r}').status_code == 404
