"""Fərdi qrupların köhnə vaxtlarını «görüş = N akademik saat» formatına çevirmək (docs/ferdi-perspektiv-plan-promtu.md §2).

Ortaq məntiq: həm `scripts/ferdi_units_migrate.py`, həm də `/api/workspaces/ferdi-units` bunu işlədir."""
from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session

from .domain.calendar import WEEKDAYS
from .models import SchoolClass, TeachingAssignment, User


def plan_ta(times: dict, slots: dict | None) -> tuple[dict, dict, int]:
    """(yeni times, yeni slots, əlavə olunan yuva sayı). Artıq çevrilmiş vaxtlar toxunulmaz qalır.
    Birinci hissə köhnə sırasını saxlayır (jurnal yazıları), qalanlar mümkünsə ondan sonrakı boş sıraya düşür
    (ardıcıl sıralar bir görüş kimi qruplanır), yoxsa ən kiçik boş sıraya."""
    from .api.classes import meeting_parts
    new_times: dict[str, str] = {}
    by_day: dict[int, list[tuple[int, str, str]]] = {}
    for k, v in times.items():
        wd, p = map(int, k.split(':'))
        s, e = v.split('–')
        by_day.setdefault(wd, []).append((p, s, e))
    added = 0
    for wd, rows in by_day.items():
        taken = {p for p, _, _ in rows}
        for p, s, e in sorted(rows):
            parts = meeting_parts(s, e)
            new_times[f'{wd}:{p}'] = f'{parts[0][0]}–{parts[0][1]}'
            nxt = p + 1
            for s2, e2 in parts[1:]:
                q = nxt if nxt < 10 and nxt not in taken else next((x for x in range(10) if x not in taken), None)
                if q is None:
                    raise ValueError(f'gün {wd}: 10 yuvadan çox lazım olur')
                taken.add(q)
                new_times[f'{wd}:{q}'] = f'{s2}–{e2}'
                nxt = q + 1
                added += 1
    new_slots: dict[str, list[int]] = {}
    for k in new_times:
        wd, p = map(int, k.split(':'))
        new_slots.setdefault(str(wd), []).append(p)
    return new_times, {k: sorted(v) for k, v in new_slots.items()}, added


def _meetings(times: dict) -> list[dict]:
    from .api.classes import times_groups
    return times_groups(SimpleNamespace(times=times))


def _fmt(g: dict) -> str:
    return f"{WEEKDAYS[g['weekday']]} {g['start']}–{g['end']}"


def report_ta(ta: TeachingAssignment, cls: SchoolClass, nt: dict, added: int) -> dict:
    from .api.classes import meeting_parts
    old = _meetings(ta.times or {})
    new = _meetings(nt)
    return {
        'ta_id': ta.id, 'class': cls.name, 'subject': ta.subject,
        'old_times': [_fmt(g) for g in old],
        'new_meetings': [{'weekday': g['weekday'], 'day': WEEKDAYS[g['weekday']], 'start': g['start'], 'end': g['end'],
                          'units': g['units'], 'parts': [f'{a}–{b}' for a, b in meeting_parts(g['start'], g['end'])]} for g in new],
        'old_slots': len(ta.times or {}), 'new_slots': len(nt),
        'has_program': bool(ta.program_id), 'changed': bool(added),
    }


def private_tas(db: Session, user: User, school_id: int) -> list[tuple[TeachingAssignment, SchoolClass]]:
    q = (select(TeachingAssignment, SchoolClass).join(SchoolClass, SchoolClass.id == TeachingAssignment.class_id)
         .where(TeachingAssignment.teacher_id == user.id, TeachingAssignment.archived_at.is_(None), SchoolClass.school_id == school_id,
                SchoolClass.archived_at.is_(None), TeachingAssignment.times.is_not(None))
         .order_by(SchoolClass.name, TeachingAssignment.subject))
    return [(ta, c) for ta, c in db.execute(q) if ta.times]


def build_report(db: Session, user: User, school_id: int) -> list[dict]:
    """Quru hesabat – heç nə yazmır."""
    out = []
    for ta, c in private_tas(db, user, school_id):
        nt, _, added = plan_ta(ta.times, ta.slots)
        out.append(report_ta(ta, c, nt, added))
    return out


def apply_all(db: Session, user: User, school_id: int) -> tuple[list[dict], list[int]]:
    """Hamısını çevirir (idempotent); proqramı olan qruplarda plan avtomatik yenidən tətbiq olunur (keçilmiş dərslər dondurulur).
    (hesabat – çevirmədən əvvəlki vəziyyətlə, dəyişən ta id-ləri). commit çağıran tərəfdədir."""
    from .api.common import audit
    from .models import PlanProgram
    from .programs import apply
    out, changed = [], []
    for ta, c in private_tas(db, user, school_id):
        nt, ns, added = plan_ta(ta.times, ta.slots)
        out.append(report_ta(ta, c, nt, added))
        if not added:
            continue
        ta.times, ta.slots, ta.weekly_hours = nt, ns, len(nt)
        db.flush()
        changed.append(ta.id)
        audit(db, user, 'update', 'teaching', ta.id, class_id=c.id, ferdi_units=True)
        p = db.get(PlanProgram, ta.program_id) if ta.program_id else None
        if p and not p.archived_at:
            rep = apply(db, p, ta, user, ta.program_sections)
            audit(db, user, 'update', 'plan_program', ta.id, program_id=p.id, lessons=rep['lessons'], auto=True, ferdi_units=True)
    return out, changed
