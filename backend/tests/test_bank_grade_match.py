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
