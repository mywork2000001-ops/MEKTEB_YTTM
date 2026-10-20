"""Perspektiv plandan mövzu testlərinin təyini (docs/plan-testleri-skripti-promtu.md §2.2). Məntiq – app/plan_tests.py.
DEFOLT QURU REJİM: heç nə yazmır, hesabat verir. Yazı yalnız --apply ilə (təsdiq sualı; --yes ilə soruşmur).
DATABASE_URL-dəki baza (canlı baza – yalnız istifadəçinin razılığı ilə!).

İstifadə (backend qovluğunda):
  py -m scripts.plan_tests --all                                  # bütün siniflər, bu gündən 7 gün, quru rejim
  py -m scripts.plan_tests --class "X a" --from 2026-10-20 --to 2026-11-30
  py -m scripts.plan_tests --all --missing --from 2026-09-15      # tarixə görə çatışmayan testlər (keçilmiş dərslər)
  py -m scripts.plan_tests --ta 42 --apply                        # yazır («N test yaradılacaq. Davam? [y/N]»)
  py -m scripts.plan_tests --all --apply --yes --include-weak --n 20 --out hesabat.csv
  py -m scripts.plan_tests --teacher login --all                  # konkret müəllimin dərsləri
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys

STATUS_AZ = {'ok': 'uyğun', 'weak': 'şübhəli', 'none': 'tapılmadı', 'pending': 'gözlənilir', 'manual': 'əl ilə seçilib',
             'has_test': 'test var', 'summative': 'summativ/sınaq', 'derived': 'törəmə dərs', 'past': 'keçib', 'missing': 'çatışan'}
COLS = ['class_name', 'date', 'seq', 'topic_no', 'topic', 'file', 'source', 'questions', 'status', 'reason', 'will_create', 'created']


def main(argv: list[str] | None = None, db=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--all', action='store_true', help='bütün siniflər (fərdi məkanlar daxil deyil)')
    ap.add_argument('--class', dest='cls', help='sinfin adı, məs. "X a"')
    ap.add_argument('--ta', type=int, action='append', help='dərs bağlılığının nömrəsi (təkrar oluna bilər)')
    ap.add_argument('--teacher', help='müəllimin giriş adı və ya adı')
    ap.add_argument('--from', dest='d1', type=dt.date.fromisoformat, help='başlanğıc (defolt: bu gün; --missing ilə: ilin əvvəli)')
    ap.add_argument('--to', dest='d2', type=dt.date.fromisoformat, help='son (defolt: başlanğıc + 7 gün)')
    ap.add_argument('--missing', action='store_true', help='keçilmiş testsiz dərslərə də (açılma – indi, bağlanma +3 gün 22:00)')
    ap.add_argument('--apply', action='store_true', help='yaz (defolt quru rejim)')
    ap.add_argument('--yes', action='store_true', help='təsdiq sualı vermə')
    ap.add_argument('--include-weak', action='store_true', help='şübhəli uyğunluqda da yarat')
    ap.add_argument('--n', type=int, default=15, help='sual sayı (defolt 15)')
    ap.add_argument('--duration', type=int, default=0, help='həll müddəti, dəq. (defolt 0 – taymer yoxdur)')
    ap.add_argument('--days', type=int, default=0, help='dərsdən N gün sonra 22:00 bağlansın (defolt 0 – son tarix yoxdur)')
    ap.add_argument('--out', help='CSV faylı')
    a = ap.parse_args(argv)

    from app import plan_tests as E
    from app.services import today
    own = db is None
    if own:
        from app.db import SessionLocal
        db = SessionLocal()
    try:
        tas = E.scope_system(db, a.ta, a.cls, a.teacher, a.all)
        if not tas:
            print('Dərs tapılmadı: --all, --class, --ta və ya --teacher göstərin')
            return 1
        d1 = a.d1 or (None if a.missing else today())
        d2 = a.d2 or ((d1 or today()) + dt.timedelta(days=7))
        opts = E.Opts(n_questions=a.n, duration=a.duration, close_days=a.days, missing_close_days=a.days, missing=a.missing, include_weak=a.include_weak)
        rep = E.assign(db, None, tas, d1, d2, opts, apply=False)
        _print(rep, d1, d2)
        n = sum(1 for r in rep.rows if r['will_create'])
        if a.apply and n:
            if not a.yes and input(f'{n} test yaradılacaq. Davam? [y/N] ').strip().lower() not in ('y', 'yes', 'b', 'bəli'):
                print('Ləğv edildi')
                a.apply = False
            else:
                rep = E.assign(db, None, tas, d1, d2, opts, apply=True)
                print(f'Yaradıldı: {sum(1 for r in rep.rows if r["created"])}')
        elif a.apply:
            print('Yaradılacaq test yoxdur')
        else:
            print(f'QURU REJİM: {n} test yaradıla bilər (yazmaq üçün --apply)')
        if a.out:
            with open(a.out, 'w', newline='', encoding='utf-8-sig') as f:
                w = csv.DictWriter(f, COLS, extrasaction='ignore', delimiter=';')
                w.writeheader()
                w.writerows(rep.rows)
            print(f'CSV: {a.out}')
    finally:
        if own:
            db.close()
    return 0


def _print(rep, d1, d2) -> None:
    print(f'Dövr: {d1 or "ilin əvvəli"} – {d2}')
    for s in rep.summary():
        parts = [f'{STATUS_AZ[k]} {s[k]}' for k in STATUS_AZ if s.get(k)]
        print(f'  {s["class_name"]:<22} cəmi {s["total"]:>3} · yaradılacaq {s["will_create"]:>3} · ' + ', '.join(parts))
    for r in rep.rows:
        if r['status'] in ('weak', 'none', 'pending') or r['will_create']:
            print(f'    {r["class_name"]:<10} {r["date"] or "-":<10} №{r["seq"]:<3} {r["topic_no"] or "":<5} {r["topic"][:44]:<44} '
                  f'{STATUS_AZ[r["status"]]:<11} {r["file"] or "-"} ({r["questions"]})')


if __name__ == '__main__':
    sys.exit(main())
