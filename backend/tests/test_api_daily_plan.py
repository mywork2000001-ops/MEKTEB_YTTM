"""Test: gündəlik plan (ARTİ) – müəllimin API açarı, perspektiv plandan kontekst, hazırlama, redaktə, Word."""
import datetime as dt

from app.models import PlanLesson, TeachingAssignment


def _setup(world):
    as_, S = world
    admin = as_('admin')
    cid = admin.post('/api/classes', json={'name': 'X e'}).json()['id']
    admin.post(f'/api/classes/{cid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 2, 'slots': {'1': [1, 5]}})
    with S() as db:
        ta = db.query(TeachingAssignment).filter_by(class_id=cid).one()
        for i in range(6):
            db.add(PlanLesson(assignment_id=ta.id, seq=i + 1, semester=1, section='II BÖLMƏ – ÇOXLUQLAR',
                              assessment_type='KSQ' if i == 5 else 'formativ', exam_no=1 if i == 5 else None,
                              topic=f'Mövzu {i + 1}', standards=['1.1.4'], tt_pages='TT I, s.129–131',
                              resources='TT I, s.129–131; S 1–20; E 21–36\nQT VI; D 6, 10',
                              tasks=[{'kind': 'sinif', 'label': '', 'start': 1, 'end': 20},
                                     {'kind': 'ev', 'label': '', 'start': 21, 'end': 36}],
                              date=dt.date(2026, 9, 15)))
        db.commit()
        return admin, ta.id


FAKE = {
    'standartlar': [{'kod': '1.1.4', 'metn': ''}, {'kod': '9.9.9', 'metn': 'uydurma'}],
    'telim_neticeleri': ['Şagird çoxluqların birləşməsini tapır'],
    'merheleler': [{'ad': 'Motivasiya', 'vaxt': 5, 'muellim': 'sual verir', 'sagird': 'cavab verir',
                    'tapsiriqlar': [{'metn': 'A={1,2}, B={2,3}. A∪B=?', 'cavab': '{1,2,3}'}]},
                   {'ad': 'Tədqiqat', 'vaxt': 40, 'muellim': '…', 'sagird': '…', 'tapsiriqlar': ['S 1–20']}],
    'qiymetlendirme': {'meyarlar': ['birləşməni tapır'], 'rubrika': [{'meyar': 'birləşmə', 'I': 'a', 'II': 'b', 'III': 'c', 'IV': 'd'}]},
    'ev_tapsirigi': 'Test toplusundan tapşırıqlar',
}


def test_ai_settings_and_daily_plan(world, monkeypatch):
    admin, ta = _setup(world)
    # açarsız – aydın xəta
    r = admin.post(f'/api/daily-plans/{ta}/generate', json={'date': '2026-09-15', 'period': 1})
    assert r.status_code == 400 and 'Süni intellekt' in r.json()['detail']
    # açar saxlanılır, geri yalnız maska qaytarılır
    assert admin.put('/api/ai/settings', json={'provider': 'gemini', 'model': 'gemini-2.5-flash'}).status_code == 400
    s = admin.put('/api/ai/settings', json={'provider': 'gemini', 'model': 'gemini-2.5-flash', 'api_key': 'AIzaTEST-1234567890abcd'}).json()
    assert s['has_key'] and s['key_mask'] == '••••abcd' and 'AIza' not in str(s)
    # model dəyişir, açar qalır
    assert admin.put('/api/ai/settings', json={'provider': 'gemini', 'model': 'gemini-2.5-pro'}).json()['has_key']
    assert admin.put('/api/ai/settings', json={'provider': 'custom', 'model': 'x-model', 'api_key': 'k' * 20,
                                                 'base_url': 'http://127.0.0.1/v1'}).status_code == 400

    seen = {}

    def fake(cfg, system, user):
        seen.update(cfg=cfg, system=system, user=user)
        return FAKE
    monkeypatch.setattr('app.ai.complete_json', fake)

    # promt perspektiv plandan dəqiq kontekst alır
    pr = admin.post(f'/api/daily-plans/{ta}/prompt', json={'date': '2026-09-22', 'period': 1, 'notes': 'Qrup işi olsun'}).json()
    assert 'MÖVZU: Mövzu 3' in pr['user'] and '1.1.4' in pr['user'] and 'Ev tapşırığı (E): № 21–36' in pr['user']
    assert 'Əvvəlki dərsin mövzusu: Mövzu 2' in pr['user'] and 'KSQ-1 – 3 dərs sonra' in pr['user']
    assert 'Qrup işi olsun' in pr['user'] and 'ARTİ' in pr['system'] and '45 dəqiqə' in pr['system']

    # yuva yoxdur
    assert admin.post(f'/api/daily-plans/{ta}/generate', json={'date': '2026-09-16', 'period': 1}).status_code == 404

    p = admin.post(f'/api/daily-plans/{ta}/generate', json={'date': '2026-09-22', 'period': 1}).json()
    assert seen['cfg']['api_key'] == 'AIzaTEST-1234567890abcd' and seen['cfg']['model'] == 'gemini-2.5-pro'
    c = p['content']
    assert p['topic'] == 'Mövzu 3' and [x['kod'] for x in c['standartlar']] == ['1.1.4']      # uydurma kod çıxarıldı
    assert c['merheleler'][1]['tapsiriqlar'] == [{'metn': 'S 1–20', 'cavab': ''}]
    assert '21' in c['ev_tapsirigi'] and '36' in c['ev_tapsirigi']                          # plandakı ev tapşırığı qorunur
    assert any('9.9.9' in w for w in p['warnings'])

    # həftə görünüşü – hazır plan görünür
    w = admin.get(f'/api/daily-plans/{ta}', params={'view': 'week', 'date': '2026-09-22'}).json()
    assert [i['lesson']['seq'] for i in w['items']] == [3, 4] and w['items'][0]['plan']['id'] == p['id'] and w['ai']['configured']

    # hazır plan silinmədən yenisi hazırlanmır; eyni gün başqa saat – ayrıca plan
    assert admin.post(f'/api/daily-plans/{ta}/generate', json={'date': '2026-09-22', 'period': 1}).status_code == 409
    p5 = admin.post(f'/api/daily-plans/{ta}/generate', json={'date': '2026-09-22', 'period': 5}).json()
    assert p5['id'] != p['id'] and p5['topic'] == 'Mövzu 4'

    # redaktə: vaxt cəmi yoxlanır
    c['merheleler'][1]['vaxt'] = 30
    e = admin.put(f'/api/daily-plans/{ta}/item/{p["id"]}', json={'content': c}).json()
    assert e['edited'] and e['warnings'] and e['meta']['topic'] == 'Mövzu 3'

    # Word – hazır plan + şablon (hazır olmayan dərs) bir faylda
    d = admin.get('/api/daily-plans-docx', params={'slots': f'{ta}:2026-09-22:1,{ta}:2026-09-29:1'})
    assert d.status_code == 200 and d.content[:2] == b'PK'
    # sistemdə baxış: hazır olmayan dərs – perspektiv plandan şablon
    b = admin.get(f'/api/daily-plans/{ta}/preview', params={'date': '2026-09-29', 'period': 1}).json()
    assert b['blank'] and b['topic'] == 'Mövzu 5' and b['content']['standartlar'][0]['kod'] == '1.1.4'
    assert '21' in b['content']['ev_tapsirigi'] and b['meta']['teacher'] == 'Həsənov Fərid'
    assert admin.get(f'/api/daily-plans/{ta}/preview', params={'date': '2026-09-22', 'period': 1}).json()['id'] == p['id']
    assert 'tam orta' in b['meta']['school']
    # əl ilə doldurma (açarsız da): şablon plana çevrilir, başlıq daxil hər sətir redaktə olunur
    mp = admin.post(f'/api/daily-plans/{ta}/manual', json={'date': '2026-09-29', 'period': 1}).json()
    assert mp['id'] and mp['edited'] and not mp['blank']
    assert admin.post(f'/api/daily-plans/{ta}/manual', json={'date': '2026-09-29', 'period': 1}).status_code == 409
    mc = {**mp['content'], 'basliq': {'school': 'Tərtər şəhər 6 nömrəli tam orta ümumtəhsil məktəbi', 'topic': 'Yeni mövzu adı',
                                      'tarix': '29.09.2026'}}
    e2 = admin.put(f'/api/daily-plans/{ta}/item/{mp["id"]}', json={'content': mc}).json()
    assert e2['topic'] == 'Yeni mövzu adı' and e2['content']['basliq']['school'].startswith('Tərtər şəhər 6')
    # başlıqda məktəbin adı – bütün planlar üçün
    assert admin.put('/api/daily-plans-header', json={'school': 'Tərtər şəhər 6 nömrəli tam orta ümumtəhsil məktəbi'}).status_code == 200
    assert admin.get(f'/api/daily-plans/{ta}/preview', params={'date': '2026-09-22', 'period': 1}).json()['meta']['school'].startswith('Tərtər şəhər 6')
    assert admin.get('/api/daily-plans-docx', params={'slots': f'{ta}:2026-09-29:1'}).status_code == 200

    # başqa müəllim görə bilmir
    as_, _ = world
    assert as_('ilqar').get(f'/api/daily-plans/{ta}/item/{p["id"]}').status_code == 404
    assert admin.delete(f'/api/daily-plans/{ta}/item/{p["id"]}').status_code == 200
    assert admin.post(f'/api/daily-plans/{ta}/generate', json={'date': '2026-09-22', 'period': 1}).status_code == 200   # silindikdən sonra
    assert admin.delete('/api/ai/settings').json()['has_key'] is False


def test_normalize_and_parse():
    from app.ai import parse_json
    assert parse_json('```json\n{"a": 1}\n```') == {'a': 1}
    assert parse_json('Budur plan: {"a": {"b": 2}} uğurlar') == {'a': {'b': 2}}


def test_day_view_all_classes(world, monkeypatch):
    admin, ta = _setup(world)
    # ikinci sinif – eyni gün (Ç.a.) 3-cü saat
    as_, S = world
    cid = admin.post('/api/classes', json={'name': 'X c'}).json()['id']
    admin.post(f'/api/classes/{cid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 1, 'slots': {'1': [3]}})
    with S() as db:
        ta2 = db.query(TeachingAssignment).filter_by(class_id=cid).one().id
        db.add(PlanLesson(assignment_id=ta2, seq=1, semester=1, assessment_type='formativ', topic='Başqa mövzu',
                          date=dt.date(2026, 9, 15)))
        db.commit()
    d = admin.get('/api/daily-plans-list', params={'date': '2026-09-15'}).json()
    assert [(i['period'], i['class_name']) for i in d['items']] == [(1, 'X e'), (3, 'X c'), (5, 'X e')]
    assert d['weekday'] == 'Çərşənbə axşamı' and not d['ai']['configured']
    assert admin.get('/api/daily-plans-list', params={'date': '2026-09-16'}).json()['items'] == []
    # dərs həftəsi – bütün siniflər; bir sinif
    w = admin.get('/api/daily-plans-list', params={'date': '2026-09-24', 'view': 'week'}).json()
    assert w['from'] == '2026-09-21' and len(w['items']) == 3
    assert len(admin.get('/api/daily-plans-list', params={'date': '2026-09-24', 'view': 'week', 'ta': str(ta2)}).json()['items']) == 1

    admin.put('/api/ai/settings', json={'provider': 'openrouter', 'model': 'google/gemini-2.5-flash', 'api_key': 'sk-or-TEST-123456789'})
    monkeypatch.setattr('app.ai.complete_json', lambda cfg, s, u: FAKE)
    for i in d['items']:
        assert admin.post(f"/api/daily-plans/{i['ta_id']}/generate", json={'date': i['date'], 'period': i['period']}).status_code == 200
    d = admin.get('/api/daily-plans-list', params={'date': '2026-09-15'}).json()
    assert all(i['plan'] for i in d['items'])
    # başqa müəllimin günü boşdur, başqasının dərsinə Word/baxış yoxdur
    assert as_('ilqar').get('/api/daily-plans-list', params={'date': '2026-09-15'}).json()['items'] == []
    assert as_('ilqar').get('/api/daily-plans-docx', params={'slots': f'{ta}:2026-09-15:1'}).status_code == 404
