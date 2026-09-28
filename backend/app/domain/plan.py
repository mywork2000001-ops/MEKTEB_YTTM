"""İşçi plan: rəsmi perspektiv plan + «Mövzunu saxla» (geriləmə).

Rəsmi plan heç vaxt dəyişmir. Dərs yuvaları (tarix, dərs saatı) cədvəl + təqvimdən hesablanır; k-cı yuvanın
mövzusu = rəsmi planın (k − k-dan ƏVVƏLKİ saxlamaların sayı)-cı dərsi. Yəni saxlanılan yuvada həmin mövzu
keçilir və növbəti dərsdə DAVAM edir; sonrakı mövzular bir dərs sürüşür. İlin sonunda sığmayan dərslər
«sığmayan» siyahısında qaytarılır (müəllim görsün)."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from .calendar import lesson_slots


@dataclass(frozen=True)
class Slot:
    date: dt.date
    period: int
    index: int                 # rəsmi plandakı dərsin indeksi (0-dan) və ya None – plan bitib
    held: bool                 # bu yuvada «mövzunu saxla» basılıb
    shift: int                 # rəsmi plana nisbətən geriləmə (dərs sayı)


def working_plan(slots: dict[int, list[int]], n_lessons: int, holds: set[tuple[dt.date, int]],
                 off: dict[dt.date, str], start: dt.date, end: dt.date) -> tuple[list[Slot], list[int]]:
    out, shift = [], 0
    for d, p in lesson_slots(slots, off, start, end):
        k = len(out)
        idx = k - shift
        held = (d, p) in holds
        out.append(Slot(d, p, idx if 0 <= idx < n_lessons else None, held, shift))
        if held:
            shift += 1
    last = max((s.index for s in out if s.index is not None), default=-1)
    return out, list(range(last + 1, n_lessons))


def slot_at(plan: list[Slot], d: dt.date, period: int) -> Slot | None:
    return next((s for s in plan if s.date == d and s.period == period), None)


def view_range(view: str, d: dt.date, sem1_end: dt.date, sem2_start: dt.date, start: dt.date,
               end: dt.date) -> tuple[dt.date, dt.date]:
    """Şagird/müəllim görünüşləri: gün, həftə (B.e.–C.), ay, yarımil."""
    if view == 'day':
        return d, d
    if view == 'week':
        a = d - dt.timedelta(days=d.weekday())
        return a, a + dt.timedelta(days=4)
    if view == 'month':
        a = d.replace(day=1)
        b = (a.replace(year=a.year + 1, month=1) if a.month == 12 else a.replace(month=a.month + 1)) - dt.timedelta(days=1)
        return a, b
    if view == 'semester':
        return (start, sem1_end) if d <= sem1_end else (sem2_start, end)
    raise ValueError(view)
