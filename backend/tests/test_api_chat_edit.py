"""Çat: öz mesajını düzəltmək (24 saat), bildirilmiş mesaj dəyişmir, dəyişikliklər başqasına /changes ilə çatır; stiker – adi mətn."""
import datetime as dt

from app.models import ChatMessage

from .test_api_portal import setup, student_client


def test_edit_message_and_changes(world):
    as_, S = world
    admin, ta, cid, st, ids = setup(world)
    a = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    b = student_client(st[1]['portal_code'], st[1]['initial_pin'])
    room = next(r for r in a.get('/api/chat/rooms').json() if r['kind'] == 'class')['id']
    since = b.get(f'/api/chat/rooms/{room}/changes', params={'since': dt.datetime.now(dt.timezone.utc).isoformat()}).json()['now']

    m = a.post(f'/api/chat/rooms/{room}/messages', data={'text': 'Salm'}).json()
    e = a.patch(f'/api/chat/messages/{m["id"]}', json={'text': 'Salam 😊'}).json()
    assert e['text'] == 'Salam 😊' and e['edited']
    # başqası düzəldə bilməz, boş mətn olmaz
    assert b.patch(f'/api/chat/messages/{m["id"]}', json={'text': 'x'}).status_code == 404
    assert a.patch(f'/api/chat/messages/{m["id"]}', json={'text': '   '}).status_code in (400, 422)
    # digər şagird dəyişikliyi görür
    ch = b.get(f'/api/chat/rooms/{room}/changes', params={'since': since}).json()
    assert [x['text'] for x in ch['items']] == ['Salam 😊']
    # oxuyanlar: b otağı oxuyanda a-nın mesajı «oxundu»
    b.post(f'/api/chat/rooms/{room}/read')
    rd = {x['name']: x['last_read_id'] for x in a.get(f'/api/chat/rooms/{room}/reads').json()}
    assert rd[st[1]['full_name']] >= m['id']
    # stiker – tək smayl mətn kimi
    s = b.post(f'/api/chat/rooms/{room}/messages', data={'text': '🌟'}).json()
    assert s['text'] == '🌟' and not s['edited']
    # bildirilmiş mesaj düzəldilmir
    assert a.post(f'/api/chat/messages/{s["id"]}/report', json={}).status_code == 200
    assert b.patch(f'/api/chat/messages/{s["id"]}', json={'text': '👍'}).status_code == 409
    # 24 saatdan köhnə mesaj düzəldilmir
    with S() as db:
        db.get(ChatMessage, m['id']).created_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=25)
        db.commit()
    assert a.patch(f'/api/chat/messages/{m["id"]}', json={'text': 'gec'}).status_code == 409
    # profil şəkli: yüklə → mesajda və baxışda görünür, sil
    png = b'\x89PNG\r\n\x1a\n' + b'0' * 100
    assert a.post('/api/chat/avatar', files={'file': ('a.gif', b'GIF89a', 'image/gif')}).status_code == 400
    assert a.post('/api/chat/avatar', files={'file': ('a.png', b'0' * (301 * 1024), 'image/png')}).status_code == 400
    url = a.post('/api/chat/avatar', files={'file': ('a.png', png, 'image/png')}).json()['avatar']
    assert url and b.get(url).content == png
    assert b.get(f'/api/chat/rooms/{room}/messages').json()[0]['avatar'] == url
    assert a.get('/api/chat/profile').json()['avatar'] == url
    a.delete('/api/chat/avatar')
    assert b.get(url).status_code == 404
    # silinmiş mesaj da /changes ilə çatır
    a.delete(f'/api/chat/messages/{m["id"]}')
    ch2 = b.get(f'/api/chat/rooms/{room}/changes', params={'since': ch['now']}).json()
    assert any(x['id'] == m['id'] and x['deleted'] and x['text'] is None for x in ch2['items'])
