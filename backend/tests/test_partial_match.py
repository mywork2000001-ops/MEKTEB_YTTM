"""Metodik audit M9: uyğunluq sualında qismən bal (düz sətirlərin payı); correct sayı tam düzləri sayır."""
from types import SimpleNamespace

import pytest

from app.api import tasks as T
from app.domain.answers import part_share

KEY = '1:ab,2:c,3:de'
Q = {'kind': 'open', 'answer': KEY}


def test_partial_two_of_three():
    assert part_share(Q, '1:ab,2:c,3:d') == pytest.approx(2 / 3)
    assert part_share(Q, '1:ab,2:c,3:de') == 1.0
    assert part_share(Q, '') == 0.0 and part_share(Q, None) == 0.0
    assert part_share(Q, 'salam') == 0.0
    assert part_share({'kind': 'mcq', 'correct': 1}, 1) == 1.0 and part_share({'kind': 'mcq', 'correct': 1}, 0) == 0.0
    assert part_share({'kind': 'open', 'answer': '3'}, '4') == 0.0          # uyğunluq deyil – hamısı ya heç nə


@pytest.mark.parametrize('given', ['1-ab, 2-c, 3-d', '1:a,b; 2:c; 3:d', '3:d,1:b,a,2:c', '1) ab 2) c 3) d'])
def test_formats_equivalent(given):
    assert part_share(Q, given) == pytest.approx(2 / 3)


def test_alternative_keys_best_match():
    q = {'kind': 'open', 'answer': '1:a,2:b|1:b,2:a'}
    assert part_share(q, '1:b,2:b') == 0.5


def _task(manual=None, answer='1:ab,2:c,3:d'):
    qs = [{'kind': 'open', 'answer': KEY, 'points': 40}, {'kind': 'open', 'answer': '5', 'points': 60}]
    t = SimpleNamespace(questions=qs, kind=None, assignment_id=0)
    a = SimpleNamespace(answers={'0': answer, '1': '5'}, manual=manual, correct=None, total=None, points=None, grade=None)
    return t, a


def test_points_partial_correct_count_full_only(monkeypatch):
    monkeypatch.setattr(T, 'class_scale', lambda t: None)
    t, a = _task()
    T.score(t, a)
    assert a.correct == 1 and a.total == 2                   # tam düz: yalnız ikinci sual
    assert a.points == pytest.approx(round(40 * 2 / 3 + 60, 1))   # 86.7


def test_manual_override_wins(monkeypatch):
    monkeypatch.setattr(T, 'class_scale', lambda t: None)
    t, a = _task(manual={'0': False})
    T.score(t, a)
    assert a.correct == 1 and a.points == 60.0              # əl düzəlişi qismən balı əvəz edir
    t, a = _task(manual={'0': True})
    T.score(t, a)
    assert a.correct == 2 and a.points == 100.0


def test_no_partial_for_ksq_and_sinaq(monkeypatch):
    monkeypatch.setattr(T, 'class_scale', lambda t: None)
    for kind in ('ksq', 'sinaq'):
        t, a = _task()
        t.kind = kind
        T.score(t, a)
        assert a.points == 60.0
