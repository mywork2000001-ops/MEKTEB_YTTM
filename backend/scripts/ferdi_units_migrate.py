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
    """Ortaq məntiq – app/ferdi_units.py (tətbiqdəki /api/workspaces/ferdi-units də onu işlədir)."""
    from app.ferdi_units import plan_ta as _plan
    try:
        return _plan(times, slots)
    except ValueError as e:
        raise SystemExit(str(e))


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
