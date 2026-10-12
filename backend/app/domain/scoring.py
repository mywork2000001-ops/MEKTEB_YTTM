"""100 ballıq qiymətləndirmə (docs/yuz-balliq-sistem-promtu.md).

Sualın çəkisi = növ × çətinlik: qapalı (variantlı) ×1, açıq ×1,5; asan ×1, orta ×1,5, çətin ×2.
Bal = 100 × çəki ÷ cəmi çəki, 0,5-ə yuvarlaq, cəmi dəqiq 100 (qalıq ən böyük bala). Çətinlik: müəllim → statistika → növ.
Ballar test yaradılanda sualın surətində dondurulur (q['points']); balı olmayan köhnə testdə – bərabər bal."""
from __future__ import annotations

LEVELS = ('asan', 'orta', 'çətin')
TYPE_W = {'mcq': 1.0, 'open': 1.5}
DIFF_W = {'asan': 1.0, 'orta': 1.5, 'çətin': 2.0}
STAT_MIN = 10                      # statistikaya görə çətinlik – ən azı bu qədər cavab
EASY, HARD = 0.70, 0.40            # düz cavab payı: > 70% – asan, < 40% – çətin


def difficulty_of(q: dict) -> tuple[str, str]:
    """(çətinlik, mənbə): müəllim → statistika → sual növü."""
    if q.get('difficulty') in LEVELS:
        return q['difficulty'], 'müəllim'
    if q.get('difficulty_auto') in LEVELS:
        return q['difficulty_auto'], 'statistika'
    return ('orta' if q.get('kind') == 'open' else 'asan'), 'növ'


def from_stats(n: int, ok: int) -> str | None:
    """Faktiki çətinlik (klassik test nəzəriyyəsi – düz cavab payı)."""
    if n < STAT_MIN:
        return None
    p = ok / n
    return 'asan' if p > EASY else 'çətin' if p < HARD else 'orta'


def assign_points(qs: list[dict]) -> list[dict]:
    """Suallara bal yazır (cəmi 100): q['points'], q['level'] (həll olunmuş çətinlik), q['level_src']."""
    if not qs:
        return qs
    ws = []
    for q in qs:
        lvl, src = difficulty_of(q)
        q['level'], q['level_src'] = lvl, src
        ws.append(TYPE_W.get(q.get('kind'), 1.0) * DIFF_W[lvl])
    total = sum(ws)
    pts = [max(0.5, round(100 * w / total * 2) / 2) for w in ws]
    diff = round((100 - sum(pts)) * 2) / 2
    order = sorted(range(len(pts)), key=lambda i: -pts[i])
    k = 0
    while abs(diff) >= 0.5 and k < 10 * len(pts):          # qalıq – ən böyük ballara 0,5-lik addımlarla
        i = order[k % len(order)]
        step = 0.5 if diff > 0 else -0.5
        if pts[i] + step >= 0.5:
            pts[i] += step
            diff -= step
        k += 1
    for q, p in zip(qs, pts):
        q['points'] = p
    return qs


def has_points(qs: list) -> bool:
    return bool(qs) and all(isinstance(q, dict) and isinstance(q.get('points'), (int, float)) for q in qs)


def question_points(qs: list) -> list[float]:
    """Balı yazılmış test – öz balları; köhnə test – bərabər (100 ÷ n)."""
    if has_points(qs):
        return [float(q['points']) for q in qs]
    return [100 / len(qs)] * len(qs) if qs else []
