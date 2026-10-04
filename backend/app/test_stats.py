"""Test nəticələri mərkəzi: mövzu testləri və sınaqlar üzrə vahid nəticə sətirləri (docs/test-neticeleri-promtu.md §1).

- «Test» = vahid (unit): sınaqda – paket (TestBatch), mövzu testində – paket (bir neçə sinfə birdən) və ya tək tapşırıq.
  «Yenidən göndər» surəti (audit: copied_from) kökün vahidinə aiddir – şagird surəti yazıbsa, həmin testi yazmış sayılır.
- Şagirdin vahiddəki statusu: yazıb (son təhvil) > yazır > gözlənilir (test hələ bağlanmayıb) > yazmayıb.
- Faiz: sınaqda cərimə ilə (düz − səhv ÷ N), mövzu testində düz / ümumi.
- Görünmə: mövzu testi – yalnız müəllimin öz dərsləri; sınaq – exams_online._access (başqa siniflər adsız, yalnız yer üçün)."""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .domain.rules import rank, summative_grade
from .models import AuditLog, OnlineTask, PlanLesson, SchoolClass, TaskAttempt, TeachingAssignment, TestBatch, User, now
from .services import SCHOOL_TZ, roster, ws_cond

KINDS = ('movzu', 'sinaq')
LOW_PART = 0.5            # iştirak bundan azdırsa – «az iştirak» nişanı
CHRONIC_N, CHRONIC_SHARE = 3, 0.5   # xroniki yazmayan: ≥3 test və ya verilənlərin ≥50%-i (ən azı 2)
ATTENTION_PCT = 40.0


def _aware(t: dt.datetime) -> dt.datetime:
    return t.astimezone(dt.timezone.utc) if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def local_date(t: dt.datetime) -> dt.date:
    return _aware(t).astimezone(ZoneInfo(SCHOOL_TZ)).date()


def avg(v):
    v = [x for x in v if x is not None]
    return round(sum(v) / len(v), 1) if v else None


# ---------------------------------------------------------------- görünən tapşırıqlar
def _visible_tasks(db: Session, user: User | None, kind: str,
                   ta_ids: set[int] | None = None) -> tuple[list[OnlineTask], dict[int, bool]]:
    """(tapşırıqlar, {task_id: adlar görünürmü}). Sınaqda başqa müəllimin sinfi də (yer üçün) gəlir – adsız.
    user=None – şagird portalı üçün: yalnız verilən dərslərin mövzu testləri (adlar çağıran tərəfdə gizlədilir)."""
    if user is None:
        ts = list(db.scalars(select(OnlineTask).where(OnlineTask.kind == kind, OnlineTask.archived_at.is_(None),
                                                      OnlineTask.assignment_id.in_(ta_ids or set()))))
        return ts, {t.id: True for t in ts}
    if kind == 'movzu':
        ts = list(db.scalars(select(OnlineTask).join(TeachingAssignment, TeachingAssignment.id == OnlineTask.assignment_id)
                             .where(OnlineTask.kind == 'movzu', OnlineTask.archived_at.is_(None),
                                    TeachingAssignment.teacher_id == user.id, TeachingAssignment.archived_at.is_(None),
                                    ws_cond(user))))
        return ts, {t.id: True for t in ts}
    from .api.exams_online import _access
    out, vis, acc = [], {}, {}
    for t in db.scalars(select(OnlineTask).where(OnlineTask.kind == 'sinaq', OnlineTask.archived_at.is_(None),
                                                 OnlineTask.batch_id.is_not(None))):
        if t.batch_id not in acc:
            b = db.get(TestBatch, t.batch_id)
            try:
                acc[t.batch_id] = _access(db, user, b) if b else None
            except HTTPException:
                acc[t.batch_id] = None
        a = acc[t.batch_id]
        if a is None:
            continue
        ta = db.get(TeachingAssignment, t.assignment_id)
        out.append(t)
        vis[t.id] = a == 'full' or ta.teacher_id == user.id
    return out, vis


def _roots(db: Session, tasks: list[OnlineTask]) -> dict[int, int]:
    """task_id → kök tapşırıq (yenidən göndərmə zənciri audit jurnalından)."""
    if not tasks:
        return {}
    parent: dict[int, int] = {}
    for a in db.scalars(select(AuditLog).where(AuditLog.entity == 'task', AuditLog.action == 'create',
                                               AuditLog.entity_id.in_([str(t.id) for t in tasks]))):
        src = (a.details or {}).get('copied_from')
        if src:
            parent[int(a.entity_id)] = int(src)
    out = {}
    for t in tasks:
        cur, seen = t.id, set()
        while cur in parent and cur not in seen and len(seen) < 20:
            seen.add(cur)
            # kök audit jurnalında da surət ola bilər – onun da valideynini tapmaq üçün
            nxt = parent[cur]
            if nxt not in parent:
                a = db.scalar(select(AuditLog).where(AuditLog.entity == 'task', AuditLog.action == 'create',
                                                     AuditLog.entity_id == str(nxt)))
                if a and (a.details or {}).get('copied_from'):
                    parent[nxt] = int(a.details['copied_from'])
            cur = nxt
        out[t.id] = cur
    return out


# ---------------------------------------------------------------- toplama
def collect(db: Session, user: User | None, kind: str, ta_ids: set[int] | None = None,
            date_from: dt.date | None = None, date_to: dt.date | None = None, subject: str | None = None) -> dict:
    """{tests: [...], rows: [...]} – bir növ üzrə. rows: (şagird, test) cütü, yer sinifdə və ümumi."""
    from .api.tasks import expire_due, is_ok
    tasks, vis = _visible_tasks(db, user, kind, ta_ids)
    root = _roots(db, tasks)
    t0 = now()
    units: dict[str, dict] = {}
    for t in tasks:
        r = db.get(OnlineTask, root[t.id]) or t
        key = f'b{r.batch_id}' if r.batch_id else f't{r.id}'
        u = units.setdefault(key, {'unit': key, 'kind': kind, 'title': (db.get(TestBatch, r.batch_id).title
                                                                         if r.batch_id else r.title),
                                   'root': r, 'tasks': []})
        u['tasks'].append(t)
    tests, rows = [], []
    rosters: dict[int, list] = {}
    for key, u in units.items():
        r = u['root']
        penalty = (db.get(TestBatch, r.batch_id).penalty if r.batch_id else 0) if kind == 'sinaq' else 0
        rta = db.get(TeachingAssignment, r.assignment_id)
        if subject and (rta.subject if rta else None) != subject:
            continue
        pl = db.get(PlanLesson, r.plan_lesson_id) if r.plan_lesson_id else None
        d = min(local_date(t.opens_at) for t in u['tasks'])
        if (date_from and d < date_from) or (date_to and d > date_to):
            continue
        per: dict[int, dict] = {}
        tas = set()
        for t in sorted(u['tasks'], key=lambda x: _aware(x.opens_at)):
            expire_due(db, t)
            ta = db.get(TeachingAssignment, t.assignment_id)
            if ta_ids is not None and ta.id not in ta_ids:
                continue
            tas.add(ta.id)
            if ta.id not in rosters:
                rosters[ta.id] = roster(db, ta)
            cls = db.get(SchoolClass, ta.class_id)
            closed = t0 >= _aware(t.closes_at)
            atts = {a.student_id: a for a in db.scalars(select(TaskAttempt).where(TaskAttempt.task_id == t.id))}
            for s in rosters[ta.id]:
                if t.student_ids is not None and s.id not in t.student_ids:
                    continue
                a = atts.get(s.id)
                p = per.setdefault(s.id, {'student_id': s.id, 'full_name': s.full_name, 'class_name': cls.name,
                                          'ta_id': ta.id, 'teacher_id': ta.teacher_id, 'unit': key, 'kind': kind,
                                          'title': u['title'], 'date': d, 'topic': pl and pl.topic,
                                          'status': None, 'pct': None, 'grade': None, 'task_id': t.id,
                                          'visible': vis[t.id], 'submitted_at': None})
                p['visible'] = p['visible'] or vis[t.id]
                if a and a.submitted_at and a.total:
                    n = len(t.questions)
                    ok = sum(is_ok(t, a, i) for i in range(n))
                    blank = sum(1 for i in range(n) if (a.answers or {}).get(str(i)) in (None, ''))
                    pts = ok - ((n - ok - blank) / penalty if penalty else 0)
                    pct = round(max(0.0, pts) * 100 / n, 1)
                    if p['status'] != 'yazıb' or _aware(a.submitted_at) >= p['submitted_at']:
                        p.update(status='yazıb', pct=pct, grade=summative_grade(pct), task_id=t.id,
                                 submitted_at=_aware(a.submitted_at))
                elif p['status'] != 'yazıb':
                    st = 'yazır' if a and not closed else 'gözlənilir' if not closed else 'yazmayıb'
                    order = ['yazmayıb', 'gözlənilir', 'yazır']
                    if p['status'] is None or order.index(st) >= order.index(p['status']):
                        p.update(status=st, task_id=t.id)
        if not per:
            continue
        rs = list(per.values())
        for k, _, place in rank([(str(i), x['pct']) for i, x in enumerate(rs) if x['status'] == 'yazıb']):
            rs[int(k)]['place_all'] = place
        for ta_id in tas:
            idx = [i for i, x in enumerate(rs) if x['ta_id'] == ta_id and x['status'] == 'yazıb']
            for k, _, place in rank([(str(i), rs[i]['pct']) for i in idx]):
                rs[int(k)]['place_class'] = place
        for x in rs:
            x.setdefault('place_all', None)
            x.setdefault('place_class', None)
            x['submitted_at'] = None if x['submitted_at'] is None else x['submitted_at'].isoformat()
        wrote = [x['pct'] for x in rs if x['status'] == 'yazıb']
        given = [x for x in rs if x['status'] in ('yazıb', 'yazmayıb')]
        tests.append({'unit': key, 'kind': kind, 'title': u['title'], 'date': d, 'topic': pl and pl.topic,
                      'subject': rta.subject if rta else None,
                      'closed': all(t0 >= _aware(t.closes_at) for t in u['tasks']),
                      'students': len(rs), 'given': len(given), 'wrote': len(wrote), 'avg_pct': avg(wrote),
                      'missed': sum(1 for x in rs if x['status'] == 'yazmayıb'), 'ta_ids': sorted(tas)})
        rows.extend(rs)
    tests.sort(key=lambda x: (x['date'], x['title']))
    return {'tests': tests, 'rows': rows}


def per_student(rows: list[dict]) -> dict[int, dict]:
    """Şagird üzrə yığım (bir növ): verilən, yazdığı, orta, son, dinamika, iştirak."""
    out: dict[int, dict] = {}
    for r in sorted(rows, key=lambda x: (x['date'], x['title'])):
        p = out.setdefault(r['student_id'], {'student_id': r['student_id'], 'full_name': r['full_name'],
                                             'class_name': r['class_name'], 'ta_id': r['ta_id'], 'visible': False,
                                             'series': [], 'given': 0, 'wrote': 0, 'missed': 0})
        p['visible'] |= r['visible']
        if r['status'] in ('yazıb', 'yazmayıb'):
            p['given'] += 1
        if r['status'] == 'yazmayıb':
            p['missed'] += 1
        if r['status'] == 'yazıb':
            p['wrote'] += 1
            p['series'].append(r['pct'])
    for p in out.values():
        s = p['series']
        p.update(avg_pct=avg(s), last_pct=s[-1] if s else None,
                 delta=round(s[-1] - s[-2], 1) if len(s) >= 2 else None,
                 participation=round(p['wrote'] * 100 / p['given'], 1) if p['given'] else None)
        p['low_participation'] = bool(p['given'] >= 2 and p['wrote'] / p['given'] < LOW_PART)
        p['attention'] = bool((p['avg_pct'] is not None and p['avg_pct'] < ATTENTION_PCT)
                              or (len(s) >= 2 and s[-1] < s[-2] - 10))
        p['chronic'] = bool(p['missed'] >= CHRONIC_N or (p['given'] >= 2 and p['missed'] / p['given'] >= CHRONIC_SHARE))
    return out


def rating(data: dict) -> dict:
    """Kumulyativ reytinq (bir növ): şagirdlər (sinifdə və ümumi yer), siniflər, irəliləyənlər, diqqət tələb edənlər."""
    ps = list(per_student(data['rows']).values())
    for k, _, place in rank([(str(i), p['avg_pct']) for i, p in enumerate(ps)]):
        ps[int(k)]['place_all'] = place
    for cname in {p['class_name'] for p in ps}:
        idx = [i for i, p in enumerate(ps) if p['class_name'] == cname]
        for k, _, place in rank([(str(i), ps[i]['avg_pct']) for i in idx]):
            ps[int(k)]['place_class'] = place
    classes: dict[str, dict] = {}
    for r in data['rows']:
        c = classes.setdefault(r['class_name'], {'class_name': r['class_name'], 'pcts': [], 'given': 0, 'wrote': 0})
        if r['status'] in ('yazıb', 'yazmayıb'):
            c['given'] += 1
        if r['status'] == 'yazıb':
            c['wrote'] += 1
            c['pcts'].append(r['pct'])
    cl = [{'class_name': c['class_name'], 'avg_pct': avg(c['pcts']), 'wrote': c['wrote'], 'given': c['given'],
           'participation': round(c['wrote'] * 100 / c['given'], 1) if c['given'] else None} for c in classes.values()]
    for k, _, place in rank([(str(i), c['avg_pct']) for i, c in enumerate(cl)]):
        cl[int(k)]['place'] = place
    cl.sort(key=lambda c: (c['place'] is None, c['place'] or 0))
    total = len(ps)
    rows = []
    for p in ps:
        p.setdefault('place_all', None)
        p.setdefault('place_class', None)
        if p.pop('visible'):
            p.pop('series')
            rows.append(p)
    rows.sort(key=lambda r: (r['place_all'] is None, r['place_all'] or 0, r['full_name']))
    improved = sorted([r for r in rows if r['delta'] is not None and r['delta'] > 0], key=lambda r: -r['delta'])[:10]
    attention = [r for r in rows if r['attention']]
    return {'tests': data['tests'], 'rows': rows, 'total': total, 'classes': cl, 'improved': improved,
            'attention': attention}


def missing(datas: list[dict]) -> dict:
    """Yazmayanlar (yalnız bağlanmış testlər, adı görünən şagirdlər)."""
    st: dict[int, dict] = {}
    tests: dict[str, dict] = {}
    for data in datas:
        for r in data['rows']:
            if not r['visible'] or r['status'] not in ('yazıb', 'yazmayıb'):
                continue
            p = st.setdefault(r['student_id'], {'student_id': r['student_id'], 'full_name': r['full_name'],
                                                'class_name': r['class_name'], 'given': 0, 'missed': 0, 'tests': []})
            p['given'] += 1
            t = tests.setdefault(r['unit'], {'unit': r['unit'], 'kind': r['kind'], 'title': r['title'], 'date': r['date'],
                                             'topic': r['topic'], 'given': 0, 'missed': 0})
            t['given'] += 1
            if r['status'] == 'yazmayıb':
                p['missed'] += 1
                t['missed'] += 1
                p['tests'].append({'unit': r['unit'], 'kind': r['kind'], 'title': r['title'], 'date': r['date'],
                                   'topic': r['topic'], 'task_id': r['task_id'], 'ta_id': r['ta_id']})
    students = []
    for p in st.values():
        if not p['missed']:
            continue
        p['tests'].sort(key=lambda x: x['date'])
        p['last_missed'] = p['tests'][-1]['date']
        p['chronic'] = bool(p['missed'] >= CHRONIC_N or (p['given'] >= 2 and p['missed'] / p['given'] >= CHRONIC_SHARE))
        students.append(p)
    students.sort(key=lambda p: (-p['missed'], p['class_name'], p['full_name']))
    return {'students': students, 'tests': sorted([t for t in tests.values() if t['missed']],
                                                  key=lambda t: (t['date'], t['title']), reverse=True)}
