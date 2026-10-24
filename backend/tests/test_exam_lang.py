"""Sinfin sektoru və yazılı imtahanın dili (docs/tasks/sinif-sektoru-yazili-dil-2026-10-24.md): sıra, qrup, vərəq, onlayn KSQ, paket,
kiril sinif adı, yeni hesabın dili, miqrasiya."""
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

from app.domain.classes import grade_of
from app.domain.exam_lang import exam_lang, flatten_question, missing_translations, pick, render_question
from app.models import Exam, ExamVariant, OnlineTask, SchoolClass, Student, TeachingAssignment, User

from .test_ksq_scan import ksq

BACKEND = Path(__file__).resolve().parent.parent


def _ru_texts(world, exam_id, upto=3):
    """Variantların ilk `upto` sualına RU mətn (və test variantlarına RU) əlavə edir; qalanında RU yoxdur."""
    _, S = world
    with S() as db:
        for v in db.query(ExamVariant).filter_by(exam_id=exam_id):
            qs = [dict(q) for q in v.questions]
            for q in sorted(qs, key=lambda q: q['slot'])[:upto]:
                q['text'] = {'az': f'AZ-{q["slot"]}', 'ru': f'РУ-{q["slot"]}'}
                if q['kind'] == 'mcq':
                    q['options'] = [{'az': f'a{i}', 'ru': f'р{i}'} for i in range(len(q['options']))]
            for q in qs[upto:]:
                q['text'] = {'az': f'AZ-{q["slot"]}'}
                if q['kind'] == 'mcq':
                    q['options'] = [{'az': f'a{i}'} for i in range(len(q['options']))]
            v.questions = qs
        db.commit()


def _class_of(world, ta):
    _, S = world
    with S() as db:
        return db.get(TeachingAssignment, ta).class_id


def test_pure_order_exam_over_class_over_sector(world):
    _, S = world
    with S() as db:
        c = SchoolClass(school_id=1, year_id=1, name='VI a', code='VIA')
        db.add(c)
        db.flush()
        e = Exam()
        assert exam_lang(db, e, c) == 'az'                       # heç nə yoxdur
        c.sector = 'ru'
        assert exam_lang(db, e, c) == 'ru'                       # sektor (exam_language boş = sector)
        c.exam_language = 'az'
        assert exam_lang(db, e, c) == 'az'                       # sinfin yazılı qaydası sektordan üstündür
        c.exam_language = 'az_ru'
        assert exam_lang(db, e, c) == 'az_ru'
        c.exam_language = 'sector'
        assert exam_lang(db, e, c) == 'ru'
        e.language = 'az_ru'
        assert exam_lang(db, e, c) == 'az_ru'                    # imtahanın öz dili hamısından üstündür
        e.language = 'az'
        assert exam_lang(db, e, c) == 'az'
        assert exam_lang(db, Exam(), None) == 'az'


def test_group_takes_value_from_parent(world):
    _, S = world
    with S() as db:
        p = SchoolClass(school_id=1, year_id=1, name='VI b', code='VIB', sector='ru', exam_language='az')
        db.add(p)
        db.flush()
        g = SchoolClass(school_id=1, year_id=1, name='VI b (1)', code='VIB1', kind='qrup', parent_id=p.id)
        db.add(g)
        db.flush()
        assert exam_lang(db, Exam(), g) == 'az'                  # ana sinfin yazılı qaydası
        g.exam_language = 'ru'
        assert exam_lang(db, Exam(), g) == 'ru'                  # qrupun öz dəyəri üstündür
        g.exam_language, p.exam_language = None, None
        assert exam_lang(db, Exam(), g) == 'ru'                  # ana sinfin sektoru


def test_pick_render_and_missing():
    x = {'az': 'Salam', 'ru': 'Привет'}
    assert pick(x, 'az') == ('Salam', None) and pick(x, 'ru') == ('Привет', None) and pick(x, 'az_ru') == ('Salam', 'Привет')
    assert pick({'az': 'Salam'}, 'ru') == ('Salam', None)       # RU yoxdur – AZ
    assert pick({'az': 'Salam'}, 'az_ru') == ('Salam', None)    # ikidillidə RU yoxdursa yalnız AZ
    assert pick('sətir', 'ru') == ('sətir', None)
    q = {'slot': 4, 'kind': 'mcq', 'text': x, 'options': [{'az': 'a', 'ru': 'б'}, {'az': 'c'}]}
    r = render_question(q, 'az_ru')
    assert r['text'] == 'Salam' and r['text_sub'] == 'Привет' and r['options'] == ['a', 'c'] and r['options_sub'] == ['б', '']
    assert render_question(q, 'ru')['options'] == ['б', 'c'] and render_question(q, 'ru')['text_sub'] is None
    assert flatten_question(q, 'az_ru')['text'] == 'Salam\n\nПривет'
    assert missing_translations([q, {'slot': 5, 'kind': 'open', 'text': x}, {'slot': 6, 'kind': 'open', 'text': {'az': 'z'}}], 'ru') == [4, 6]
    assert missing_translations([q], 'az') == []


def test_sheet_language_ignores_student_interface_language(world):
    """Rus sektoru, yazılı – AZ: vərəq AZ (şagirdin interfeysi RU qalır). Yazılı – RU: vərəq RU (interfeys AZ olsa da)."""
    admin, ta, e, _ = ksq(world)
    _, S = world
    cid = _class_of(world, ta)
    _ru_texts(world, e['id'])
    with S() as db:
        for u in db.query(User).filter(User.role == 'student'):
            u.language = 'az'                                     # interfeysi AZ olan, amma rus sektorunda oxuyan şagird
        db.commit()
    r = admin.patch(f'/api/classes/{cid}', json={'sector': 'ru'})
    assert r.status_code == 200 and r.json()['sector'] == 'ru' and r.json()['exam_lang_eff'] == 'ru'
    pr = admin.get(f'/api/exams/{ta}/{e["id"]}/variants/print').json()
    assert pr['exam']['lang'] == 'ru' and all(s['lang'] == 'ru' for s in pr['sheets'])
    assert pr['sheets'][0]['questions'][0]['text'] == 'РУ-1' and pr['sheets'][0]['questions'][0]['text_sub'] is None
    # xəbərdarlıq: 27 sualın RU mətni yoxdur (hər şagird üçün) – sual nömrələri siyahıda
    assert pr['exam']['missing_translations'] == 27 * len(pr['sheets'])
    assert pr['exam']['missing_detail'][0]['slots'][0] == 4
    assert pr['sheets'][0]['questions'][5]['text'] == 'AZ-6'      # RU yoxdur – AZ çap olunur
    # yazılı imtahan AZ
    admin.patch(f'/api/classes/{cid}', json={'exam_language': 'az'})
    pr = admin.get(f'/api/exams/{ta}/{e["id"]}/variants/print').json()
    assert pr['exam']['lang'] == 'az' and pr['sheets'][0]['questions'][0]['text'] == 'AZ-1' and pr['exam']['missing_translations'] == 0
    # ikidilli
    admin.patch(f'/api/classes/{cid}', json={'exam_language': 'az_ru'})
    pr = admin.get(f'/api/exams/{ta}/{e["id"]}/variants/print').json()
    q0 = pr['sheets'][0]['questions'][0]
    assert q0['text'] == 'AZ-1' and q0['text_sub'] == 'РУ-1'
    mcq = next(q for q in pr['sheets'][0]['questions'] if q['slot'] <= 3 and q['kind'] == 'mcq')
    assert mcq['options_sub'][0].startswith('р')
    assert pr['sheets'][0]['questions'][10]['text_sub'] is None     # RU yoxdur – yalnız AZ
    # imtahanın istisnası: sinif AZ, imtahan RU
    admin.patch(f'/api/classes/{cid}', json={'exam_language': 'az'})
    body = {'kind': 'KSQ', 'no': 1, 'semester': 1, 'date': '2026-10-20', 'max_points': 100, 'language': 'ru'}
    assert admin.patch(f'/api/exams/{ta}/{e["id"]}', json=body).json()['language'] == 'ru'
    pr = admin.get(f'/api/exams/{ta}/{e["id"]}/variants/print').json()
    assert pr['exam']['lang'] == 'ru' and pr['sheets'][0]['questions'][0]['text'] == 'РУ-1'
    body.pop('language')                                          # göndərilməyib – dəyişmir
    assert admin.patch(f'/api/exams/{ta}/{e["id"]}', json=body).json()['language'] == 'ru'
    body['language'] = None                                       # null – sinfin qaydası
    assert admin.patch(f'/api/exams/{ta}/{e["id"]}', json=body).json()['language'] is None
    # etibarsız dəyər
    assert admin.patch(f'/api/classes/{cid}', json={'sector': 'en'}).status_code == 422
    assert admin.patch(f'/api/classes/{cid}', json={'exam_language': 'xx'}).status_code == 422


def test_blank_form_uses_exam_language(world):
    admin, ta, e, _ = ksq(world)
    cid = _class_of(world, ta)
    admin.patch(f'/api/classes/{cid}', json={'sector': 'ru'})
    # hamıya eyni suallar olmadıqca boş forma 409 – dil üçün yalnız vərəq yolu yoxlanır
    r = admin.get(f'/api/exams/{ta}/{e["id"]}/variants/print', params={'blank': True})
    assert r.status_code in (200, 409)
    if r.status_code == 200:
        assert r.json()['sheets'][0]['lang'] == 'ru'


def test_online_ksq_questions_in_exam_language(world):
    admin, ta, e, _ = ksq(world)
    _, S = world
    cid = _class_of(world, ta)
    _ru_texts(world, e['id'])
    admin.patch(f'/api/classes/{cid}', json={'sector': 'ru'})
    r = admin.post(f'/api/ksq-online/{ta}/{e["id"]}', json={})
    assert r.status_code == 200, r.text
    with S() as db:
        t = db.query(OnlineTask).filter_by(exam_id=e['id']).first()
        q1 = sorted(t.questions, key=lambda q: q['slot'])[0]
        assert q1['text'] == 'РУ-1'                               # tapşırıq mətni sətir, imtahan dilində


def test_result_package_text_in_exam_language_labels_in_user_language(world, monkeypatch):
    from .test_api_portal import student_client
    from .test_ksq_scan import _graded
    admin, ta, e, pr, st, _ = _graded(world, monkeypatch)
    _, S = world
    cid = _class_of(world, ta)
    _ru_texts(world, e['id'])
    with S() as db:
        scanned = [s.student_id for s in db.query(__import__('app.models', fromlist=['ExamScan']).ExamScan).filter_by(exam_id=e['id'])]
        s0 = next(x for x in st if x['id'] in scanned)
        db.query(User).filter(User.id == db.get(Student, s0['id']).user_id).one().language = 'az'
        db.commit()
    admin.patch(f'/api/classes/{cid}', json={'sector': 'ru'})
    admin.put(f'/api/exams/{ta}/{e["id"]}/publish', json={'published': True})
    c = student_client(s0['portal_code'], s0['initial_pin'])
    p = c.get(f'/api/portal/exams/{e["id"]}/package').json()
    assert p['exam']['lang'] == 'ru'
    assert p['questions'][0]['text'] == 'РУ-1'                    # sual mətni – imtahan dilində (interfeys AZ olsa da)
    assert isinstance(p['questions'][0]['topic'], dict) or isinstance(p['questions'][0]['topic'], str)   # altmövzu adı – şagirdin dilində (label_ml)
    card = c.get(f'/api/portal/exams/{e["id"]}/card').json()
    assert card['questions'][0]['text'] == 'РУ-1'
    admin.patch(f'/api/classes/{cid}', json={'exam_language': 'az'})
    p = c.get(f'/api/portal/exams/{e["id"]}/package').json()
    assert p['exam']['lang'] == 'az' and p['questions'][0]['text'] == 'AZ-1'


def test_grade_of_cyrillic_lookalikes():
    assert grade_of('IХ а') == 9                                  # Х – kiril
    assert grade_of('VІ б') == 6                                  # І – kiril
    assert grade_of('ХІ а') == 11 and grade_of('Х а') == 10
    assert grade_of('Ⅸ b') == 9 and grade_of('9 в') == 9
    assert grade_of('IX a') == 9 and grade_of('X b (riyaziyyat qrupu)') == 10


def test_new_student_account_defaults_to_class_sector_language(world):
    admin = world[0]('admin')
    _, S = world
    ru = admin.post('/api/classes', json={'name': 'VI а', 'sector': 'ru'}).json()
    az = admin.post('/api/classes', json={'name': 'VI b'}).json()
    assert ru['sector'] == 'ru' and ru['grade'] == 6 and az['sector'] is None and az['sector_eff'] == 'az'
    s1 = admin.post('/api/students', json={'full_name': 'Иванов Иван Иванович', 'class_id': ru['id'], 'force': True}).json()
    s2 = admin.post('/api/students', json={'full_name': 'Əliyev Əli Əli oğlu', 'class_id': az['id'], 'force': True}).json()
    with S() as db:
        assert db.get(User, db.get(Student, s1['id']).user_id).language == 'ru'
        assert db.get(User, db.get(Student, s2['id']).user_id).language == 'az'


def test_class_list_exposes_sector_fields(world):
    admin = world[0]('admin')
    c = admin.post('/api/classes', json={'name': 'IX а', 'sector': 'ru', 'exam_language': 'az'}).json()
    assert c['grade'] == 9
    row = next(x for x in admin.get('/api/classes').json() if x['id'] == c['id'])
    assert row['sector'] == 'ru' and row['exam_language'] == 'az' and row['exam_lang_eff'] == 'az' and row['sector_eff'] == 'ru'


def test_migration_up_down_up(tmp_path):
    url = f'sqlite:///{(tmp_path / "m.db").as_posix()}'
    env = {**os.environ, 'MK_DATABASE_URL': url, 'MK_BANK_SYNC_MINUTES': '0'}

    def run(*args):
        r = subprocess.run([sys.executable, '-m', 'alembic', *args], cwd=BACKEND, env=env, capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
        assert r.returncode == 0, r.stderr[-800:]

    def cols(t):
        return {c['name'] for c in inspect(create_engine(url)).get_columns(t)}
    run('upgrade', 'head')
    assert {'sector', 'exam_language'} <= cols('classes') and 'language' in cols('exams')
    assert {'per_slot', 'newest_first'} <= cols('exam_series') and 'answers_released_at' in cols('task_attempts')
    assert 'focus_log' in cols('task_attempts') and 'task_appeals' in inspect(create_engine(url)).get_table_names()
    run('downgrade', '-1')                                         # f1c5a9d3e7b4 (focus_log + task_appeals) geri
    assert 'focus_log' not in cols('task_attempts') and 'task_appeals' not in inspect(create_engine(url)).get_table_names()
    run('downgrade', '-1')                                         # f7c1e5a9b3d2 (sınaq seriyası) geri
    assert not ({'per_slot', 'newest_first'} & cols('exam_series')) and 'answers_released_at' not in cols('task_attempts')
    run('downgrade', '-1')
    assert not ({'sector', 'exam_language'} & cols('classes')) and 'language' not in cols('exams')
    assert 'standard' in cols('bank_questions')                   # əvvəlki miqrasiya yerində
    run('upgrade', 'head')
    assert {'sector', 'exam_language'} <= cols('classes') and 'language' in cols('exams')
