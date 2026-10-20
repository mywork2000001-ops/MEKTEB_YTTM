"""Məşğələ qruplarına proqram təyini (docs/meshgele-proqram-ve-video-beledci-promtu.md §A). Məntiq – app/extra_programs.py.
DEFOLT QURU REJİM (--dry): heç nə yazmır. Yazı yalnız --apply ilə. DATABASE_URL-dəki baza (canlı baza – yalnız istifadəçinin razılığı ilə!).

  py -m scripts.extra_programs --dry                 # bütün aktiv qruplar, hesabat
  py -m scripts.extra_programs --apply --school 1
"""
from __future__ import annotations

import argparse


def main(argv: list[str] | None = None, db=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--dry', action='store_true', help='quru rejim (defolt)')
    g.add_argument('--apply', action='store_true', help='yaz')
    ap.add_argument('--school', type=int, help='məktəbin nömrəsi (defolt: hamısı)')
    a = ap.parse_args(argv)

    from sqlalchemy import select

    from app.extra_programs import assign_programs
    from app.models import ExtraCourse
    from app.services import today
    own = db is None
    if own:
        from app.db import SessionLocal
        db = SessionLocal()
    try:
        st = select(ExtraCourse).where(ExtraCourse.archived_at.is_(None))
        if a.school:
            st = st.where(ExtraCourse.school_id == a.school)
        rows = assign_programs(db, list(db.scalars(st.order_by(ExtraCourse.id))), today(), apply=a.apply)
        for r in rows:
            prog = (r['program'] or {}).get('key') or r['mode'] or '—'
            print(f"#{r['course_id']:<4} {r['title'][:32]:<32} {r['kind']:<8} sinif={r['grade'] or '—'} proqram={prog} "
                  f"doldurulur={r['to_fill']} keçirilmiş={r['held']} əl={r['kept_manual']}" + (f"  [{r['skip']}]" if r['skip'] else ''))
        if a.apply:
            db.commit()
            print('Yazıldı.')
        else:
            db.rollback()
            print('Quru rejim – heç nə yazılmadı (--apply ilə yazın).')
        return 0
    finally:
        if own:
            db.close()


if __name__ == '__main__':
    raise SystemExit(main())
