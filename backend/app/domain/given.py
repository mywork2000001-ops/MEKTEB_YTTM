"""Sınaq təkrarsızlığı – şagird səviyyəsində (docs/tasks/sinaq-tekrarsiz-ve-davam-2026-10-24.md).

Şagird eyni sınağı (və ya eyni sualları olan başqa bank faylını) iki dəfə almasın: sinif, onun qrupu və fərdi tapşırıqlar
ayrı dərslər olsa da, şagirdin aid olduğu BÜTÜN dərslərdə verilmiş sınaqlar (arxivlənmişlər də) sayılır.
Seriya və əl ilə yaratma bu modulu çağırır; bank/sinif məntiqi `api/exams_online.py`-dədir (dairəvi import olmasın deyə tənbəl)."""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

SAME_RATIO = 0.8                       # sualların ≥ 80%-i eyni olan iki fayl «eyni sınaq» sayılır

_cache: dict = {'sig': None, 'same': {}}


def _norm(x) -> str:
    t = (x.get('az') or next(iter(x.values()), '')) if isinstance(x, dict) else (x or '')
    return re.sub(r'[\s$\\{}.,;:()]+', '', str(t)).lower()


def question_key(text, options=None) -> str:
    """Sualın məzmun heşi: kiçik hərf, boşluq/LaTeX boşluqları və variant sırası nəzərə alınmır."""
    opts = sorted(_norm(o.get('az') if isinstance(o, dict) and 'az' in o else o) for o in (options or []))
    return hashlib.sha1((_norm(text) + '|' + '|'.join(opts)).encode('utf-8')).hexdigest()


def same_map(db: Session) -> dict[int, set[int]]:
    """{fayl: eyni məzmunlu digər sınaq faylları}. Bank dəyişəndə (sual sayı / son id) yenidən hesablanır."""
    from ..models import BankFile, BankQuestion
    sig = (db.scalar(select(func.count(BankQuestion.id))), db.scalar(select(func.max(BankQuestion.id))),
           db.scalar(select(func.count(BankFile.id))))
    if _cache['sig'] == sig:
        return _cache['same']
    keys: dict[int, set[str]] = defaultdict(set)
    for fid, text, options in db.execute(select(BankQuestion.file_id, BankQuestion.text, BankQuestion.options)
                                         .join(BankFile, BankFile.id == BankQuestion.file_id)
                                         .where(BankQuestion.active.is_(True), BankFile.active.is_(True), BankFile.kind == 'sinaq')):
        k = question_key(text, options)
        keys[fid].add(k)
    inv: dict[str, set[int]] = defaultdict(set)
    for fid, ks in keys.items():
        for k in ks:
            inv[k].add(fid)
    out: dict[int, set[int]] = defaultdict(set)
    for fid, ks in keys.items():
        common: dict[int, int] = defaultdict(int)
        for k in ks:
            for g in inv[k]:
                if g != fid:
                    common[g] += 1
        for g, n in common.items():
            if n >= SAME_RATIO * max(len(ks), len(keys[g])):
                out[fid].add(g)
    _cache['sig'], _cache['same'] = sig, dict(out)
    return _cache['same']


def same_as(db: Session, file_id: int) -> set[int]:
    return set(same_map(db).get(file_id, ()))


def received(db: Session, student_ids) -> dict[int, set[int]]:
    """{şagird: aldığı sınaq fayllarının id-ləri (eyni məzmunlular da daxil)} – bütün dərslərdə, arxivlənmişlər də."""
    from ..api.exams_online import _full, _task_counts, _text_index
    from ..models import BankFile, OnlineTask, TeachingAssignment
    from ..services import roster
    want = set(student_ids)
    out: dict[int, set[int]] = {s: set() for s in want}
    if not want:
        return out
    tasks = list(db.scalars(select(OnlineTask).where(OnlineTask.kind == 'sinaq')))
    if not tasks:
        return out
    idx = _text_index(db)
    qn = {f.id: f.question_count for f in db.scalars(select(BankFile))}
    rost: dict[int, set[int]] = {}
    same = same_map(db)
    for t in tasks:
        if t.student_ids is not None:
            rec = set(t.student_ids) & want
        else:
            if t.assignment_id not in rost:
                ta = db.get(TeachingAssignment, t.assignment_id)
                rost[t.assignment_id] = {s.id for s in roster(db, ta)} if ta else set()
            rec = rost[t.assignment_id] & want
        if not rec:
            continue
        files = {fid for fid, n in _task_counts(db, t.questions or [], idx).items() if _full(n, qn.get(fid) or n)}
        files |= {g for f in files for g in same.get(f, ())}
        for s in rec:
            out[s] |= files
    return out


def given_students(db: Session, file_ids, student_ids) -> dict[int, set[int]]:
    """{fayl: bu sınağı (və ya eyni məzmunlusunu) artıq almış şagirdlər} – yalnız verilən şagirdlər arasından."""
    rec = received(db, student_ids)
    return {f: {s for s, fs in rec.items() if f in fs} for f in file_ids}
