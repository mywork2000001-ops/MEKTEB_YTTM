"""Bank boşluqları hesabatı (docs/sinfe-gore-testler-promtu.md §3): proqramın hər mövzusu üçün sinif + tapılan fayl + uyğunluq.
Yalnız oxuyur (DATABASE_URL-dəki bazadan), heç nə yazmır.

İstifadə (backend qovluğunda):
  py -m scripts.bank_coverage --list                       # proqramlar
  py -m scripts.bank_coverage --key hazirliq-buraxilis-9   # daxili proqram açarı
  py -m scripts.bank_coverage --id 12 [--grade 7] [--missing]
"""
import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--key')
    ap.add_argument('--id', type=int)
    ap.add_argument('--grade', type=int, help='qrupun sinfi (proqramda sinfi olmayan mövzular üçün)')
    ap.add_argument('--missing', action='store_true', help='yalnız tapılmayanlar')
    a = ap.parse_args(argv)

    from sqlalchemy import select

    from app.bank.coverage import coverage
    from app.db import SessionLocal
    from app.models import PlanProgram
    with SessionLocal() as db:
        if a.list:
            for p in db.scalars(select(PlanProgram).where(PlanProgram.archived_at.is_(None)).order_by(PlanProgram.id)):
                print(f'{p.id:>4}  {p.key or "-":<28} {p.title}')
            return 0
        p = db.get(PlanProgram, a.id) if a.id else db.scalar(select(PlanProgram).where(PlanProgram.key == a.key)) if a.key else None
        if p is None:
            print('Proqram tapılmadı: --id və ya --key göstərin (--list ilə siyahı)')
            return 1
        r = coverage(db, p, None, a.grade)
        print(f'{p.title}\nMövzu: {r["total"]} · tapıldı: {r["found"]} · yoxdur: {r["missing"]} · gözlənilir: {r["pending"]}')
        for g, v in r['by_grade'].items():
            print(f'  sinif {g}: {v["found"]}/{v["total"]} tapıldı, yoxdur {v["missing"]}, gözlənilir {v["pending"]}')
        for i in r['items']:
            if a.missing and i['found']:
                continue
            tag = 'OK ' if i['found'] else 'GÖZ' if i['pending'] else 'YOX'
            print(f'  [{tag}] {i["grade"] or "?":>2}  {i["topic"][:60]:<60} -> {(i["source"] or "-")} {i["label"] or ""} ({i["cover"]})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
