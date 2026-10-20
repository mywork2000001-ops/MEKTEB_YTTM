"""Video bələdçi üçün ZƏNGİN DEMO məlumat (yalnız müvəqqəti SQLite bazasında; real ad YOXDUR).

Mümkün olduqda tətbiqin öz API-ları ilə yaradılır (müəllim kimi giriş); API-sı olmayan hissələr (test bankı faylları,
KSQ variantı/skanı) birbaşa bazaya yazılır. guide_videos.py bunu server qalxandan sonra çağırır: seed(demo).

Yaranan: X e (X sinif, perspektiv plan proqramı ilə, keçmiş dərslər, plan testləri, mövzu testləri/sınaq nəticələri, KSQ-1 + nəticə
paketi, jurnal qiymət/davamiyyət) · IX a (səviyyə: Zəif/Orta/Güclü) · məşğələ qrupları: «inkişaf» (IX Zəif) və «tərəqqi» (X Güclü).
"""
from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parents[1]
UTC = dt.timezone.utc
N10 = ['Şagird Bir', 'Şagird İki', 'Şagird Üç', 'Şagird Dörd', 'Şagird Beş', 'Şagird Altı']
N9 = ['Şagird Yeddi', 'Şagird Səkkiz', 'Şagird Doqquz', 'Şagird On', 'Şagird On Bir']
TOPICS = ['Kvadrat tənliklər', 'Bərabərsizliklər', 'Funksiyalar', 'Ardıcıllıqlar', 'Triqonometriya', 'Törəmə', 'Çoxhədlilər', 'Loqarifm']


def ok(r: httpx.Response, what: str):
    if r.status_code >= 400:
        raise RuntimeError(f'{what}: {r.status_code} {r.text[:300]}')
    return r.json() if r.content else None


def login(base: str, login_: str, pw: str) -> httpx.Client:
    c = httpx.Client(base_url=base, timeout=60)
    ok(c.post('/api/auth/login', json={'login': login_, 'password': pw}), f'giriş {login_}')
    return c


def take(base: str, login_: str, pin: str, task_id: int, right: int):
    """Şagird testi işləyir: ilk `right` suala düzgün (variant 0 / açıq «7»), qalanına səhv cavab; təhvil verir."""
    s = login(base, login_, pin)
    q = ok(s.post(f'/api/portal/tasks/{task_id}/start'), f'start {task_id}')['questions']
    ans = {}
    for k, x in enumerate(q):
        good = k < right
        ans[str(x['index'])] = (0 if good else 1) if x['kind'] == 'mcq' else ('7' if good else '0')
    ok(s.post(f'/api/portal/tasks/{task_id}/submit', json={'answers': ans}), f'submit {task_id}')
    s.close()


def seed(demo) -> None:
    from guide_videos import TEACHER                                          # noqa: PLC0415
    os.environ.update(demo.env)
    sys.path.insert(0, str(BACKEND))
    base = demo.base
    now = dt.datetime.now(UTC)
    today = dt.date.today()
    c = login(base, TEACHER['login'], TEACHER['password'])

    # ---------------------------------------------------------------- proqramlar, siniflər, şagirdlər
    progs = {p.get('key'): p for p in ok(c.get('/api/programs'), 'proqramlar')}
    p10, p9 = progs['dim-sinif-testleri-10'], progs['dim-sinif-testleri-9']
    cid10 = ok(c.post('/api/classes', json={'name': 'X e'}), 'sinif X e')['id']
    cid9 = ok(c.post('/api/classes', json={'name': 'IX a'}), 'sinif IX a')['id']
    j10 = ok(c.post(f'/api/classes/{cid10}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 3, 'slots': {'0': [2], '2': [3], '4': [1]},
                                                       'program_id': p10['id']}), 'join X e')
    j9 = ok(c.post(f'/api/classes/{cid9}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 2, 'slots': {'1': [2], '3': [3]},
                                                     'program_id': p9['id']}), 'join IX a')
    ta10, ta9 = j10['mine']['ta_id'], j9['mine']['ta_id']
    st10, st9 = [], []
    for names, cid, out in ((N10, cid10, st10), (N9, cid9, st9)):
        for n in names:
            j = ok(c.post('/api/students', json={'full_name': n, 'class_id': cid, 'force': True}), f'şagird {n}')
            demo.student_pins[j['portal_code']] = j['initial_pin']
            out.append(j)
    demo.first_student = st10[0]['portal_code']
    pin = lambda s: demo.student_pins[s['portal_code']]                       # noqa: E731

    # səviyyələr: IX a – 3 Zəif; X e – 3 Güclü (məşğələ qrupları üçün)
    for s, lv in zip(st9, ['Zəif', 'Zəif', 'Zəif', 'Orta', 'Güclü']):
        ok(c.put(f'/api/levels/{ta9}/{s["id"]}', json={'level': lv, 'locked': True}), 'səviyyə')
    for s, lv in zip(st10, ['Güclü', 'Güclü', 'Güclü', 'Orta', 'Orta', 'Zəif']):
        ok(c.put(f'/api/levels/{ta10}/{s["id"]}', json={'level': lv, 'locked': True}), 'səviyyə')

    # ---------------------------------------------------------------- test bankı + plan dərslərinə bağlantı (birbaşa baza)
    from app.db import SessionLocal                                           # noqa: PLC0415
    from app.models import BankFile, BankQuestion, BankSource, LessonBankLink, PlanLesson
    with SessionLocal() as db:
        db.add(BankSource(key='p0010', label='P0010 (demo)'))
        lessons = list(db.query(PlanLesson).filter(PlanLesson.assignment_id == ta10, PlanLesson.assessment_type == 'formativ')
                       .order_by(PlanLesson.seq))
        ksq_date = db.query(PlanLesson.date).filter(PlanLesson.assignment_id == ta10, PlanLesson.assessment_type == 'KSQ').order_by(PlanLesson.seq).first()[0]
        files = []
        for k in range(8):                                                    # 8 test faylı; plan dərsləri onlara dövrə ilə bağlanır
            f = BankFile(source_key='p0010', lesson=f'demo-{k + 1}.html', label=f'Mövzu {k + 1} – test', url=f'http://demo/{k + 1}.html',
                         question_count=6, kind='movzu', grades=[10], subject='Riyaziyyat')
            db.add(f)
            db.flush()
            for n in range(1, 7):
                db.add(BankQuestion(file_id=f.id, n=n, kind='mcq', text={'az': f'Mövzu {k + 1}, sual {n}: {n} + {n} = ?'},
                                    options=[{'az': str(2 * n)}, {'az': str(2 * n + 1)}, {'az': str(2 * n - 1)}, {'az': str(n)}], correct=0,
                                    explanation={'az': f'{n} + {n} = {2 * n}.'}, content_hash=f'demo-{k}-{n}'))
            files.append(f.id)
        for i, pl in enumerate(lessons):
            db.add(LessonBankLink(plan_lesson_id=pl.id, file_id=files[i % 8]))
        db.commit()

    # keçmiş dərslərin mövzu testləri (plan testləri mühərriki, çatışanlar rejimi) – gələcək dərslərin testləri təyin edilməmiş qalır
    y0 = today - dt.timedelta(days=40)
    rep = ok(c.post('/api/plan-tests/assign', json={'ta_ids': [ta10], 'date_from': y0.isoformat(), 'date_to': today.isoformat(),
                                                   'opts': {'missing': True, 'n_questions': 6}}), 'plan testləri')
    import json                                                               # noqa: PLC0415
    print('  plan testləri:', json.dumps(rep, ensure_ascii=False, default=str)[:1800])

    # ---------------------------------------------------------------- əlavə mövzu testi (müddətsiz) + vaxtlı test + sınaq
    custom = [{'kind': 'mcq', 'text': 'x² − 9 = 0 tənliyinin kökləri hansılardır?', 'options': ['±3', '3', '9', '−3'], 'correct': 0,
               'explanation': 'x² = 9, deməli x = 3 və ya x = −3.'},
              {'kind': 'mcq', 'text': '2 + 2 · 2 = ?', 'options': ['6', '8', '4', '10'], 'correct': 0,
               'explanation': 'Əvvəl vurma: 2 · 2 = 4, sonra 2 + 4 = 6.'},
              {'kind': 'open', 'text': 'x + 5 = 12 tənliyində x = ?', 'answer': '7'}]
    untimed = ok(c.post(f'/api/tasks/{ta10}', json={'title': 'Kvadrat tənliklər – mövzu testi', 'opens_at': (now - dt.timedelta(hours=2)).isoformat(),
                                                    'shuffle': False, 'custom': custom}), 'müddətsiz test')
    ok(c.post(f'/api/tasks/{ta10}', json={'title': 'Tənliklər – vaxtlı test', 'opens_at': (now - dt.timedelta(hours=2)).isoformat(),
                                          'closes_at': (now + dt.timedelta(days=7)).isoformat(), 'duration_min': 40, 'shuffle': False,
                                          'custom': custom}), 'vaxtlı test')
    sq = ok(c.post('/api/exams-online', json={'title': 'Sınaq 1 – Cəbr', 'duration_min': 0, 'shuffle': False, 'custom': custom * 2,
                                              'allow_repeat': True, 'allow_other_grade': True,
                                              'targets': [{'ta_id': ta10, 'opens_at': (now - dt.timedelta(hours=2)).isoformat()}]}), 'sınaq')

    import sqlalchemy as sa                                                   # noqa: PLC0415
    with SessionLocal() as db:                                                # əlavə testlər «Mövzu testləri» bölməsində görünsün
        db.execute(sa.text("UPDATE online_tasks SET kind='movzu' WHERE title IN ('Kvadrat tənliklər – mövzu testi', 'Tənliklər – vaxtlı test')"))
        db.commit()
    # şagirdlər bu testləri işləyir: hamı hamısını yox – 5 və 6-cı şagird heç nə işləməyib
    import sqlalchemy as sa                                                   # noqa: PLC0415
    with SessionLocal() as db:
        tasks = [dict(r._mapping) for r in db.execute(sa.text('SELECT id, title, kind, questions FROM online_tasks ORDER BY id'))]
    done = {  # şagird indeksi -> {tapşırıq başlığının hissəsi: düzgün sayı}
        0: {'*plan': 5, 'Sınaq': 5}, 1: {'*plan': 4, 'Sınaq': 3}, 2: {'*plan': 3}, 3: {'*plan': 2, 'Sınaq': 6}, 4: {}, 5: {}}
    plan_ids = [r['task_id'] for r in rep['rows'] if r.get('task_id')]
    plan_tasks = [t for t in tasks if t['id'] in plan_ids]
    for i, rules in done.items():
        for k, t in enumerate(plan_tasks):
            r = rules.get('*plan')
            if r is not None and not (i == 2 and k == 1):
                take(base, st10[i]['portal_code'], pin(st10[i]), t['id'], max(0, r - k))
        for t in tasks:
            if t['title'].startswith('Sınaq') and 'Sınaq' in rules:
                take(base, st10[i]['portal_code'], pin(st10[i]), t['id'], rules['Sınaq'])
    # 1-ci şagird: bir mövzu testini (müddətsiz) hələ işləməyib → «işləməli olduğun testlər» görünür
    print('  tapşırıqlar:', len(tasks), 'plan:', len(plan_tasks), 'sınaq id:', sq if not isinstance(sq, dict) else list(sq)[:3])

    # ---------------------------------------------------------------- jurnal: davamiyyət və qiymətlər
    wd = {0: 2, 2: 3, 4: 1}                                                   # cədvəl: bazar ertəsi 2, çərşənbə 3, cümə 1-ci saat
    days = [today - dt.timedelta(days=d) for d in range(1, 24)]
    ent = [(x, wd[x.weekday()]) for x in days if x.weekday() in wd and x != ksq_date][:7]
    for k, (d, p) in enumerate(ent):
        att = {s['id']: ('yox' if (k + i) % 7 == 0 else 'gecikdi' if (k + i) % 5 == 0 else 'var') for i, s in enumerate(st10)}
        marks = [{'student_id': s['id'], 'kind': 'şifahi', 'grade': 3 + (k + i) % 3} for i, s in enumerate(st10)
                 if (k + i) % 2 == 0 and att[s['id']] == 'var']
        r = c.put(f'/api/journal/{ta10}/entry', json={'date': d.isoformat(), 'period': p, 'homework': 'Dərslik, səh. 45–46',
                                                      'attendance': {str(a): b for a, b in att.items()}, 'marks': marks})
        if r.status_code >= 400:
            print('  jurnal xəbərdarlıq:', d, p, r.status_code, r.text[:120])

    # ---------------------------------------------------------------- KSQ-1: bal, variant, skan, nəticə paketi
    items = [{'n': i, 'points': 5} for i in range(1, 7)]
    ex = ok(c.post(f'/api/exams/{ta10}', json={'kind': 'KSQ', 'no': 1, 'semester': 1, 'date': ksq_date.isoformat(),
                                               'items': items, 'send_on_scan': False}), 'KSQ-1')
    from app.models import ExamScan, ExamVariant                              # noqa: PLC0415
    with SessionLocal() as db:
        for si, s in enumerate(st10):
            qs = [{'slot': n, 'key': 'A', 'kind': 'mcq', 'level': 'orta', 'points': 5, 'topic': TOPICS[n - 1], 'text': f'{n}-ci tapşırıq: {n} + {n} = ?',
                   'options': [{'az': str(2 * n)}, {'az': str(2 * n + 1)}, {'az': str(2 * n - 1)}, {'az': str(n)}], 'correct': 0, 'bank_id': None}
                  for n in range(1, 7)]
            db.add(ExamVariant(exam_id=ex['id'], student_id=s['id'], code=f'KSQ1-{si + 1:03d}', questions=qs))
            if si in (5,):                                                    # bir şagird yazmayıb
                continue
            marks = [1 if (n + si) % 3 else 0 for n in range(1, 7)]
            read = [{'slot': n, 'value': 'A' if m else 'B', 'confidence': 1.0} for n, m in zip(range(1, 7), marks)]
            db.add(ExamScan(exam_id=ex['id'], student_id=s['id'], code=f'KSQ1-{si + 1:03d}', status='graded', reading=read, read_by='teacher',
                            marks=marks, points=float(sum(marks) * 5), source='paper'))
        db.commit()
    scores = []
    for si, s in enumerate(st10):
        if si == 5:
            scores.append({'student_id': s['id'], 'absent': True})
        else:
            m = sum(1 if (n + si) % 3 else 0 for n in range(1, 7))
            scores.append({'student_id': s['id'], 'points': float(m * 5)})
    ok(c.put(f'/api/exams/{ta10}/{ex["id"]}/scores', json=scores), 'KSQ balları')
    ok(c.put(f'/api/exams/{ta10}/{ex["id"]}/publish', json={'published': True, 'appeal_days': 7}), 'KSQ göndər')

    # ---------------------------------------------------------------- məşğələ qrupları
    start = (today - dt.timedelta(days=14)).isoformat()
    end = (today + dt.timedelta(days=60)).isoformat()
    ok(c.post('/api/extra', json={'title': 'IX – inkişaf qrupu (Zəif)', 'format': 'əyani', 'ta_ids': [ta9], 'levels': ['Zəif'], 'kind': 'inkisaf',
                                  'schedule': [{'weekday': 5, 'start': '10:00', 'end': '11:30', 'room': '12'}], 'starts_on': start, 'ends_on': end,
                                  'goal': 'Zəif səviyyəli şagirdlərin əsas biliklərini möhkəmləndirmək'}), 'inkişaf qrupu')
    ok(c.post('/api/extra', json={'title': 'X – tərəqqi qrupu (Güclü)', 'format': 'əyani', 'ta_ids': [ta10], 'levels': ['Güclü'], 'kind': 'tereqqi',
                                  'schedule': [{'weekday': 5, 'start': '12:00', 'end': '13:30', 'room': '12'}], 'starts_on': start, 'ends_on': end,
                                  'goal': 'Güclü şagirdlər üçün dərinləşdirilmiş mövzular'}), 'tərəqqi qrupu')
    demo.ids = {'ta10': ta10, 'ta9': ta9, 'exam': ex['id']}
    c.close()
