"""Mövzu icrası: perspektiv plana nisbətən FAKTİKİ irəliləyiş / geriləmə.

Mövzunun statusu (mənbə ierarxiyası):
1. müəllimin əl ilə qeydi (`TopicProgress`): keçildi | təkrar | qismən;
2. yoxdursa – jurnal: mövzu jurnalda yazılıbsa (`JournalEntry.plan_lesson_id`) «keçildi» (tarix – son yazılış);
3. yoxdursa – rəsmi tarixi keçibsə «gecikir», keçməyibsə «gözlənilir».

Sayılan (icra olunmuş) = keçildi + təkrar; qismən ayrıca göstərilir, sayılmır.
Fərq = sayılan − rəsmi tarixi bu günə qədər olan mövzular (mənfi – geriləmə, müsbət – irəliləmə).
Proqnoz: qalan mövzular cədvəl üzrə ilin sonuna qədər qalan dərs saatlarına sığırmı; son 4 həftənin tempi."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import JournalEntry, TopicProgress
from .services import PlanCtx

STATUSES = ('keçildi', 'təkrar', 'qismən')
DONE = ('keçildi', 'təkrar')


def _monday(d: dt.date) -> dt.date:
    return d - dt.timedelta(days=d.weekday())


def topic_progress(db: Session, ctx: PlanCtx, today: dt.date) -> dict:
    marks = {m.plan_lesson_id: m for m in db.scalars(select(TopicProgress).where(
        TopicProgress.assignment_id == ctx.ta.id))}
    taught: dict[int, list[dt.date]] = {}
    for e in db.scalars(select(JournalEntry).where(JournalEntry.assignment_id == ctx.ta.id,
                                                   JournalEntry.plan_lesson_id.is_not(None)).order_by(JournalEntry.date)):
        taught.setdefault(e.plan_lesson_id, []).append(e.date)
    work: dict[int, dt.date] = {}
    for s in ctx.slots:
        if s.index is not None:
            work.setdefault(s.index, s.date)

    topics = []
    for i, pl in enumerate(ctx.lessons):
        m, dates = marks.get(pl.id), taught.get(pl.id, [])
        if m:
            status, done_on, source = m.status, m.done_on, 'qeyd'
        elif dates:
            status, done_on, source = 'keçildi', dates[-1], 'jurnal'
        else:
            status, done_on, source = ('gecikir' if pl.date < today else 'gözlənilir'), None, None
        ref = done_on if status in DONE else today
        topics.append({
            'id': pl.id, 'seq': pl.seq, 'semester': pl.semester, 'section': pl.section, 'topic': pl.topic,
            'assessment_type': pl.assessment_type, 'exam_no': pl.exam_no, 'official_date': pl.date,
            'working_date': work.get(i), 'taught_dates': dates, 'status': status, 'done_on': done_on,
            'source': source, 'note': m.note if m else None,
            # gecikmə (gün): keçilibsə – rəsmi tarixdən nə qədər sonra; keçilməyibsə – bu günə qədər (yalnız vaxtı keçibsə)
            'delay_days': (ref - pl.date).days if (status in DONE or pl.date < today) else None,
        })

    done = [t for t in topics if t['status'] in DONE]
    expected = sum(t['official_date'] <= today for t in topics)
    total = len(topics)
    delta = len(done) - expected
    wh = ctx.ta.weekly_hours or 1
    remaining = total - len(done)
    slots_left = sum(s.date > today for s in ctx.slots)
    weeks_left = round(slots_left / wh, 1)
    recent = sum(1 for t in done if t['done_on'] and today - dt.timedelta(days=28) < t['done_on'] <= today)
    summary = {
        'total': total, 'done': len(done), 'partial': sum(t['status'] == 'qismən' for t in topics),
        'review': sum(t['status'] == 'təkrar' for t in topics),
        'overdue': sum(t['status'] == 'gecikir' for t in topics),
        'expected': expected, 'delta': delta, 'delta_weeks': round(delta / wh, 1),
        'done_pct': round(len(done) * 100 / total, 1) if total else None,
        'plan_pct': round(expected * 100 / total, 1) if total else None,
        'hold_lag': next((s.shift for s in ctx.slots if s.date >= today), ctx.slots[-1].shift if ctx.slots else 0),
        'weekly_hours': ctx.ta.weekly_hours,
    }
    forecast = {
        'remaining': remaining, 'slots_left': slots_left, 'weeks_left': weeks_left,
        'shortfall': max(0, remaining - slots_left),                  # ilin sonuna sığmayan mövzu
        'pace_recent': round(recent / 4, 1),                          # son 4 həftədə həftəlik keçilən mövzu
        'pace_needed': round(remaining / weeks_left, 1) if weeks_left else None,
    }

    sections: list[dict] = []
    for t in topics:
        key = t['section'] or '—'
        if not sections or sections[-1]['section'] != key:
            sections.append({'section': key, 'semester': t['semester'], 'total': 0, 'done': 0, 'expected': 0,
                             'from_seq': t['seq'], 'to_seq': t['seq']})
        sec = sections[-1]
        sec['total'] += 1
        sec['done'] += t['status'] in DONE
        sec['expected'] += t['official_date'] <= today
        sec['to_seq'] = t['seq']

    series = []
    if topics:
        y = ctx.year
        w, last = _monday(y.start), y.end
        plan_dates = sorted(t['official_date'] for t in topics)
        done_dates = sorted(t['done_on'] for t in done if t['done_on'])
        while w <= last:
            end = w + dt.timedelta(days=6)
            series.append({'week': w, 'planned': sum(d <= end for d in plan_dates),
                           'done': sum(d <= end for d in done_dates) if w <= today else None})
            w += dt.timedelta(days=7)
    return {'summary': summary, 'forecast': forecast, 'sections': sections, 'series': series, 'topics': topics,
            'today': today}
