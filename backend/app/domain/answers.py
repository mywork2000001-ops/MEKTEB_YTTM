"""Onlayn tapşırıq cavablarının yoxlanması.
- mcq: seçilən variantın indeksi.
- open: qəbul edilən cavablar «|» ilə ayrılır (viktorina formatı); böyük/kiçik hərf, boşluq, onluq vergül/nöqtə
  fərq etmir. Uyğunluq cavabı «1:a,b, 2:d» – sətirlərin və hərflərin sırası fərq etmir."""
from __future__ import annotations

import re


def _norm(s: str) -> str:
    s = str(s).strip().lower().replace('−', '-').replace('–', '-')
    s = re.sub(r'(\d),(\d)', r'\1.\2', s)            # 2,5 -> 2.5
    s = re.sub(r'\s+', '', s)
    return s.rstrip('.')


def _match_canon(s: str) -> str | None:
    """«1:a,b; 2:d» -> «1:ab|2:d» (sıradan asılı deyil); uyğunluq formatı deyilsə None."""
    parts = re.findall(r'(\d+)\s*[:)\-]\s*([a-e](?:\s*[,/ ]?\s*[a-e])*)', str(s).lower())
    if not parts:
        return None
    rows = {int(k): ''.join(sorted(set(re.findall(r'[a-e]', v)))) for k, v in parts}
    return '|'.join(f'{k}:{rows[k]}' for k in sorted(rows))


def _num(s: str) -> float | None:
    try:
        return float(_norm(s).replace('/', '÷')) if '/' not in s else None
    except ValueError:
        return None


def check_open(given: str | None, accepted: str) -> bool:
    if given is None or not str(given).strip():
        return False
    for a in str(accepted).split('|'):
        if not a.strip():
            continue
        if _norm(given) == _norm(a):
            return True
        ma, mg = _match_canon(a), _match_canon(given)
        if ma and ma == mg:
            return True
        na, ng = _num(a), _num(given)
        if na is not None and ng is not None and abs(na - ng) < 1e-9:
            return True
    return False


def check(q: dict, given) -> bool:
    if q['kind'] == 'mcq':
        try:
            return given is not None and int(given) == int(q['correct'])
        except (TypeError, ValueError):
            return False
    return check_open(given, q.get('answer') or '')


def match_rows(s) -> dict[int, str] | None:
    """Uyğunluq cavabı -> {sətir: hərflər}; uyğunluq formatı deyilsə None (_match_canon ilə eyni parser)."""
    c = _match_canon(s)
    if c is None:
        return None
    return {int(k): v for k, v in (x.split(':') for x in c.split('|'))}


def part_share(q: dict, given) -> float:
    """Uyğunluq sualında düz sətirlərin payı (0..1); sətir yalnız tam düz olanda sayılır.
    Tam düzdürsə 1; uyğunluq formatı deyilsə 0; qəbul edilən variantlardan ən yaxşısı götürülür."""
    if check(q, given):
        return 1.0
    if q.get('kind') == 'mcq' or given is None:
        return 0.0
    gr = match_rows(given)
    if not gr:
        return 0.0
    best = 0.0
    for a in str(q.get('answer') or '').split('|'):
        ar = match_rows(a)
        if ar:
            best = max(best, sum(1 for k, v in ar.items() if gr.get(k) == v) / len(ar))
    return best
