"""Çat: kontaktlar (qruplar, alt yazı), sinif rəhbəri ↔ şagird, admin ↔ hər kəs, boş şəxsi yazışma siyahıda yoxdur."""
from .test_api_portal import clock, setup, student_client  # noqa: F401


def test_homeroom_and_admin_contacts(world, clock):
    as_, _ = world
    admin, ta, cid, st, ids = setup(world)
    ilqar = as_('ilqar')
    ilqar_id = ilqar.get('/api/auth/me').json()['id']
    s0 = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    s0_uid = s0.get('/api/auth/me').json()['id']
    # İlqar bu sinifdə dərs demir və rəhbər deyil – şagirdə yaza bilməz
    assert ilqar.post('/api/chat/dm', json={'user_id': s0_uid}).status_code == 403
    admin.put(f'/api/classes/{cid}/homeroom', json={'teacher_id': ilqar_id})
    assert ilqar.post('/api/chat/dm', json={'user_id': s0_uid}).status_code == 200      # rəhbər – yaza bilər
    assert any(r['kind'] == 'class' for r in ilqar.get('/api/chat/rooms').json())          # sinif söhbətinə daxildir
    c = {x['full_name']: x for x in s0.get('/api/chat/contacts').json()}
    assert c['Nəcəfov İlqar']['group'] == 'Müəllimlər' and 'sinif rəhbəri' in c['Nəcəfov İlqar']['sub']
    assert c['Həsənov Fərid']['sub'].startswith('Riyaziyyat')
    assert c[st[1]['full_name']]['group'] == 'X e'                                           # sinif yoldaşı
    # admin məktəbdə hər kəsə yaza bilər; boş yazışma siyahıda görünmür, mesajdan sonra görünür
    r = admin.post('/api/chat/dm', json={'user_id': ilqar_id}).json()
    assert not any(x['id'] == r['id'] for x in admin.get('/api/chat/rooms').json())
    admin.post(f'/api/chat/rooms/{r["id"]}/messages', data={'text': 'Salam'})
    rooms = admin.get('/api/chat/rooms').json()
    dm = next(x for x in rooms if x['id'] == r['id'])
    assert dm['last']['mine'] and dm['last']['text'] == 'Salam' and rooms[-1]['kind'] == 'dm'
    assert next(x for x in admin.get('/api/chat/contacts').json() if x['id'] == ilqar_id)['room_id'] == r['id']
