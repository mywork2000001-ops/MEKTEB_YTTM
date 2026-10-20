"""Mövzu nömrəsi, uyğunluq həddi (ok/weak/none/pending) və Plan səhifəsi nişanı (docs/mekteb-plan-movzu-testleri-promtu.md)."""
import datetime as dt
import types

from app.bank.match import PENDING_GRADES, bank_no, base_topic, topic_no, topic_numbers
from app.models import BankFile, BankSource, LessonBankLink, PlanLesson, TeachingAssignment


def L(topic, section=None, typ='formativ', id=None):
    return {'id': id, 'topic': topic, 'section': section, 'assessment_type': typ}


def test_topic_no_from_text_and_section_order():
    assert topic_no(L('3.4. Triqonometriya')) == '3.4' and topic_no(L('X sinif: 2.1 Funksiya')) == '2.1'
    assert topic_no(L('§12 Faiz')) == '12' and topic_no(L('Kvadrat tənliklər')) is None
    ls = [L('Funksiya anlayışı. Nəzəri xülasə və nümunə məsələlər', '1. Funksiya'), L('Funksiya anlayışı (2/2). Məsələ həlli', '1. Funksiya'),
          L('Funksiya anlayışı. Sinif testi və təhlil', '1. Funksiya'), L('Funksiyaların xassələri. Test', '1. Funksiya'),
          L('KSQ-1: Funksiya', '1. Funksiya', 'KSQ'), L('Fəzada paralellik. Test', '2. Fəza'),
          L('Məşq və möhkəmləndirmə: Funksiyaların xassələri', 'Bazanın bərpası'), L('Bölmə təkrarı: Funksiya', 'Təkrar')]
    assert topic_numbers(ls) == ['1.1', '1.1', '1.1', '1.2', None, '2.1', '1.2', None]       # törəmə dərs əsas mövzunun nömrəsini alır
    assert topic_no(ls[3], None, ls) == '1.2'
    prog = types.SimpleNamespace(data={'template': {'semesters': [[{'section': '1. Funksiya', 'topics': ['Əvvəlki', 'Funksiya anlayışı']}]]}})
    assert topic_numbers(ls[:1], prog) == ['1.2']                                             # şablon sırası üstündür


def test_base_topic_and_bank_no():
    assert base_topic('X sinif: Kvadrat tənliklər (2/3). Məsələ həlli') == 'Kvadrat tənliklər'
    assert base_topic('Kvadrat tənliklər. Sinif testi') == 'Kvadrat tənliklər'
    f = lambda label, lesson='x': BankFile(label=label, lesson=lesson, source_key='p013')
    assert bank_no(f('Tənliklər — 2.3 Kvadrat tənliklər')) == '2.3' and bank_no(f('Faiz', 'f2/3.1/q')) == '3.1'
    assert bank_no(f('12. Tənliklər — Kvadrat')) is None


def _class(admin, S, name, topics, slots=None):
    cid = admin.post('/api/classes', json={'name': name}).json()['id']
    slots = slots or {'3': [2]}
    r = admin.post(f'/api/classes/{cid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': sum(len(v) for v in slots.values()), 'slots': slots})
    assert r.status_code == 200, r.text
    with S() as db:
        ta = db.query(TeachingAssignment).filter_by(class_id=cid).one()
        for i, (t, typ, sec) in enumerate(topics):
            db.add(PlanLesson(assignment_id=ta.id, seq=i + 1, semester=1, assessment_type=typ, topic=t, section=sec, date=dt.date(2026, 9, 17)))
        db.commit()
        return ta.id, [p.id for p in db.query(PlanLesson).filter_by(assignment_id=ta.id).order_by(PlanLesson.seq)]


def _bank(S, rows):
    with S() as db:
        db.add_all([BankSource(key=k, label=k) for k in ('p003', 'p013', 'p001')]); db.flush()
        for src, lesson, label, grades in rows:
            db.add(BankFile(source_key=src, lesson=lesson, label=label, url='http://x/' + lesson, kind='movzu', question_count=20, grades=grades))
        db.commit()
        return {f.lesson: f.id for f in db.query(BankFile)}


def _lessons(admin, ta):
    items = admin.get(f'/api/plan/{ta}', params={'view': 'year', 'date': '2026-09-17'}).json()['items']
    return {i['lesson']['topic']: i['lesson'] for i in items if i['lesson']}


def test_number_picks_right_file_and_names_fallback(world):
    """1. Eyni adlı iki fayl – mövzu nömrəsi düzgününü seçir. 2. Nömrəsiz plan – köhnə nəticə (ad oxşarlığı)."""
    as_, S = world
    admin = as_('admin')
    ids = _bank(S, [('p003', 'a', 'Tənliklər — 5.1 Kvadrat tənliklər', None), ('p003', 'b', 'Tənliklər — 2.3 Kvadrat tənliklər', None),
                    ('p003', 'c', 'Tənliklər — Kvadrat tənliyə gətirilən tənliklər', None)])
    # planda «Kvadrat tənliklər» 2-ci bölmənin 3-cü mövzusudur → «2.3»; iki fayl eyni ad, nömrələri 5.1 və 2.3 (nömrəsiz 'a' qalib gələrdi)
    ta, _ = _class(admin, S, 'X b', [('A mövzu', 'formativ', '2. Tənliklər'), ('B mövzu', 'formativ', '2. Tənliklər'),
                                     ('Kvadrat tənliklər', 'formativ', '2. Tənliklər')], {'3': [2, 3, 4]})
    k = _lessons(admin, ta)['Kvadrat tənliklər']
    assert k['topic_no'] == '2.3' and k['p0010']['file_id'] == ids['b'] and k['p0010_status'] == 'ok'
    # 2. nömrəsiz plan (Word) – nömrə yoxdur, ad oxşarlığı ilə köhnə nəticə
    ta2, _ = _class(admin, S, 'X e', [('Kvadrat tənliyə gətirilən tənliklər', 'formativ', None)])
    k2 = _lessons(admin, ta2)['Kvadrat tənliyə gətirilən tənliklər']
    assert k2['topic_no'] is None and k2['p0010']['file_id'] == ids['c']


def test_weak_none_manual_and_summative(world):
    """3. Zəif uyğunluq – 'weak' (qoşulur), çox zəif – 'none' (qoşulmur). 4. Əl ilə seçim qorunur; KSQ-ya test yoxdur."""
    as_, S = world
    admin = as_('admin')
    ids = _bank(S, [('p003', 'a', 'Həndəsə — Üçbucaqların bərabərliyi və oxşarlığı sınaqları', None)])
    ta, pls = _class(admin, S, 'X c', [('Üçbucaqların oxşarlığı və sahə düsturları sınaq', 'formativ', None),     # 2/3 kök uyğun...
                                       ('Üçbucaqların həndəsi çevrilmələri məsələləri', 'formativ', None),
                                       ('Loqarifm funksiyası', 'formativ', None), ('KSQ-1: Həndəsə', 'KSQ', None)], {'3': [2, 3, 4, 5]})
    ls = _lessons(admin, ta)
    assert ls['Loqarifm funksiyası']['p0010'] is None and ls['Loqarifm funksiyası']['p0010_status'] == 'none'
    assert 'p0010' not in ls['KSQ-1: Həndəsə'] or ls['KSQ-1: Həndəsə'].get('p0010') is None
    weak = [l for l in ls.values() if l.get('p0010_status') == 'weak']
    ok = [l for l in ls.values() if l.get('p0010_status') == 'ok']
    assert len(weak) + len(ok) == 2 and all(l['p0010']['file_id'] == ids['a'] for l in weak + ok)
    r = admin.put(f'/api/plan/{ta}/topics/{pls[2]}/p0010', json={'mode': 'file', 'file_id': ids['a']})
    assert r.status_code == 200
    assert _lessons(admin, ta)['Loqarifm funksiyası']['p0010_status'] == 'manual'


def test_pending_grades_v_viii(world):
    """V–VIII: bank boşdur → tapılmayan mövzu 'pending' (gözlənilir); IX–XI → 'none'. PENDING_GRADES bir yerdə."""
    as_, S = world
    admin = as_('admin')
    assert PENDING_GRADES == {5, 6, 7, 8}
    _bank(S, [])
    ta5, _ = _class(admin, S, 'VII a', [('Natural ədədlər', 'formativ', None)])
    ta10, _ = _class(admin, S, 'X d', [('Natural ədədlər', 'formativ', None)])
    assert _lessons(admin, ta5)['Natural ədədlər']['p0010_status'] == 'pending'
    assert _lessons(admin, ta10)['Natural ədədlər']['p0010_status'] == 'none'
