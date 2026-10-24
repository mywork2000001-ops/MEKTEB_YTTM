"""Distraktor təhlili (M2): app/distractors.py – variantların paylanması, boş cavab, populyar səhv həddi."""
from types import SimpleNamespace as NS

from app.distractors import question_distribution

MCQ = {'kind': 'mcq', 'text': {'az': 'q'}, 'options': [{'az': x} for x in 'abcde'], 'correct': 2}
OPEN = {'kind': 'open', 'text': {'az': 'o'}, 'answer': '5'}


def att(a, order=(1, 0)):
    """Bir şagird: ans – 0-cı sualın cavabı; order qarışdırılmış sıradır (cavab yenə də ƏSL indekslə yazılır)."""
    return NS(answers={'0': a, '1': 'x'}, order=list(order))


def test_distribution_five_students_shuffled_order():
    at = [att(2, order=(1, 0)), att(0, order=(0, 1)), att(0, order=(1, 0)), att('', order=(0, 1)), att(4, order=(1, 0))]
    d = question_distribution(MCQ, 0, at)
    assert d['counts'] == [2, 0, 1, 0, 1] and d['empty'] == 1 and d['correct'] == 2
    assert sum(d['counts']) + d['empty'] == 5
    assert d['popular_wrong'] is None            # 2/5 = 40 %, amma 3 nəfərdən azdır


def test_input_question_has_no_distribution():
    assert question_distribution(OPEN, 1, [att(1)]) is None


def test_popular_wrong_threshold():
    # 3 nəfər eyni səhv (3/10 = 30 %) → populyar
    at = [att(0)] * 3 + [att(2)] * 7
    assert question_distribution(MCQ, 0, at)['popular_wrong'] == 0
    # 3 nəfər, amma 3/11 < 30 % → yox
    assert question_distribution(MCQ, 0, at + [att(2)])['popular_wrong'] is None
    # 2 nəfər (kiçik sinif, 2/4 = 50 %) → 3-dən az, yox
    assert question_distribution(MCQ, 0, [att(1), att(1), att(2), att(2)])['popular_wrong'] is None
    # düzgün variant heç vaxt «populyar səhv» deyil
    assert question_distribution(MCQ, 0, [att(2)] * 5)['popular_wrong'] is None
    # iki namizəddən çoxu seçilən götürülür
    at2 = [att(0)] * 3 + [att(1)] * 4 + [att(2)] * 3
    assert question_distribution(MCQ, 0, at2)['popular_wrong'] == 1


def test_invalid_answer_counts_as_empty():
    d = question_distribution(MCQ, 0, [att(9), att('abc'), att(None)])
    assert d['counts'] == [0] * 5 and d['empty'] == 3
