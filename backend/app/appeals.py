"""Sualın bank ünvanı (variantda dondurulur) və apelyasiya məntiqi: qəbul olunmuş apelyasiyalar skanın qiymətləndirilməsinə təsir edir
(exam_scans.apply) – ona görə «Yenilə» və ya təkrar skan qəbul olunmuş düzəlişi silmir."""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import BankFile, BankQuestion, ExamAppeal


def bank_ref(db: Session, q: dict) -> dict | None:
    """Sualın bank ünvanı: {text: «altmövzu · №n · B<id>», file_id, n, qid, bank_id}; şablon sualı: «altmövzu · şablon <id>»."""
    bid = q.get('bank_id')
    if bid:
        bq = db.get(BankQuestion, bid)
        if bq is not None:
            f = db.get(BankFile, bq.file_id)
            label = (f.label if f else None) or q.get('lesson') or ''
            return {'text': f'{label} · №{bq.n} · B{bid}', 'file_id': bq.file_id, 'n': bq.n, 'qid': bq.qid, 'bank_id': bid}
        return {'text': f'{q.get("lesson") or ""} · B{bid}', 'file_id': None, 'n': None, 'qid': None, 'bank_id': bid}
    if q.get('template'):
        return {'text': f'{q.get("lesson") or q.get("topic") or ""} · şablon {q["template"]}', 'file_id': None, 'n': None, 'qid': None, 'bank_id': None}
    return None


def freeze_refs(db: Session, qs: list[dict]) -> list[dict]:
    """Variant yaradılanda / sual dəyişəndə ünvan dondurulur – bank sonra dəyişsə də apelyasiyada köhnə ünvan qalır."""
    out = []
    for q in qs:
        if q.get('ref') is None:
            r = bank_ref(db, q)
            q = {**q, 'ref': r} if r else q
        out.append(q)
    return out


def ref_of(db: Session, q: dict) -> dict | None:
    """Dondurulmuş ünvan; köhnə variantlarda – oxuyanda hesablanır."""
    return q.get('ref') or bank_ref(db, q)


def norm(v) -> str:
    return re.sub(r'\s+', '', str(v or '')).lower().replace(',', '.')


def accepted_slots(db: Session, exam_id: int, student_id: int, source: str, questions: list[dict], read: dict[int, str]) -> set[int]:
    """Bu şagirdin skanında qəbul olunmuş apelyasiyalar: öz apelyasiyası (slot) + «hamıya tətbiq et» (eyni bank sualı və eyni cavab)."""
    rows = list(db.scalars(select(ExamAppeal).where(ExamAppeal.exam_id == exam_id, ExamAppeal.status == 'accepted')))
    acc = {a.slot for a in rows if a.student_id == student_id and a.source == source}
    for a in rows:
        if not (a.apply_all and a.bank_id):
            continue
        for q in questions:
            if q.get('bank_id') == a.bank_id and norm(read.get(q['slot'])) == norm(a.my_answer) and norm(a.my_answer):
                acc.add(q['slot'])
    return acc


def apply_accepted(g: dict, questions: list[dict], acc: set[int], void: set[int]) -> dict:
    """grade() nəticəsində qəbul olunmuş slotlar düz sayılır; bal eyni düsturla (ləğv olunmuşlar çıxılır, 100-ə miqyas)."""
    qs = sorted(questions, key=lambda q: q['slot'])
    marks = [1 if (m or (q['slot'] in acc and q['slot'] not in void)) else 0 for q, m in zip(qs, g['marks'])]
    total = sum(q['points'] for q in qs if q['slot'] not in void) or 1
    full = sum(q['points'] for q in qs) or 100
    pts = sum(q['points'] for q, m in zip(qs, marks) if m)
    return {**g, 'marks': marks, 'points': round(pts * full / total, 2)}
