"""Dərs sayı və müvəffəqiyyət (успеваемость).

Dərs sayı (bir dərs bağlılığı üzrə): plandakı dərslər, cədvələ görə bu günə qədər keçilməli olanlar, jurnalda
yazılanlar, yazılmamış dərslər (tarix + saat), plan üzrə keçilən / qalan mövzular, geriləmə, ilə sığmayanlar.

Müvəffəqiyyət (məktəb hesabatındakı kimi):
- şagirdin fənn qiyməti = yarımil qiyməti (KSQ×0,4 + BSQ×0,6) varsa o, yoxdursa formativ qiymətlərin ortası
  (adi yuvarlaqlaşdırma) – mənbə ayrıca göstərilir;
- müvəffəqiyyət % = «2» almayanlar / qiymətləndirilənlər × 100;
- keyfiyyət %     = «4» və «5» alanlar / qiymətləndirilənlər × 100;
- təlim səviyyəsi (SOU) = (100·n5 + 64·n4 + 36·n3 + 16·n2) / n;
- qiyməti olmayan şagirdlər hesabdan çıxır və ayrıca sayılır; yarımil qiyməti yoxdursa və formativ qiymət
  MIN_MARKS-dan azdırsa – «az qiymət» (qiymətləndirilməyib), ilin əvvəlində tək testdən faiz çıxmasın."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from .domain.rules import grade_from_points, round_half_up, semester_grade
from .models import Exam, ExamScore, JournalEntry, Mark
from .services import PlanCtx, roster

SOU_W = {5: 100, 4: 64, 3: 36, 2: 16}
MIN_MARKS = 3        # yarımil qiyməti yoxdursa, formativ ortadan fənn qiyməti ən azı bu qədər qiymətlə çıxarılır


def sem_range(ctx: PlanCtx, sem: int | None) -> tuple[dt.date, dt.date]:
    y = ctx.year
    return {1: (y.start, y.sem1_end), 2: (y.sem2_start, y.end)}.get(sem, (y.start, y.end))


def lesson_counts(db: Session, ctx: PlanCtx, today: dt.date, sem: int | None = None) -> dict:
    a, b = sem_range(ctx, sem)
    slots = [s for s in ctx.slots if a <= s.date <= b]
    due = [s for s in slots if s.date <= today]
    written = {(e.date, e.period) for e in db.scalars(select(JournalEntry).where(
        JournalEntry.assignment_id == ctx.ta.id, JournalEntry.date >= a, JournalEntry.date <= b,
        JournalEntry.auto.is_(False)))}                   # yalnız onlayn test qiyməti olan dərs yazılmış sayılmır
    missing = [s for s in due if (s.date, s.period) not in written]
    plan = [pl for pl in ctx.lessons if sem is None or pl.semester == sem]
    seqs = {pl.id for pl in plan}
    covered = {ctx.lessons[s.index].id for s in due if s.index is not None} & seqs
    # perspektiv planla uyğunluq: «saxla» olmayan yuvada tarix plandakı tarixlə eyni olmalıdır
    mism = [(s, ctx.lessons[s.index]) for s in slots if s.index is not None and s.shift == 0
            and ctx.lessons[s.index].date != s.date]
    cur = next((s for s in ctx.slots if s.date >= today), None)
    last = ctx.slots[-1] if ctx.slots else None
    return {
        'semester': sem, 'from': a, 'to': b, 'weekly_hours': ctx.ta.weekly_hours,
        'plan_total': len(plan),                              # perspektiv planda dərs
        'timetable_total': len(slots),                        # cədvələ görə bu dövrdə dərs saatı
        'due': len(due),                                      # bu günə qədər keçilməli idi
        'written': len([k for k in written if k[0] <= today]),   # jurnalda yazılıb
        'missing': len(missing),                              # yazılmamış dərslər
        'missing_list': [{'date': s.date, 'period': s.period} for s in missing[-30:]],
        'covered': len(covered),                              # plan üzrə keçilən mövzu
        'remaining': len(plan) - len(covered),                # qalan mövzu
        'held': sum(s.held for s in due),                     # «Mövzunu saxla»
        'lag': (cur or last).shift if (cur or last) else 0,   # geriləmə (dərs)
        'unfit': len(ctx.unfit) if sem is None else sum(ctx.lessons[i].semester == sem for i in ctx.unfit),
        'date_mismatch': len(mism),                           # cədvəl plandan fərqlənir (0 olmalıdır)
        'mismatch_list': [{'seq': pl.seq, 'plan_date': pl.date, 'date': s.date, 'period': s.period}
                          for s, pl in mism[:10]],
        'ksq': sum(pl.assessment_type == 'KSQ' for pl in plan),
        'bsq': len({pl.exam_no for pl in plan if pl.assessment_type == 'BSQ'}),
    }


def semester_grades(db: Session, ta_id: int, sem: int, sids: list[int]) -> dict[int, dict]:
    """{sid: {'ksq': [...], 'bsq': g, 'semester_grade': g}} – exams.semester ilə eyni qayda."""
    exams = list(db.scalars(select(Exam).where(Exam.assignment_id == ta_id, Exam.semester == sem)
                            .order_by(Exam.kind.desc(), Exam.no)))
    scores = {(sc.exam_id, sc.student_id): sc for sc in db.scalars(
        select(ExamScore).where(ExamScore.exam_id.in_([e.id for e in exams])))}

    def g(e, sid):
        sc = scores.get((e.id, sid))
        return None if not sc or sc.absent or sc.points is None else grade_from_points(sc.points, e.max_points)
    out = {}
    for sid in sids:
        ksq = [x for x in (g(e, sid) for e in exams if e.kind == 'KSQ') if x is not None]
        bsq = next((g(e, sid) for e in exams if e.kind == 'BSQ'), None)
        out[sid] = {'ksq': ksq, 'bsq': bsq, 'semester_grade': semester_grade(ksq, bsq)}
    return out


def subject_grades(db: Session, ctx: PlanCtx, sem: int | None, sids: list[int] | None = None) -> dict[int, dict]:
    """Şagirdin bu fənn üzrə qiyməti: yarımil qiyməti, yoxdursa formativ orta (yuvarlaqlaşdırılmış)."""
    if sids is None:
        sids = [s.id for s in roster(db, ctx.ta)]
    a, b = sem_range(ctx, sem)
    marks: dict[int, list[int]] = {}
    for m in db.scalars(select(Mark).join(JournalEntry, JournalEntry.id == Mark.entry_id).where(
            JournalEntry.assignment_id == ctx.ta.id, JournalEntry.date >= a, JournalEntry.date <= b)):
        marks.setdefault(m.student_id, []).append(m.grade)
    sg = {}
    if sem in (1, 2):
        sg = semester_grades(db, ctx.ta.id, sem, sids)
    else:                                          # bütün il: iki yarımil qiymətinin ortası
        s1, s2 = semester_grades(db, ctx.ta.id, 1, sids), semester_grades(db, ctx.ta.id, 2, sids)
        for sid in sids:
            v = [x for x in (s1[sid]['semester_grade'], s2[sid]['semester_grade']) if x is not None]
            sg[sid] = {'semester_grade': round_half_up(sum(v) / len(v)) if v else None}
    out = {}
    for sid in sids:
        f = marks.get(sid, [])
        favg = round(sum(f) / len(f), 2) if f else None
        sem_g = sg.get(sid, {}).get('semester_grade')
        few = sem_g is None and 0 < len(f) < MIN_MARKS
        grade, src = (sem_g, 'yarımil') if sem_g is not None else \
            (None, 'az qiymət') if few else \
            (max(2, min(5, round_half_up(favg))), 'formativ') if favg is not None else (None, None)
        out[sid] = {'grade': grade, 'source': src, 'formative_avg': favg, 'marks': len(f), 'semester_grade': sem_g,
                    'few_marks': few}
    return out


def metrics(grades: list[int | None]) -> dict:
    g = [x for x in grades if x is not None]
    n = len(g)
    dist = {k: g.count(k) for k in (5, 4, 3, 2)}
    pct = (lambda v: round(v * 100 / n, 1)) if n else (lambda v: None)
    return {'students': len(grades), 'graded': n, 'not_graded': len(grades) - n, 'distribution': dist,
            'avg': round(sum(g) / n, 2) if n else None,
            'success_pct': pct(n - dist[2]), 'quality_pct': pct(dist[5] + dist[4]),
            'sou': round(sum(SOU_W[k] * v for k, v in dist.items()) / n, 1) if n else None}


def category(grades: list[int | None]) -> str | None:
    """Bütün fənlər üzrə: əlaçı / zərbəçi / bir «3»-lü / «3»-lü / geridə qalan."""
    g = [x for x in grades if x is not None]
    if not g:
        return None
    if 2 in g:
        return 'Geridə qalan'
    if all(x == 5 for x in g):
        return 'Əlaçı'
    if all(x >= 4 for x in g):
        return 'Zərbəçi'
    return 'Bir «3»-lü' if g.count(3) == 1 else '«3»-lü'


CATEGORIES = ['Əlaçı', 'Zərbəçi', 'Bir «3»-lü', '«3»-lü', 'Geridə qalan']
