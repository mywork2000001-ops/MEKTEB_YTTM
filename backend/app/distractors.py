"""Distraktor təhlili (metodik audit M2): test sualı üzrə şagirdlərin seçdiyi variantların paylanması.
Cavab TaskAttempt.answers[str(sual_indeksi)] = ƏSL variant indeksi (variantlar qarışdırılmır, yalnız sualların sırası – attempt.order),
ona görə xəritələmə lazım deyil. Yalnız mcq; açıq (input) suallarda paylanma yoxdur."""
from __future__ import annotations

POP_SHARE = 0.30     # populyar səhv: təhvil verənlərin ≥30 %-i eyni səhv variantı seçib
POP_MIN = 3          # və ən azı 3 şagird


def question_distribution(q: dict, i: int, attempts: list) -> dict | None:
    """{counts:[…hər variant], empty, popular_wrong:int|None} – təhvil verilmiş cəhdlər üzrə; mcq deyilsə None."""
    opts = q.get('options')
    if q.get('kind') != 'mcq' or not opts:
        return None
    n = len(opts)
    counts, empty = [0] * n, 0
    for a in attempts:
        v = (a.answers or {}).get(str(i))
        try:
            k = int(v) if v not in (None, '') else None
        except (TypeError, ValueError):
            k = None
        if k is None or not 0 <= k < n:
            empty += 1
        else:
            counts[k] += 1
    try:
        right = int(q.get('correct'))
    except (TypeError, ValueError):
        right = -1
    total = len(attempts)
    pop = None
    wrong = [(c, k) for k, c in enumerate(counts) if k != right and c >= POP_MIN and c >= POP_SHARE * total]
    if wrong:
        pop = max(wrong, key=lambda x: (x[0], -x[1]))[1]
    return {'counts': counts, 'empty': empty, 'correct': right if 0 <= right < n else None, 'popular_wrong': pop}
