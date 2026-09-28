"""Tədris təqvimi və dərs cədvəli (2026–2027). Mənbə: 05 Texniki/build.py (OFF lüğəti) və müəllimin həftəlik cədvəli.
Bu dəyərlər yalnız ilkin (seed) məlumatdır – bazada redaktə edilə bilən cədvəl kimi saxlanılır."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

YEAR_START = dt.date(2026, 9, 15)
YEAR_END = dt.date(2027, 6, 14)
SEM1_END = dt.date(2027, 1, 26)
SEM2_START = dt.date(2027, 2, 1)
BSQ_DATES = {1: SEM1_END, 2: YEAR_END}

OFF_DAYS: dict[dt.date, str] = {dt.date.fromisoformat(k): v for k, v in {
    '2026-11-09': 'Dövlət Bayrağı Günü',
    '2026-11-10': 'Zəfər Günü (8 noyabrın əvəzi)',
    '2026-12-30': 'Qış tətili / Yeni il bayramı',
    '2026-12-31': 'Qış tətili / Yeni il bayramı',
    '2027-01-01': 'Qış tətili / Yeni il bayramı',
    '2027-01-04': 'Qış tətili / Yeni il bayramı',
    '2027-01-05': 'Qış tətili / Yeni il bayramı',
    '2027-01-06': 'Qış tətili / Yeni il bayramı',
    '2027-01-20': 'Ümumxalq Hüzn Günü',
    '2027-01-27': 'Yarımillər arası tətil',
    '2027-01-28': 'Yarımillər arası tətil',
    '2027-01-29': 'Yarımillər arası tətil',
    '2027-03-08': 'Qadınlar Günü',
    '2027-03-09': 'Ramazan bayramı (təxmini)',
    '2027-03-10': 'Ramazan bayramı (təxmini)',
    '2027-03-19': 'Yaz tətili / Novruz bayramı',
    '2027-03-22': 'Yaz tətili / Novruz bayramı',
    '2027-03-23': 'Yaz tətili / Novruz bayramı',
    '2027-03-24': 'Yaz tətili / Novruz bayramı',
    '2027-03-25': 'Yaz tətili / Novruz bayramı',
    '2027-03-26': 'Yaz tətili / Novruz bayramı',
    '2027-05-10': 'Faşizm üzərində qələbə günü (9 mayın əvəzi)',
    '2027-05-17': 'Qurban bayramı (təxmini)',
    '2027-05-18': 'Qurban bayramı (təxmini)',
    '2027-05-28': 'Müstəqillik Günü',
}.items()}

WEEKDAYS = ['B.e.', 'Ç.a.', 'Ç.', 'C.a.', 'C.']
BELLS = ['08:50–09:35', '09:40–10:25', '10:35–11:20', '11:25–12:10', '12:15–13:00', '13:35–14:20', '14:25–15:10']


@dataclass(frozen=True)
class ClassSeed:
    code: str            # daxili açar
    name: str            # interfeysdə göstərilən ad
    kind: str            # 'TOM' | 'adi'
    weekly_hours: int
    plan_prefix: str     # 01 Aktual dərs proqramları – fayl adının əvvəli
    slots: dict[int, list[int]]   # həftə günü (0 = B.e.) -> dərs saatları
    has_summative: bool = True
    parent: str | None = None
    utis_class: str | None = None      # UTİS siyahısında sinif (şagirdlər buradan: Utis_siyahi.xlsx)
    bells: dict[int, str] | None = None   # sinfin öz zəng vaxtları (dərs saatı -> vaxt); yoxdursa məktəbin BELLS
    split_with: str | None = None      # bölünən qrup: paralel keçilən fənn


CLASSES: list[ClassSeed] = [
    ClassSeed('xb', 'X b', 'TOM', 5, 'X-b sinif – bütöv sinif', {2: [3, 7], 3: [1, 4], 4: [2]}, utis_class='10 b'),
    ClassSeed('xb_q', 'X b (riyaziyyat qrupu)', 'TOM', 5, 'X-b sinif – riyaziyyat qrupu', {0: [3, 5], 1: [3, 6, 7]},
              has_summative=False, parent='xb',
              split_with='Biologiya – Şərqiyə müəllimə'),   # B.e. 3, 5; Ç.a. 3, 6, 7 – məktəb cədvəli, istifadəçi təsdiqi
    ClassSeed('xc', 'X c', 'TOM', 8, 'X-c sinif', {0: [6], 1: [2, 4], 2: [1, 2], 3: [6, 7], 4: [1]}, utis_class='10 c'),
    ClassSeed('xe', 'X e', 'TOM', 7, 'X-e sinif', {0: [2, 7], 1: [1, 5], 2: [6], 3: [5], 4: [6]}, utis_class='10 e'),   # istifadəçi təsdiqi 2026-09-28: X e = UTİS «10 e» (köhnə «X ə» vərəqi 10 ə idi – səhv)
    ClassSeed('xia', 'XI a', 'TOM', 7, 'XI-a sinif', {0: [4], 1: [], 2: [4, 5], 3: [2, 3], 4: [3, 4]}, utis_class='11 a 1'),
    # XI peşə – öz zəng vaxtları (istifadəçi, 28.09.2026): 1-ci saat 08:00–08:45, 2-ci saat 08:50–09:35
    ClassSeed('xip', 'XI peşə sinfi', 'adi', 4, 'XI peşə sinfi', {0: [1, 2], 1: [1], 2: [1]},
              bells={1: '08:00–08:45', 2: '08:50–09:35'}),
]
CLASS_BY_CODE = {c.code: c for c in CLASSES}

SCHOOL_TOM = 'Tərtər şəhər Rafiq Nuriyev adına 6 nömrəli tam orta ümumtəhsil məktəbi'
SCHOOL_ADI = 'Tərtər şəhər Rafiq Nuriyev adına 6 nömrəli ümumtəhsil məktəbi'


def school_title(kind: str) -> str:
    return SCHOOL_TOM if kind == 'TOM' else SCHOOL_ADI


def semester_of(d: dt.date) -> int:
    return 1 if d <= SEM1_END else 2


def is_school_day(d: dt.date, off: dict[dt.date, str] | None = None) -> bool:
    off = OFF_DAYS if off is None else off
    return YEAR_START <= d <= YEAR_END and d.weekday() < 5 and d not in off


def lesson_slots(slots: dict[int, list[int]], off: dict[dt.date, str] | None = None,
                 start: dt.date = YEAR_START, end: dt.date = YEAR_END) -> list[tuple[dt.date, int]]:
    """Cədvəl və təqvimə görə bütün dərs yuvaları (tarix, dərs saatı), xronoloji ardıcıllıqla."""
    off = OFF_DAYS if off is None else off
    out, d = [], start
    while d <= end:
        if d.weekday() < 5 and d not in off:            # il sərhədi – start/end (hər tədris ili üçün)
            for p in sorted(slots.get(d.weekday(), [])):
                out.append((d, p))
        d += dt.timedelta(days=1)
    return out


def check_plan_dates(plan_dates: list[dt.date], slots: dict[int, list[int]],
                     off: dict[dt.date, str] | None = None) -> dict:
    """Plandakı tarixləri cədvəl + təqvimdən hesablanan yuvalarla müqayisə edir. Planı dəyişmir, yalnız hesabat verir."""
    expected = [d for d, _ in lesson_slots(slots, off)]
    mismatches = []
    for i, (a, b) in enumerate(zip(plan_dates, expected), 1):
        if a != b:
            mismatches.append({'sira': i, 'planda': a.isoformat(), 'cedvelde': b.isoformat()})
    return {
        'plan_saat': len(plan_dates),
        'cedvel_saat': len(expected),
        'ferq': len(plan_dates) - len(expected),
        'uygunsuz_tarixler': len(mismatches),
        'ilk_uygunsuzluqlar': mismatches[:10],
        'tetile_dusen': [d.isoformat() for d in plan_dates if d in (OFF_DAYS if off is None else off)],
    }


def bsq_due_dates(slots: dict[int, list[int]]) -> tuple[dt.date, dt.date]:
    """BSQ qaydası: BSQ-1 – I yarımilin son dərs günü (SEM1_END-ə qədər), BSQ-2 – ilin son dərs günü (YEAR_END-ə qədər)."""
    days = [d for d, _ in lesson_slots(slots)]
    return max(d for d in days if d <= SEM1_END), max(d for d in days if d <= YEAR_END)


def check_bsq(plan_bsq: list[tuple[int | None, dt.date]], slots: dict[int, list[int]]) -> list[str]:
    """Plandakı BSQ-ləri qayda ilə tutuşdurur; boş siyahı = uyğundur. Eyni BSQ bir gündə 2 saat ola bilər."""
    due = bsq_due_dates(slots)
    got = sorted({(n, d) for n, d in plan_bsq})
    errs = []
    if len({n for n, _ in got}) != 2:
        errs.append(f'BSQ sayı 2 olmalıdır, planda: {len({n for n, _ in got})}')
    for n, d in got:
        if n in (1, 2) and d != due[n - 1]:
            errs.append(f'BSQ-{n}: planda {d:%d.%m.%Y}, olmalıdır {due[n - 1]:%d.%m.%Y} (yarımilin son dərs günü)')
    return errs


def bell_time(c: ClassSeed, period: int) -> str:
    """Dərs saatının vaxtı: sinfin öz zəngi, yoxdursa məktəbin ümumi zəngi."""
    if c.bells and period in c.bells:
        return c.bells[period]
    return BELLS[period - 1]


def _minutes(t: str) -> tuple[int, int]:
    a, b = t.replace('–', '-').split('-')
    f = lambda x: int(x.split(':')[0]) * 60 + int(x.split(':')[1])
    return f(a), f(b)


def teacher_conflicts(classes: list[ClassSeed]) -> list[str]:
    """Müəllimin həftəlik cədvəlində real vaxt üzrə üst-üstə düşən dərslər. Bölünən qrup (parent) öz sinfi ilə
    eyni anda ola bilməz; boş siyahı = toqquşma yoxdur."""
    busy, out = [], []
    for c in classes:
        for wd, periods in c.slots.items():
            for p in periods:
                a, b = _minutes(bell_time(c, p))
                for wd2, a2, b2, c2, p2 in busy:
                    if wd2 == wd and a < b2 and a2 < b:
                        out.append(f'{WEEKDAYS[wd]} {c2.name} ({p2}-ci saat) ↔ {c.name} ({p}-ci saat)')
                busy.append((wd, a, b, c, p))
    return out
