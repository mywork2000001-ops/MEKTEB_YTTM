"""KSQ/BSQ cavab kartı: QR məzmunu (HMAC imzalı – saxta kart rədd edilir) və kart quruluşu (docs/ksq-bsq-kagiz-promtu.md §3).

QR: «MK1|exam_id|student_id|code|imza» — imza = HMAC-SHA256(secret_key, «exam|student|code») ilk 10 simvolu (base32)."""
from __future__ import annotations

import base64
import hashlib
import hmac

from ..config import settings

PREFIX = 'MK1'
MCQ_LETTERS = 'ABCDE'


def _sig(exam_id: int, student_id: int, code: str) -> str:
    d = hmac.new(settings().secret_key.encode(), f'ksq|{exam_id}|{student_id}|{code}'.encode(), hashlib.sha256).digest()
    return base64.b32encode(d).decode()[:10]


def qr_payload(exam_id: int, student_id: int, code: str) -> str:
    return f'{PREFIX}|{exam_id}|{student_id}|{code}|{_sig(exam_id, student_id, code)}'


def parse_qr(s: str) -> dict | None:
    """Kartdan oxunmuş QR → {exam_id, student_id, code}; format və ya imza səhvdirsə – None."""
    p = (s or '').strip().split('|')
    if len(p) != 5 or p[0] != PREFIX or not p[1].isdigit() or not p[2].isdigit():
        return None
    e, st, code, sig = int(p[1]), int(p[2]), p[3], p[4]
    if not hmac.compare_digest(sig, _sig(e, st, code)):
        return None
    return {'exam_id': e, 'student_id': st, 'code': code}


def pick_lang(x, lang: str) -> str:
    if isinstance(x, dict):
        return x.get(lang) or x.get('az') or next((v for v in x.values() if v), '')
    return str(x or '')


def key_value(q: dict) -> str:
    """Müəllim açarı: test – hərf, açıq – kartda yazılacaq cavab."""
    from .ksq_variants import card_answer
    if q.get('kind') == 'mcq' and q.get('correct') is not None:
        return MCQ_LETTERS[int(q['correct'])]
    return card_answer(q.get('answer')) or str(q.get('answer') or '')


def variant_rev(questions: list[dict]) -> str:
    """Variantın «barmaq izi»: slot · sual · düzgün cavab. Çapdan sonra sual/açar dəyişsə – dəyişir, köhnə kart qəbul olunmur."""
    import json
    # açar çapdan sonra düzəldilibsə – kağız dəyişməyib: çap anındakı qiymət (rev_*) – köhnə kart keçərlidir
    raw = json.dumps(sorted([q.get('slot'), q.get('key'), q.get('rev_correct', q.get('correct')), q.get('rev_answer', q.get('answer'))]
                            for q in questions), ensure_ascii=False, default=str)
    return hashlib.sha1(raw.encode()).hexdigest()[:6]


def split_code(code: str) -> tuple[str, str | None]:
    """«KSQ1-03~a1b2c3» → ('KSQ1-03', 'a1b2c3'); köhnə kartlarda versiya yoxdur."""
    base, _, rev = (code or '').partition('~')
    return base, rev or None
