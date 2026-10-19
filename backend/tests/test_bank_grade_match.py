"""Sinfə görə testlər (docs/sinfe-gore-testler-promtu.md): plan dərsinin testi dərsin öz sinfinin bankından."""
import datetime as dt

from app.models import BankFile, BankSource, LessonBankLink, PlanLesson, TeachingAssignment


def _class(admin, S, name, topics, slots=None):
    cid = admin.post('/api/classes', json={'name': name}).json()['id']
    slots = slots or {'3': [2]}
    r = admin.post(f'/api/classes/{cid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': sum(len(v) for v in slots.values()), 'slots': slots})
    assert r.status_code == 200, r.text
    with S() as db:
        ta = db.query(TeachingAssignment).filter_by(class_id=cid).one()
        for i, (t, typ) in enumerate(topics):
            db.add(PlanLesson(assignment_id=ta.id, seq=i + 1, semester=1, assessment_type=typ, topic=t, date=dt.date(2026, 9, 17)))
        db.commit()
        return cid, ta.id, [p.id for p in db.query(PlanLesson).filter_by(assignment_id=ta.id).order_by(PlanLesson.seq)]


def _bank(S):
    with S() as db:
        db.add_all([BankSource(key=k, label=k) for k in ('p001', 'p003', 'p007', 'p013')]); db.flush()
        for src, lesson, label, grades in (
                ('p007', 'a', 'Natural ədədlər', [9]), ('p007', 'b', 'Kvadrat tənliklər', [9]),
                ('p001', 'c', 'Natural ədədlər', [5]), ('p003', 'd', 'Natural ədədlər — Natural ədədlər', None),
                ('p003', 'e', 'Tənliklər — Kvadrat tənliklər', None)):
            db.add(BankFile(source_key=src, lesson=lesson, label=label, url='http://x/' + lesson, kind='movzu', question_count=20, grades=grades))
        db.commit()
        return {f.lesson: f.id for f in db.query(BankFile)}


def _lessons(admin, ta):
    items = admin.get(f'/api/plan/{ta}', params={'view': 'year', 'date': '2026-09-17'}).json()['items']
    return {i['lesson']['topic']: i['lesson'] for i in items if i['lesson']}


def test_prep_course_lesson_gets_own_grade_file(world):
    """1. IX hazırlıq kursu: «V sinif: …» dərsinə yalnız V sinif faylı düşür; P007 faylı düşmür."""
    as_, S = world
    admin = as_('admin')
    ids = _bank(S)
    _, ta, _ = _class(admin, S, 'IX a', [('V sinif: Natural ədədlər', 'formativ'), ('IX sinif: Kvadrat tənliklər', 'formativ')],
                      {'3': [2, 3]})
    ls = _lessons(admin, ta)
    v, ix = ls['V sinif: Natural ədədlər'], ls['IX sinif: Kvadrat tənliklər']
    assert v['lesson_grade'] == 5 and v['p0010']['file_id'] == ids['c'] and 5 in v['p0010']['grades']
    assert v['p0010']['source'] != 'p007' and v['p0010_src'] == 'p001'
    assert ix['lesson_grade'] == 9 and ix['p0010']['file_id'] == ids['b']          # IX → DİM 9 toplusu (P007)


def test_school_grade_x_unchanged(world):
    """3. Məktəb X sinfi: P0010 (p003) – köhnə nəticə; başqa sinfin (p001/p007) faylı düşmür."""
    as_, S = world
    admin = as_('admin')
    ids = _bank(S)
    _, ta, _ = _class(admin, S, 'X a', [('Natural ədədlər', 'formativ'), ('Kvadrat tənliklər', 'formativ')], {'3': [2, 3]})
    ls = _lessons(admin, ta)
    assert ls['Natural ədədlər']['p0010']['file_id'] == ids['d'] and ls['Natural ədədlər']['lesson_grade'] == 10
    assert ls['Kvadrat tənliklər']['p0010']['file_id'] == ids['e']
    assert ls['Natural ədədlər']['p0010_src'] == 'p003'


def test_manual_link_survives_and_wins(world):
    """4. Əl ilə seçilmiş link yenidən tətbiqdən (eyni mövzu) sonra qalır və avtomatikdən üstündür; bank_source sabitdirsə köhnə davranış."""
    as_, S = world
    admin = as_('admin')
    ids = _bank(S)
    _, ta, pls = _class(admin, S, 'IX b', [('V sinif: Natural ədədlər', 'formativ')])
    r = admin.put(f'/api/plan/{ta}/topics/{pls[0]}/p0010', json={'mode': 'file', 'file_id': ids['d']})
    assert r.status_code == 200 and r.json()['p0010_manual'] and r.json()['p0010']['file_id'] == ids['d']
    lesson = _lessons(admin, ta)['V sinif: Natural ədədlər']
    assert lesson['p0010_manual'] and lesson['p0010']['file_id'] == ids['d']
    with S() as db:
        assert db.query(LessonBankLink).filter_by(plan_lesson_id=pls[0]).count() == 1
        db.get(TeachingAssignment, ta).bank_source = 'p007'; db.commit()
    assert admin.put(f'/api/plan/{ta}/topics/{pls[0]}/p0010', json={'mode': 'file', 'file_id': ids['d']}).status_code == 400   # ayar: yalnız p007
    assert admin.put(f'/api/plan/{ta}/topics/{pls[0]}/p0010', json={'mode': 'auto'}).status_code == 200
    got = _lessons(admin, ta)['V sinif: Natural ədədlər']
    assert got['p0010']['source'] == 'p007'                                       # sabit mənbə: sinif süzgəci yoxdur (köhnə davranış)


# ---------------------------------------------------------------- fərdi məkan: summativsiz, variantlar, sinif uyğunsuzluğu
def _private_group(t, name, grade, program_key, S, slots=None):
    cid = t.post('/api/classes', json={'name': name, 'kind': 'adi', 'private': True}).json()['id']
    pid = next(p['id'] for p in t.get('/api/programs').json() if p['key'] == program_key)       # daxili proqramlar ilk GET-də yaranır
    slots = slots or {'1': [1, 2], '3': [1, 2]}
    r = t.post(f'/api/classes/{cid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': sum(len(v) for v in slots.values()),
                                                 'slots': slots, 'grade': grade})
    assert r.status_code == 200, r.text
    return r.json()['mine']['ta_id'], pid


def test_private_group_has_no_summative_and_own_grade_tests(world):
    """2. VII fərdi qrup + «Sinif testləri – VII»: KSQ/BSQ yoxdur (formativ «Sınaq: bölmə»), testlər VII sinif fayllarından."""
    as_, S = world
    t = as_('ilqar')
    ta, pid = _private_group(t, 'Fərdi VII', 7, 'dim-sinif-testleri-7', S)
    with S() as db:
        assert db.get(TeachingAssignment, ta).has_summative is False
    pv = t.get(f'/api/programs/{pid}/preview/{ta}').json()
    kinds = {x['assessment_type'] for x in pv['list']}
    assert 'KSQ' not in kinds and 'BSQ' not in kinds and pv['ksq'] == 0 and pv['bsq'] == 0
    assert any(x['topic'].startswith('VII sinif: Sınaq:') and x['assessment_type'] == 'formativ' for x in pv['list'])
    first = next(x for x in pv['list'] if x['topic'].endswith('Sinif testi'))
    name = first['topic'].split(': ', 1)[1].rsplit('. Sinif testi', 1)[0]
    with S() as db:
        db.add_all([BankSource(key='p013', label='Sinif testləri'), BankSource(key='p001', label='P001')]); db.flush()
        db.add(BankFile(source_key='p001', lesson='x', label=name, url='http://x/v', kind='movzu', question_count=20, grades=[5]))   # V sinif – düşmür
        db.add(BankFile(source_key='p013', lesson='y', label=name, url='http://x/vii', kind='movzu', question_count=20, grades=[7]))
        db.commit()
    assert t.post(f'/api/programs/{pid}/apply/{ta}', json={}).status_code == 200
    items = t.get(f'/api/plan/{ta}', params={'view': 'year', 'date': '2026-10-01'}).json()['items']
    got = next(i['lesson'] for i in items if i['lesson'] and i['lesson']['topic'] == first['topic'])
    assert got['lesson_grade'] == 7 and got['p0010']['url'] == 'http://x/vii' and got['p0010']['grades'] == [7]


def test_variants_by_grade():
    """5. Variantlar sinfə görə: IX – yalnız A–B (C/D yoxdur → öz rəqəmləri), VIII – A–C, V – A–D."""
    from app.programs import grade_variants, variant_for
    assert [grade_variants(g) for g in (5, 8, 9, 11)] == ['A–D', 'A–C', 'A–B', 'A–D']
    assert variant_for('lesson', 'A–B') == 'A' and variant_for('mock', 'A–B') == 'A (öz rəqəmləri)'
    assert variant_for('final', 'A–B') == 'B (öz rəqəmləri)' and variant_for('mock', 'A–C') == 'C'
    assert variant_for('final', 'A–C') == 'B (öz rəqəmləri)' and variant_for('final', 'A–D') == 'D'


def test_course_resources_use_real_variants(world):
    from app.models import PlanProgram
    from app.programs import annotate_variants
    as_, S = world
    as_('ilqar').get('/api/programs')
    with S() as db:
        p = db.query(PlanProgram).filter_by(key='hazirliq-buraxilis-9').one()
        ls = [{'topic': 'V sinif: Natural ədədlər. Test', 'section': 'V sinif – X', 'resources': 'DİM: «N»', 'assessment_type': 'formativ'},
              {'topic': 'Aralıq sınaq (1)', 'section': 'V sinif – X', 'resources': None, 'assessment_type': 'formativ'},
              {'topic': 'IX sinif: Funksiya. Test', 'section': 'IX sinif – F', 'resources': None, 'assessment_type': 'formativ'},
              {'topic': 'Aralıq sınaq (2)', 'section': 'IX sinif – F', 'resources': None, 'assessment_type': 'formativ'},
              {'topic': 'Yekun sınaq imtahanı', 'section': 'Yekun', 'resources': None, 'assessment_type': 'formativ'}]
        annotate_variants(ls, p, 9)
        assert [l['resources'].rsplit('variant ', 1)[1] for l in ls] == ['A', 'C', 'A', 'A (öz rəqəmləri)', 'B (öz rəqəmləri)']


def test_course_grade_warning(world):
    """6. VII qrup + «Buraxılış – IX» kursu: sinif uyğunsuzluğu xəbərdarlığı və təklif olunan bölmələr (yalnız V–VII)."""
    import json

    from app.models import PlanProgram
    from app.programs import section_grade
    as_, S = world
    t = as_('ilqar')
    ta, pid = _private_group(t, 'Fərdi VII-b', 7, 'hazirliq-buraxilis-9', S)
    pv = t.get(f'/api/programs/{pid}/preview/{ta}').json()
    w = pv['grade_warning']
    assert w and w['params'] == {'top': 'IX', 'grp': 'VII'} and 'IX' in w['message'] and 'VII' in w['message']
    with S() as db:
        secs = {s['section']: s for s in db.query(PlanProgram).filter_by(key='hazirliq-buraxilis-9').one().data['template']['sections']}
    assert pv['suggest_sections'] and all(section_grade(secs[n]) <= 7 for n in pv['suggest_sections'])
    ok = t.get(f'/api/programs/{pid}/preview/{ta}', params={'sections': json.dumps(pv['suggest_sections'])}).json()
    assert ok['grade_warning'] is None
    ta9, pid9 = _private_group(t, 'Fərdi IX-b', 9, 'hazirliq-buraxilis-9', S)          # IX qrupu üçün IX kursu – xəbərdarlıq yoxdur
    assert t.get(f'/api/programs/{pid9}/preview/{ta9}').json()['grade_warning'] is None
