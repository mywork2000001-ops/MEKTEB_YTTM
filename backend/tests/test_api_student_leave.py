"""Şagird məktəbdən gedib: passiv (səbəb, tarix, giriş bağlanır, qiymətlər qalır) → geri qaytar / həmişəlik sil.
Çatda mesajı olan şagird silinəndə hesabı anonimləşir (başqalarının yazışması pozulmur)."""
from app.models import User

from .test_api_portal import setup, student_client


def test_leave_restore_delete(world):
    as_, S = world
    admin, ta, cid, st, ids = setup(world)
    s0 = st[0]
    a = student_client(s0['portal_code'], s0['initial_pin'])
    room = next(r for r in a.get('/api/chat/rooms').json() if r['kind'] == 'class')['id']
    a.post(f'/api/chat/rooms/{room}/messages', data={'text': 'Salam'})

    r = admin.post(f'/api/students/{s0["id"]}/archive', json={'confirm': s0['full_name'], 'reason': 'Başqa məktəbə köçdü: Bərdə 2',
                                                            'left_on': '2026-09-30'})
    assert r.status_code == 200
    assert s0['id'] not in [x['id'] for x in admin.get('/api/students', params={'class_id': cid}).json()]
    arch = next(x for x in admin.get('/api/students', params={'archived': True}).json() if x['id'] == s0['id'])
    assert arch['left_reason'].startswith('Başqa məktəbə') and arch['left_on'] == '2026-09-30'
    # giriş bağlanıb
    assert a.get('/api/chat/rooms').status_code in (401, 403)
    # geri qaytar – səbəb təmizlənir
    admin.post(f'/api/students/{s0["id"]}/restore')
    back = next(x for x in admin.get('/api/students', params={'class_id': cid}).json() if x['id'] == s0['id'])
    assert back['left_reason'] is None
    # yenidən passiv → həmişəlik sil; mesajı olan hesab anonimləşir
    admin.post(f'/api/students/{s0["id"]}/archive', json={'confirm': s0['full_name']})
    assert admin.request('DELETE', f'/api/students/{s0["id"]}', json={'confirm': s0['full_name']}).status_code == 200
    with S() as db:
        u = db.query(User).filter(User.login.like('silinib-%')).one()
        assert u.full_name == 'Silinmiş şagird' and u.archived_at is not None
    b = student_client(st[1]['portal_code'], st[1]['initial_pin'])
    msgs = b.get(f'/api/chat/rooms/{room}/messages').json()
    assert msgs[0]['sender'] == 'Silinmiş şagird' and msgs[0]['text'] == 'Salam'
    # mesajı olmayan şagird – hesabı tam silinir
    s2 = st[2]
    admin.post(f'/api/students/{s2["id"]}/archive', json={'confirm': s2['full_name']})
    assert admin.request('DELETE', f'/api/students/{s2["id"]}', json={'confirm': s2['full_name']}).status_code == 200
    with S() as db:
        assert db.query(User).filter(User.login == s2['portal_code']).count() == 0
