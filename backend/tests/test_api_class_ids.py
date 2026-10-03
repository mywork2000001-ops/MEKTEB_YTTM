"""Şagird əlavə etmə və sinif ID-si: bölünmə qrupuna birbaşa, kod toqquşması, arxivdəki təkrar, ID redaktəsi."""
from app.models import Role, User
from app.security import hash_password


def test_add_student_to_split_group_and_class_id(world):
    as_, S = world
    admin = as_('admin')
    xb = admin.post('/api/classes', json={'name': 'X b'}).json()
    g = admin.post('/api/classes', json={'name': 'X b (riyaziyyat qrupu)', 'kind': 'qrup', 'parent_id': xb['id']}).json()
    xc = admin.post('/api/classes', json={'name': 'X c'}).json()['id']
    assert xb['code'] == 'XB'

    # bölünmə qrupundan: şagird ana sinfə yazılır və dərhal qrupa üzv olur
    s = admin.post('/api/students', json={'full_name': 'Məmmədov Rauf Vüqar oğlu', 'class_id': xb['id'], 'group_id': g['id']}).json()
    assert s['portal_code'] == 'XB-001' and admin.get(f'/api/classes/{g["id"]}/members').json() == [s['id']]
    assert admin.post('/api/students', json={'full_name': 'Səhv Qrup Şagirdi', 'class_id': xc, 'group_id': g['id']}).status_code == 400
    assert admin.post('/api/students', json={'full_name': 'Gələcək Doğum Tarixi', 'class_id': xb['id'],
                                             'birth_date': '2099-01-01'}).status_code == 400

    # kod istifadəçi loginində tutulubsa – növbəti boş nömrə
    with S() as db:
        db.add(User(role=Role.teacher, login='XB-002', password_hash=hash_password('x-parol-123'), full_name='Toqquşma'))
        db.commit()
    assert admin.post('/api/students', json={'full_name': 'İkinci Şagird oğlu', 'class_id': xb['id']}).json()['portal_code'] == 'XB-003'

    # arxivdəki təkrar: 409 + archived=True (geri qaytarmaq üçün)
    admin.post(f'/api/students/{s["id"]}/archive', json={'confirm': s['full_name']})
    r = admin.post('/api/students', json={'full_name': 'Məmmədov  Rauf Vüqar oğlu', 'class_id': xb['id']})
    assert r.status_code == 409 and r.json()['detail']['archived'] is True and r.json()['detail']['student_id'] == s['id']

    # sinif ID-si: redaktə, unikal; yeni şagirdlər yeni ID ilə
    assert admin.patch(f'/api/classes/{xb["id"]}', json={'code': 'xc'}).status_code == 409
    assert admin.patch(f'/api/classes/{xb["id"]}', json={'code': '10b'}).json()['code'] == '10B'
    assert admin.post('/api/students', json={'full_name': 'Üçüncü Şagird qızı', 'class_id': xb['id']}).json()['portal_code'] == '10B-001'
