"""Test qrupları: eyni testin təkrar göndərişləri (alt-qruplara «Yenidən göndər») bir qrupda birləşir.

Qrup açarı: sınaq – (təyinat, 'sinaq', batch_id), batch_id yoxdursa sual imzası; digərləri – (təyinat, növ, plan_lesson_id,
sual imzası). Sual imzası = sıralı bank_id-lər (bank_id yoxdursa sualın mətninin sha1-i): eyni suallı yenidən göndəriş bir qrupdur,
eyni mövzuya fərqli suallı test ayrı qalır. Funksiya saf Python-dur (DB-yə toxunmur) – /api/tasks/mine və /api/paper-exams/{ta}/sources
eyni məntiqi işlədir."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable

_ROMAN = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6, 'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10, 'XI': 11}
_GRADE_RE = re.compile(r'\(\s*(?:(XI|X|IX|VIII|VII|VI|V|IV|III|II|I)|(\d{1,2}))\s*-?\s*(?:ci|cı|cu|cü|inci|ıncı|uncu|üncü)?\s+sinif',
                       re.IGNORECASE)


def grade_hint(title: str | None) -> int | None:
    """Başlıqdakı «(IX sinif …)» / «(9-cu sinif …)» göstəricisi → sinif rəqəmi (1–11), yoxdursa None."""
    m = _GRADE_RE.search(title or '')
    if not m:
        return None
    g = _ROMAN.get(m.group(1).upper()) if m.group(1) else int(m.group(2))
    return g if g and 1 <= g <= 11 else None


def question_signature(task: Any) -> str:
    """Sıralı sual imzası: bank_id (yoxdursa mətnin sha1-i) – eyni suallı surətlər eyni imza verir."""
    parts = []
    for q in (task.questions or []):
        if not isinstance(q, dict):
            parts.append('?')
        elif q.get('bank_id'):
            parts.append(f'b{q["bank_id"]}')
        else:
            parts.append('h' + hashlib.sha1(json.dumps(q.get('text'), sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12])
    return ','.join(parts)


def group_key(task: Any) -> tuple:
    if task.kind == 'sinaq':
        return (task.assignment_id, 'sinaq', task.batch_id if task.batch_id else question_signature(task))
    return (task.assignment_id, task.kind or '', task.plan_lesson_id, question_signature(task))


def key_str(key: tuple) -> str:
    return 'g' + hashlib.sha1(repr(key).encode()).hexdigest()[:12]


def group_tasks(tasks: Iterable[Any], *, submitted: dict[int, int] | None = None, seqs: dict[int, int] | None = None,
                paper_task_ids: set[int] | None = None, roster_n: dict[int, int] | None = None) -> list[dict]:
    """Tapşırıqları qruplara ayırır (birinci rast gələn qrup birinci). tasks: id, opens_at, student_ids, kind, batch_id,
    plan_lesson_id, assignment_id, questions, title atributlu obyektlər. submitted {task_id: təhvil}, seqs {plan_lesson_id: №},
    paper_task_ids – yazılı işi olan tapşırıqlar, roster_n {assignment_id: sinif şagird sayı} (students_n üçün)."""
    submitted, seqs, paper_task_ids, roster_n = submitted or {}, seqs or {}, paper_task_ids or set(), roster_n or {}
    buckets: dict[tuple, list] = {}
    for t in tasks:
        buckets.setdefault(group_key(t), []).append(t)
    out = []
    for key, ts in buckets.items():
        ts = sorted(ts, key=lambda t: (t.opens_at, t.id))
        main = next((t for t in ts if t.student_ids is None), ts[0])
        everyone = any(t.student_ids is None for t in ts)
        union = sorted({s for t in ts for s in (t.student_ids or [])})
        ids = [t.id for t in ts]
        out.append({
            'group_key': key_str(key), 'main_task_id': main.id, 'task_ids': ids, 'sends': len(ts),
            'students': 'all' if everyone else len(union),
            'students_n': roster_n.get(main.assignment_id) if everyone else len(union),
            'student_ids': None if everyone else union,
            'submitted': sum(submitted.get(i, 0) for i in ids),
            'first_opens_at': ts[0].opens_at, 'last_opens_at': ts[-1].opens_at,
            'title': main.title, 'kind': main.kind, 'assignment_id': main.assignment_id,
            'seq': seqs.get(main.plan_lesson_id) if main.plan_lesson_id else None,
            'grade_hint': grade_hint(main.title),
            'has_paper': any(i in paper_task_ids for i in ids),
        })
    return out
