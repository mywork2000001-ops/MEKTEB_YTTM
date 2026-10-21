"""İnkişaf qrupu – ardıcıl zəncir (V→IX; docs/inkisaf-qrupu-ardicil-proqram-promtu.md §3, §5, §6): ardıcıllıq, bir məşğələ – bir mövzu,
günlər/saat/end_date, Təkrar çıxır, illik testlər, alt mövzular, idempotentlik, keçirilmiş/əl ilə mövzulara toxunmamaq, defolt (gündəlik tapşırıq)."""
import datetime as dt

from app import extra_chain as XC
from app import programs
from app.extra_programs import assign_programs
from app.models import ExtraCourse, ExtraSession

from .test_api_portal import UTC, clock  # noqa: F401 – clock fixture
from .test_extra_programs import SAT, mk_class, mk_course, setup_programs

END = dt.date(2027, 1, 26)
CHAIN = {'kind': 'inkisaf', 'mode': 'chain'}


def start(world, clock, monkeypatch, name='V a', title='İnkişaf qrupu'):
    as_, S = world
    monkeypatch.setattr('app.api.extra.now', clock)
    clock.t = dt.datetime(2026, 10, 21, 8, 0, tzinfo=UTC)
    admin = as_('admin')
    setup_programs(S)
    ta, _, _ = mk_class(admin, S, name)
    c = mk_course(admin, ta, title, kind='inkisaf', starts_on='2026-10-21', ends_on='2026-11-30')
    return admin, S, c


def rows_of(admin, cid):
    ses = admin.get(f'/api/extra/{cid}').json()['session_list']
    return [s for s in ses if s['topics']]


def test_entries_order_and_content():
    e = XC.build_entries(XC.normalize({}))
    txt = [x['text'] for x in e]
    assert txt[0].startswith('V sinif · 3. Onluq kəsrlər') and 'Alt mövzular: Onluq kəsrlər' in txt[0]
    assert [x['ref'] for x in e[:6]] == ['ch:5:3.1', 'ch:5:4.1', 'ch:5:4.2', 'ch:5:5.1', 'ch:5:6.1', 'ch:5:6.2']      # V 2-ci yarımil: 6 mövzu
    assert e[6]['ref'] == 'ch:5:annual' and e[6]['text'] == 'V sinif illik test' and e[6]['topic'] is None
    vi = [x for x in e if x['grade'] == 6]
    assert vi and not any('Təkrar' in (x['section'] or '') for x in vi) and vi[-1]['ref'] == 'ch:6:annual'
    assert [x['grade'] for x in e] == sorted(x['grade'] for x in e)                       # V → VI → VII → VIII → IX
    assert len({x['ref'] for x in e}) == len(e)
    full = XC.build_entries(XC.normalize({'start': {'grade': 5, 'semester': 1}}))
    assert full[0]['text'].startswith('V sinif · 1. Natural ədədlər') and len(full) == len(e) + 5
    assert not any(x['prereq'] for x in e if x['grade'] == 5)                            # prereq yalnız VI–VII


def test_subtopics_az_ru_en_and_no_invention():
    e = {(x['grade'], x['topic']): x for x in XC.build_entries(XC.normalize({}))}
    v = e[(5, 'Faiz')]
    assert v['sub'] == {'az': 'Faiz', 'ru': 'Проценты', 'en': 'Percent'} and v['links'][0]['url'].endswith('/Lesson-10.html')
    dec = e[(5, 'Onluq kəsrlər')]['sub']
    assert dec['az'].startswith('Onluq kəsrlər; Adi və onluq') and 'Десятичные' in dec['ru'] and 'Decimal' in dec['en']
    p6 = e[(6, 'Adi kəsrlərin müqayisəsi')]
    assert p6['prereq']['az'] == 'Adi kəsrlər; Adi kəsrlərin müqayisəsi' and '5-ci sinifdən təkrar: Adi kəsrlər' in p6['text']
    assert e[(6, 'Koordinatlar. Funksiya')]['prereq'] is None                            # uyğunluq yoxdur – boş
    assert 'təkrar' not in e[(6, 'Koordinatlar. Funksiya')]['text']
    assert e[(7, 'Çoxhədli')]['prereq'] is None
    off = {(x['grade'], x['topic']): x for x in XC.build_entries(XC.normalize({'p001': False}))}
    assert off[(5, 'Faiz')]['sub'] is None and off[(6, 'Tənasüb')]['prereq'] is None


def test_preview_and_apply(world, clock, monkeypatch):
    admin, S, c = start(world, clock, monkeypatch)
    cid = c['id']
    p = admin.post(f'/api/extra/{cid}/program', json={**CHAIN, 'dry': True})
    assert p.status_code == 200, p.text
    p = p.json()
    ch = p['chain']
    assert p['mode'] == 'chain' and p['applicable'] and ch['schedule_changed']
    assert ch['config']['weekdays'] == [2, 3, 4] and ch['config']['end_date'] == '2027-01-26'
    assert ch['first'] >= '2026-10-21' and ch['last'] <= '2027-01-26'
    assert ch['sessions'] == len(p['rows']) == sum(x['n'] for x in ch['by_grade'])
    assert 30 <= ch['sessions'] <= 45, ch['sessions']                                       # ~14 həftə × 3, tətillər çıxılır
    assert ch['overflow'] > 0 and p['warnings'] and p['topics_left'] == ch['overflow']      # IX-a qədər sığmır → xəbərdarlıq
    assert [r['grade'] for r in p['rows'][:7]] == [5] * 7 and p['rows'][6]['ref'] == 'ch:5:annual'
    for r in p['rows']:
        d = dt.date.fromisoformat(r['date'])
        assert d.weekday() in (2, 3, 4) and d <= END and (r['start'], r['end']) == ('21:00', '22:00')
    with S() as db:                                                                         # önbaxış heç nə yazmır
        assert [s['weekday'] for s in db.get(ExtraCourse, cid).schedule] == [5] and db.query(ExtraSession).filter(ExtraSession.topic_ref.is_not(None)).count() == 0
        assert db.get(ExtraCourse, cid).audience.get('chain') is None

    a = admin.post(f'/api/extra/{cid}/program', json=CHAIN).json()
    assert a['chain']['sessions'] == ch['sessions'] and [r['ref'] for r in a['rows']] == [r['ref'] for r in p['rows']]
    full = admin.get(f'/api/extra/{cid}').json()
    assert full['schedule'][0]['start'] == '21:00' and sorted(s['weekday'] for s in full['schedule']) == [2, 3, 4]
    ses = rows_of(admin, cid)
    assert len(ses) == ch['sessions'] and all(len(s['topics']) == 1 for s in ses)           # bir məşğələ – bir mövzu
    assert ses[0]['topics'][0]['sub']['ru'] == 'Десятичные дроби; Обыкновенные и десятичные дроби (смешанные действия)'
    assert max(s['date'] for s in full['session_list']) <= END.isoformat()
    with S() as db:
        aud = db.get(ExtraCourse, cid).audience
        assert aud['chain']['weekdays'] == [2, 3, 4] and aud['ta_ids']                     # audience-in qalan hissəsi qorunur
        assert db.get(ExtraCourse, cid).program_id is None

    again = admin.post(f'/api/extra/{cid}/program', json=CHAIN).json()                      # idempotent
    assert [r['ref'] for r in again['rows']] == [r['ref'] for r in a['rows']] and again['chain']['schedule_changed'] is False
    after = rows_of(admin, cid)
    assert [s['topics'] for s in after] == [s['topics'] for s in ses]


def test_held_and_manual_untouched_and_resume(world, clock, monkeypatch):
    admin, S, c = start(world, clock, monkeypatch)
    cid = c['id']
    admin.post(f'/api/extra/{cid}/program', json=CHAIN)
    ses = admin.get(f'/api/extra/{cid}').json()['session_list']
    sid = [s['id'] for s in ses]
    admin.put(f'/api/extra/{cid}/sessions/{sid[3]}', json={'topics': [{'text': 'Mənim mövzum'}]})
    with S() as db:
        s0 = db.get(ExtraSession, sid[0])
        s0.status = 'held'
        db.commit()
    clock.t = dt.datetime(2026, 10, 23, 8, 0, tzinfo=UTC)
    r = admin.post(f'/api/extra/{cid}/program', json=CHAIN).json()
    assert r['held'] == 1 and r['kept_manual'] == 1
    now = admin.get(f'/api/extra/{cid}').json()['session_list']
    assert now[0]['topics'][0]['text'].startswith('V sinif · 3. Onluq')              # keçirilmiş toxunulmaz
    assert now[3]['topics'][0]['text'] == 'Mənim mövzum'
    refs = [t['topics'][0].get('ref') for t in now if t['topics']]
    with S() as db:
        refs = [s.topic_ref for s in db.query(ExtraSession).filter_by(course_id=cid) if s.topic_ref]
    assert len(refs) == len(set(refs))                                                  # dublikat yoxdur


def test_schedule_change_future_only_and_follow(world, clock, monkeypatch):
    admin, S, c = start(world, clock, monkeypatch)
    cid = c['id']
    admin.post(f'/api/extra/{cid}/program', json={**CHAIN, 'weekdays': [0, 1], 'start_time': '20:00', 'end_time': '21:00'})
    full = admin.get(f'/api/extra/{cid}').json()
    assert all(dt.date.fromisoformat(s['date']).weekday() in (0, 1) and s['start'] == '20:00' for s in full['session_list'])
    # müəllim cədvəli əl ilə dəyişir → zəncir izləyir, mövzular yenidən paylanır
    p = admin.patch(f'/api/extra/{cid}', json={'schedule': [{'weekday': 4, 'start': '19:00', 'end': '20:00'}]}).json()
    assert p['refilled'] is not None
    with S() as db:
        assert db.get(ExtraCourse, cid).audience['chain']['weekdays'] == [4]
    full = admin.get(f'/api/extra/{cid}').json()
    assert all(dt.date.fromisoformat(s['date']).weekday() == 4 for s in full['session_list'] if s['status'] == 'planned')


def test_validation_and_default_job(world, clock, monkeypatch):
    admin, S, c = start(world, clock, monkeypatch)
    cid = c['id']
    assert admin.post(f'/api/extra/{cid}/program', json={**CHAIN, 'weekdays': [9]}).status_code == 400
    assert admin.post(f'/api/extra/{cid}/program', json={**CHAIN, 'start_time': '22:00', 'end_time': '21:00'}).status_code == 400
    # gündəlik tapşırıq (assign_programs): öz proqramı olmayan inkişaf qrupu defolt zəncirlə
    with S() as db:
        rows = assign_programs(db, [db.get(ExtraCourse, cid)], dt.date(2026, 10, 21), apply=True)
        db.commit()
        assert rows[0]['mode'] == 'chain' and rows[0]['to_fill'] > 30
        cc = db.get(ExtraCourse, cid)
        assert cc.audience['chain']['grades'] == [5, 9] and sorted(s['weekday'] for s in cc.schedule) == [2, 3, 4]
        assert all(s['start'] == '21:00' for s in cc.schedule)
        first = db.query(ExtraSession).filter_by(course_id=cid).order_by(ExtraSession.date).first()
        assert first.topic_ref == 'ch:5:3.1'
        again = assign_programs(db, [cc], dt.date(2026, 10, 21), apply=True)
        assert again[0]['mode'] == 'chain' and again[0]['to_fill'] == rows[0]['to_fill']
    # müəllim proqramı ayırdı → zəncir geri qayıtmır
    admin.delete(f'/api/extra/{cid}/program')
    with S() as db:
        cc = db.get(ExtraCourse, cid)
        assert cc.audience['chain'] == {'enabled': False} and not XC.default_eligible(db, cc)


def test_non_inkisaf_not_chained(world, clock, monkeypatch):
    as_, S = world
    monkeypatch.setattr('app.api.extra.now', clock)
    clock.t = dt.datetime(2026, 10, 21, 8, 0, tzinfo=UTC)
    admin = as_('admin')
    setup_programs(S)
    ta, _, _ = mk_class(admin, S, 'IX a')
    c = mk_course(admin, ta, 'Olimpiada')
    with S() as db:
        assert not XC.default_eligible(db, db.get(ExtraCourse, c['id']))
