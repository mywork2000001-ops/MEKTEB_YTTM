"""Şagird sorğusu (müəllim haqqında): açıq link, anonimlik (cavabda şagird yoxdur), təkrar göndərmə, k-anonimlik həddi,
əks suallar və NPS, həftəlik sorğu tətbiqdə, məxfilik (başqa müəllim / şagird), CSV, süni intellektin rəyi, silmə."""
import datetime as dt

from fastapi.testclient import TestClient

from app.main import app
from app.models import SurveyResponse

from .test_api_portal import UTC, Clock, setup, student_client


def _clock(monkeypatch):
    c = Clock()
    c.t = dt.datetime(2026, 10, 5, 9, 0, tzinfo=UTC)            # bazar ertəsi, 2026-W41
    monkeypatch.setattr('app.api.surveys.now', c)
    return c


def _answers(sv, likert=4, reverse=2, overall=8, nps=9, text='Dərslər maraqlıdır'):
    out = {}
    for q in sv['questions']:
        k = q['kind']
        if k == 'likert5':
            out[str(q['id'])] = reverse if q['key'] in ('A5', 'D6') else likert
        elif k == 'scale10':
            out[str(q['id'])] = overall if q['key'] == 'overall' else nps
        elif k == 'text' and q['key'] == 'H1':
            out[str(q['id'])] = text
    return out


def _guest():
    c = TestClient(app)
    c.__enter__()
    return c


def test_public_link_anonymous_results(world, monkeypatch):
    as_, S = world
    _clock(monkeypatch)
    admin, ta, cid, st, _ = setup(world)
    sv = admin.post('/api/surveys', json={'title': 'Həsənov Fərid – şagird rəyi', 'open': False}).json()
    assert len(sv['questions']) == 33 and sv['links'][0]['label'] == 'Ümumi link'
    tok = sv['links'][0]['token']
    g = _guest()
    r = g.get(f'/api/public/surveys/{tok}')                               # qaralama – hələ başlamayıb
    assert r.status_code == 410 and 'başlamayıb' in r.json()['detail']
    assert admin.post(f'/api/surveys/{sv["id"]}/status', json={'status': 'open'}).json()['state'] == 'open'
    pub = g.get(f'/api/public/surveys/{tok}').json()
    assert pub['teacher'] == 'Həsənov Fərid' and all('reverse' not in q for q in pub['questions'])

    # yoxlamalar: məcburi sual, səhv dəyər, HTML təmizlənir
    bad = _answers(sv)
    bad.pop(str(sv['questions'][0]['id']))
    assert g.post(f'/api/public/surveys/{tok}/responses', json={'answers': bad}).status_code == 400
    bad = {**_answers(sv), str(sv['questions'][0]['id']): 7}
    assert g.post(f'/api/public/surveys/{tok}/responses', json={'answers': bad}).status_code == 400

    # sinif linki – yalnız öz dərsi üçün
    sv2 = admin.post(f'/api/surveys/{sv["id"]}/links', json={'ta_id': ta}).json()
    cl = next(l for l in sv2['links'] if l['class_id'] == cid)
    assert cl['label'] == 'X e'
    assert as_('ilqar').post(f'/api/surveys/{sv["id"]}/links', json={'ta_id': ta}).status_code == 404

    vals = [(5, 1, 10, 10), (4, 2, 8, 9), (4, 2, 7, 7), (3, 3, 6, 5), (5, 1, 9, 10)]
    for i, (lk, rv, ov, np_) in enumerate(vals[:4]):
        c = _guest()
        r = c.post(f'/api/public/surveys/{cl["token"]}/responses',
                   json={'answers': _answers(sv, lk, rv, ov, np_, text=f'<b>Fikir {i}</b>'), 'device': f'device-{i:04d}'})
        assert r.status_code == 200, r.text
        if i == 0:                                                         # eyni cihaz – təkrar olmaz
            again = c.post(f'/api/public/surveys/{cl["token"]}/responses', json={'answers': _answers(sv)})
            assert again.status_code == 409
    res = admin.get(f'/api/surveys/{sv["id"]}/results').json()
    assert res['n'] == 4 and res['hidden'] and 'questions' not in res               # < 5 – gizli
    assert admin.get(f'/api/surveys/{sv["id"]}/export.csv').status_code == 409
    lk, rv, ov, np_ = vals[4]
    assert _guest().post(f'/api/public/surveys/{tok}/responses',
                         json={'answers': _answers(sv, lk, rv, ov, np_)}).status_code == 200

    res = admin.get(f'/api/surveys/{sv["id"]}/results').json()
    assert res['n'] == 5 and not res['hidden']
    a5 = next(q for q in res['questions'] if q['key'] == 'A5')
    assert a5['mean'] == 1.8 and a5['adj_mean'] == 4.2 and a5['agree_pct'] == 80.0       # əks sual: 6 − x
    sec_a = next(x for x in res['section_index'] if x['key'] == 'A')
    assert sec_a['index'] == 4.2                                                          # (4×4,2 + 4,2) / 5
    assert res['overall']['mean'] == 8.0
    assert res['nps'] == {'n': 5, 'score': 40, 'promoters': 3, 'passives': 1, 'detractors': 1}
    assert [x['text'] for x in res['texts'][0]['items']] and all('<' not in x['text'] for x in res['texts'][0]['items'])
    assert {l['label']: l['n'] for l in res['links']} == {'Ümumi link': 1, 'X e': 4}
    assert res['compare'] == []                                         # hər linkdə < 5 – müqayisə gizli
    assert admin.get(f'/api/surveys/{sv["id"]}/results', params={'link_id': cl['id']}).json()['hidden']

    # anonimlik: cavab cədvəlində şagirdi/cihazı göstərən sahə yoxdur
    cols = set(SurveyResponse.__table__.columns.keys())
    assert cols == {'id', 'survey_id', 'link_id', 'period', 'submitted_on', 'answers', 'hidden'}

    # açıq cavabı hesabatdan gizlətmək
    item = res['texts'][0]['items'][0]
    admin.post(f'/api/surveys/{sv["id"]}/responses/{item["rid"]}/hide', json={'qid': res['texts'][0]['qid'], 'hidden': True})
    res = admin.get(f'/api/surveys/{sv["id"]}/results').json()
    assert next(x for x in res['texts'][0]['items'] if x['rid'] == item['rid'])['hidden']

    # CSV
    r = admin.get(f'/api/surveys/{sv["id"]}/export.csv')
    assert r.status_code == 200 and r.text.startswith('﻿№;') and len(r.text.strip().splitlines()) == 6

    # cavab gəldikdən sonra suallar dəyişmir
    body = {'title': 'Yeni ad', 'questions': [{'section': 'A', 'kind': 'likert5', 'text': 'Yeni sual'}]}
    assert admin.put(f'/api/surveys/{sv["id"]}', json=body).status_code == 409
    assert admin.put(f'/api/surveys/{sv["id"]}', json={'title': 'Yeni ad'}).json()['title'] == 'Yeni ad'

    # məxfilik: başqa müəllim, başqa məktəb, şagird
    assert as_('ilqar').get(f'/api/surveys/{sv["id"]}/results').status_code == 404
    assert as_('yad').get(f'/api/surveys/{sv["id"]}').status_code == 404
    assert as_('ilqar').get('/api/surveys').json() == []
    s0 = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    assert s0.get(f'/api/surveys/{sv["id"]}/results').status_code == 403

    # link deaktiv → 404; sorğu bağlı → 410
    admin.post(f'/api/surveys/{sv["id"]}/links/{cl["id"]}', json={'active': False})
    assert _guest().get(f'/api/public/surveys/{cl["token"]}').status_code == 404
    admin.post(f'/api/surveys/{sv["id"]}/status', json={'status': 'closed'})
    r = _guest().post(f'/api/public/surveys/{tok}/responses', json={'answers': _answers(sv)})
    assert r.status_code == 410 and 'bağlanıb' in r.json()['detail']

    # təkrar sorğu (2-ci dalğa) – suallar köçürülür
    w2 = admin.post('/api/surveys', json={'title': 'Yarımil sonu', 'from_id': sv['id']}).json()
    assert w2['wave'] == 2 and w2['root_id'] == sv['id'] and len(w2['questions']) == 33

    # silmə: əvvəl arxiv, sonra adı yazaraq
    assert admin.request('DELETE', f'/api/surveys/{sv["id"]}', json={'confirm': 'Yeni ad'}).status_code == 409
    admin.post(f'/api/surveys/{sv["id"]}/archive')
    assert admin.request('DELETE', f'/api/surveys/{sv["id"]}', json={'confirm': 'səhv'}).status_code == 400
    assert admin.request('DELETE', f'/api/surveys/{sv["id"]}', json={'confirm': 'Yeni ad'}).status_code == 200
    with S() as db:
        assert db.query(SurveyResponse).filter_by(survey_id=sv['id']).count() == 0


def test_weekly_in_app(world, monkeypatch):
    as_, S = world
    clock = _clock(monkeypatch)
    admin, ta, cid, st, _ = setup(world)
    sv = admin.post('/api/surveys', json={'title': 'Həftəlik rəy', 'repeat': 'weekly', 'include_demo': True, 'open': False}).json()
    assert len(sv['questions']) == 35
    s0 = student_client(st[0]['portal_code'], st[0]['initial_pin'])
    assert s0.get('/api/portal/surveys').json() == []                    # hələ açılmayıb
    admin.post(f'/api/surveys/{sv["id"]}/status', json={'status': 'open'})
    lst = s0.get('/api/portal/surveys').json()
    assert lst[0]['id'] == sv['id'] and not lst[0]['done'] and lst[0]['period_label'] == '05.10–11.10.2026'
    one = s0.get(f'/api/portal/surveys/{sv["id"]}').json()
    assert one['label'] == 'X e' and one['repeat'] == 'weekly'
    # qısa həftəlik sorğu: 6 meyardan bir sual + ümumi bal + bir açıq sual (yorucu olmasın)
    w41 = one['questions']
    assert len(w41) == 8 and sorted({q['section'] for q in w41 if q['kind'] == 'likert5'}) == list('ABCDEF')
    assert [q['key'] for q in w41 if q['kind'] == 'scale10'] == ['overall']
    assert s0.post(f'/api/portal/surveys/{sv["id"]}/responses', json={'answers': _answers(sv)}).status_code == 200
    assert s0.get('/api/portal/surveys').json()[0]['done']
    assert s0.post(f'/api/portal/surveys/{sv["id"]}/responses', json={'answers': _answers(sv)}).status_code == 409
    # eyni şagird açıq linklə də ikinci dəfə yaza bilmir (eyni həftə)
    tok = sv['links'][0]['token']
    assert s0.get(f'/api/public/surveys/{tok}').json()['done']
    assert s0.post(f'/api/public/surveys/{tok}/responses', json={'answers': _answers(sv)}).status_code == 409
    # sinif linki avtomatik yaranıb (müqayisə üçün)
    assert any(l['class_id'] == cid and l['responses'] == 1 for l in admin.get(f'/api/surveys/{sv["id"]}').json()['links'])

    # yeni həftə – sorğu yenilənir
    clock.t = dt.datetime(2026, 10, 12, 9, 0, tzinfo=UTC)
    assert not s0.get('/api/portal/surveys').json()[0]['done']
    w42 = s0.get(f'/api/portal/surveys/{sv["id"]}').json()['questions']
    assert len(w42) == 8 and {q['id'] for q in w42 if q['kind'] == 'likert5'}.isdisjoint({q['id'] for q in w41 if q['kind'] == 'likert5'})
    assert s0.post(f'/api/portal/surveys/{sv["id"]}/responses', json={'answers': _answers(sv)}).status_code == 200
    with S() as db:
        assert sorted(r.period for r in db.query(SurveyResponse)) == ['2026-W41', '2026-W42']

    # həftələr üzrə: hər həftədə ≥ 5 cavab olduqda dinamika
    for i in range(4):
        _guest().post(f'/api/public/surveys/{tok}/responses', json={'answers': _answers(sv, likert=3)})
    res = admin.get(f'/api/surveys/{sv["id"]}/results').json()
    assert [p['period'] for p in res['periods']] == ['2026-W41', '2026-W42']
    assert [w['period'] for w in res['weeks']] == ['2026-W42'] and res['weeks'][0]['n'] == 5
    assert admin.get(f'/api/surveys/{sv["id"]}/results', params={'period': '2026-W41'}).json()['hidden']
    assert admin.put(f'/api/surveys/{sv["id"]}', json={'title': 'Həftəlik rəy', 'repeat': 'once'}).status_code == 409

    # tam həftəlik sorğu (qısa rejim söndürülüb) – bütün suallar
    admin.put(f'/api/surveys/{sv["id"]}', json={'title': 'Həftəlik rəy', 'repeat': 'weekly', 'pulse': False})
    assert len(s0.get(f'/api/portal/surveys/{sv["id"]}').json()['questions']) == 35

    # in_app söndürüləndə tətbiqdə görünmür
    admin.put(f'/api/surveys/{sv["id"]}', json={'title': 'Həftəlik rəy', 'repeat': 'weekly', 'in_app': False})
    assert s0.get('/api/portal/surveys').json() == []
    assert s0.get(f'/api/portal/surveys/{sv["id"]}').status_code == 404


def test_ai_review(world, monkeypatch):
    as_, S = world
    _clock(monkeypatch)
    admin, *_ = setup(world)
    sv = admin.post('/api/surveys', json={'title': 'Rəy'}).json()
    admin.post(f'/api/surveys/{sv["id"]}/status', json={'status': 'open'})
    tok = sv['links'][0]['token']
    monkeypatch.setattr('app.api.lessonplans.ai_config', lambda u: {'provider': 'x', 'model': 'm-1', 'api_key': 'k'})
    seen = {}

    def fake(cfg, system, user):
        seen['ctx'] = user
        return {'xulase': 'Ümumilikdə yüksək qiymət.', 'guclu': ['İzah aydındır'], 'inkisaf': ['Qiymətləndirmə meyarları'],
                'movzular': [{'movzu': 'maraqlı dərs', 'say': 5, 'ton': 'müsbət'}],
                'tovsiyeler': [{'ne': 'Meyarları əvvəlcədən paylaşmaq', 'muddet': '3 həftə', 'olcu': 'C1 ≥ 4'}], 'diqqet': []}
    monkeypatch.setattr('app.ai.complete_json', fake)
    assert admin.post(f'/api/surveys/{sv["id"]}/ai-review', json={}).status_code == 409    # cavab az
    for _ in range(5):
        _guest().post(f'/api/public/surveys/{tok}/responses', json={'answers': _answers(sv)})
    r = admin.post(f'/api/surveys/{sv["id"]}/ai-review', json={}).json()['review']
    assert r['payload']['tovsiyeler'][0]['olcu'] == 'C1 ≥ 4' and r['payload']['n'] == 5
    assert 'Dərslər maraqlıdır' in seen['ctx']
    assert admin.get(f'/api/surveys/{sv["id"]}/ai-review').json()['review']['id'] == r['id']


def test_link_modes_whatsapp(world, monkeypatch):
    """WhatsApp qrupu üçün: eyni sorğuya tam və qısa link; qısa birdəfəlik linkdə hər şagird başqa dəst alır."""
    as_, S = world
    _clock(monkeypatch)
    admin, *_ = setup(world)
    sv = admin.post('/api/surveys', json={'title': 'Rəy'}).json()
    admin.post(f'/api/surveys/{sv["id"]}/status', json={'status': 'open'})
    sv = admin.post(f'/api/surveys/{sv["id"]}/links', json={'mode': 'short'}).json()
    full, short = sv['links'][0], sv['links'][1]
    assert (full['effective'], full['served']) == ('full', 33) and short['effective'] == 'short' and short['served'] == 9      # v=0: + NPS (4 variantda bir)
    g = _guest()
    assert len(g.get(f'/api/public/surveys/{full["token"]}').json()['questions']) == 33
    a = g.get(f'/api/public/surveys/{short["token"]}', params={'v': 0}).json()
    b = g.get(f'/api/public/surveys/{short["token"]}', params={'v': 1}).json()
    assert a['mode'] == 'short' and a['variant'] == 0 and len(a['questions']) == 9 and len(b['questions']) == 8
    assert {q['id'] for q in a['questions']} != {q['id'] for q in b['questions']}
    # qısa cavab: yalnız verilən suallar məcburidir
    ans = {str(q['id']): (4 if q['kind'] == 'likert5' else 8) for q in b['questions'] if q['kind'] != 'text'}
    assert g.post(f'/api/public/surveys/{short["token"]}/responses', json={'answers': ans, 'variant': 1}).status_code == 200
    # tam link qısa cavabı qəbul etmir (məcburi suallar)
    assert _guest().post(f'/api/public/surveys/{full["token"]}/responses', json={'answers': ans}).status_code == 400
    # rejimi sonradan dəyişmək
    sv = admin.post(f'/api/surveys/{sv["id"]}/links/{full["id"]}', json={'mode': 'short'}).json()
    assert sv['links'][0]['effective'] == 'short'


def test_new_survey_open_by_default(world, monkeypatch):
    """Yaradılan sorğu dərhal açıqdır – müəllim linki göndərəndə «bağlıdır» çıxmasın; planlaşdırılmış sorğuda tarix yazılır."""
    as_, S = world
    clock = _clock(monkeypatch)
    admin, *_ = setup(world)
    sv = admin.post('/api/surveys', json={'title': 'Rəy'}).json()
    assert sv['state'] == 'open'
    assert _guest().get(f'/api/public/surveys/{sv["links"][0]["token"]}').status_code == 200
    admin.put(f'/api/surveys/{sv["id"]}', json={'title': 'Rəy', 'opens_at': '2026-10-06T06:00:00Z'})
    r = _guest().get(f'/api/public/surveys/{sv["links"][0]["token"]}')
    assert r.status_code == 410 and '06.10.2026 10:00' in r.json()['detail']
    clock.t = dt.datetime(2026, 10, 6, 7, 0, tzinfo=UTC)
    assert _guest().get(f'/api/public/surveys/{sv["links"][0]["token"]}').status_code == 200
