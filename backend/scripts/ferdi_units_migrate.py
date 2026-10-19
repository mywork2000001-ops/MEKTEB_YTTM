"""Fərdi qrupların köhnə vaxtlarını «görüş = N akademik saat» formatına çevirir (docs/ferdi-perspektiv-plan-promtu.md §2).

Köhnə: 17:00–18:30 bir yuva. Yeni: iki yuva (17:00–17:45, 17:45–18:30). Birinci hissə köhnə sırasını (jurnal yazılarını) saxlayır,
qalan hissələr yeni boş sıra alır. Sxem dəyişmir (ta.times JSON).

İstifadə (backend qovluğunda):
    python -m scripts.ferdi_units_migrate            # quru rejim (defolt): yalnız hesabat, heç nə yazılmır
    python -m scripts.ferdi_units_migrate --apply    # yalnız açıq bayraqla yazır (canlı DB – istifadəçinin razılığı ilə)
"""
import argparse
import sys


def plan_ta(times: dict, slots: dict | None) -> tuple[dict, dict, int]:
    """(yeni times, yeni slots, əlavə olunan yuva sayı). Artıq çevrilmiş vaxtlar toxunulmaz qalır."""
    from app.api.classes import meeting_parts
    new_times: dict[str, str] = {}
    by_day: dict[int, list[tuple[int, str, str]]] = {}
    for k, v in times.items():
        wd, p = map(int, k.split(':'))
        s, e = v.split('–')
        by_day.setdefault(wd, []).append((p, s, e))
    added = 0
    for wd, rows in by_day.items():
        used = {p for p, _, _ in rows}
        free = iter(p for p in range(10) if p not in used)
        for p, s, e in sorted(rows):
            parts = meeting_parts(s, e)
            new_times[f'{wd}:{p}'] = f'{parts[0][0]}–{parts[0][1]}'
            for s2, e2 in parts[1:]:
                try:
                    q = next(free)
                except StopIteration:
                    raise SystemExit(f'gün {wd}: 10 yuvadan çox lazım olur')
                new_times[f'{wd}:{q}'] = f'{s2}–{e2}'
                added += 1
    new_slots: dict[str, list[int]] = {}
    for k in new_times:
        wd, p = map(int, k.split(':'))
        new_slots.setdefault(str(wd), []).append(p)
    return new_times, {k: sorted(v) for k, v in new_slots.items()}, added


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--apply', action='store_true', help='həqiqətən yaz (defolt – quru rejim)')
    ap.add_argument('--dry-run', action='store_true', help='quru rejim (defolt)')
    a = ap.parse_args(argv)
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import School, SchoolClass, TeachingAssignment
    db = SessionLocal()
    total = changed = 0
    try:
        q = (select(TeachingAssignment, SchoolClass).join(SchoolClass, SchoolClass.id == TeachingAssignment.class_id)
             .join(School, School.id == SchoolClass.school_id)
             .where(School.kind == 'private', TeachingAssignment.times.is_not(None)))
        for ta, c in db.execute(q):
            if not ta.times:
                continue
            nt, ns, added = plan_ta(ta.times, ta.slots)
            total += 1
            print(f'{c.name} / {ta.subject} (ta {ta.id}): {len(ta.times)} → {len(nt)} yuva (+{added})')
            if added:
                changed += 1
                if a.apply:
                    ta.times, ta.slots, ta.weekly_hours = nt, ns, len(nt)
        if a.apply and changed:
            db.commit()
        print(f'Qrup: {total}, dəyişən: {changed}. ' + ('YAZILDI.' if a.apply else 'Quru rejim – heç nə yazılmadı (--apply ilə yazılır).'))
    finally:
        db.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
