"""köhnə sınaqlar: yeniləmədən əvvəl adi tapşırıq kimi göndərilən sınaqlar «Sınaq imtahanları»na köçür;
silinmiş (arxivdəki) sınaqlar sistemdən tam silinir

Sınaq sayılır: tapşırığın test bazası suallarının yarıdan çoxu sınaq/yekun faylındandır və ya adı sınaq kimidir
(bank/classify.py). Eyni müəllimin eyni adlı və eyni suallı testləri (müxtəlif siniflər) bir sınaq paketi olur –
siniflər müqayisə olunur və ümumi reytinqə düşür.

Revision ID: c6d1e3f5a8b2
Revises: b5c9d2e4f7a1
Create Date: 2026-10-03 12:00:00

"""
import datetime as dt
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c6d1e3f5a8b2'
down_revision: Union[str, Sequence[str], None] = 'b5c9d2e4f7a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EXAM_KINDS = ('sinaq', 'yekun')


def _js(v):
    return json.loads(v) if isinstance(v, str) else (v or [])


def upgrade() -> None:
    from app.bank.classify import _SINAQ, classify
    from app.domain.classes import grade_of
    conn = op.get_bind()

    # 1) köhnə sınaqları tanı
    rows = conn.execute(sa.text('SELECT id, assignment_id, title, questions, created_by, created_at FROM online_tasks '
                                'WHERE kind IS NULL AND batch_id IS NULL')).all()
    tasks = [(r[0], r[1], r[2], _js(r[3]), r[4], r[5]) for r in rows]
    bank_ids = {q['bank_id'] for t in tasks for q in t[3] if isinstance(q, dict) and q.get('bank_id')}
    fkind = {}
    if bank_ids:
        st = sa.text('SELECT q.id, f.kind FROM bank_questions q JOIN bank_files f ON f.id = q.file_id '
                     'WHERE q.id IN :ids').bindparams(sa.bindparam('ids', expanding=True))
        fkind = dict(conn.execute(st, {'ids': list(bank_ids)}).all())
    groups: dict[tuple, list] = {}
    for tid, ta_id, title, qs, by, created in tasks:
        qs = [q for q in qs if isinstance(q, dict)]
        from_bank = [q for q in qs if q.get('bank_id') or q.get('source') not in (None, '', 'müəllim')]
        exam = sum(1 for q in from_bank
                   if (fkind.get(q.get('bank_id')) or classify(q.get('source') or '', q.get('lesson') or '')['kind'])
                   in EXAM_KINDS)
        if not ((from_bank and exam * 2 > len(from_bank)) or _SINAQ.search(title or '')):
            continue
        sig = tuple(sorted(str(q.get('bank_id') or json.dumps(q.get('text'), sort_keys=True)) for q in qs))
        groups.setdefault((by, (title or '').strip().lower(), sig), []).append((tid, ta_id, title, created))

    # 2) hər qrupa sınaq paketi
    ins = sa.text('INSERT INTO test_batches (kind, title, subject, grade, penalty, created_by, created_at) '
                  "VALUES ('sinaq', :t, :s, :g, 0, :by, :at) RETURNING id")
    for (by, _, _), items in groups.items():
        tid0, ta0, title, _ = items[0]
        subj, cname, cutis, cgrade = conn.execute(sa.text(
            'SELECT ta.subject, c.name, c.utis_class, c.grade FROM teaching_assignments ta '
            'JOIN classes c ON c.id = ta.class_id WHERE ta.id = :i'), {'i': ta0}).one()
        at = min((x[3] for x in items if x[3] is not None), default=None) or dt.datetime.now(dt.timezone.utc)
        bid = conn.execute(ins, {'t': (title or 'Sınaq')[:200], 's': subj, 'g': cgrade or grade_of(cname, cutis),
                                 'by': by, 'at': at}).scalar_one()
        for tid, *_ in items:
            conn.execute(sa.text("UPDATE online_tasks SET kind = 'sinaq', batch_id = :b WHERE id = :i"),
                         {'b': bid, 'i': tid})

    # 3) silinmiş sınaqlar – tam silinir (cəhdlər də); boş qalan sınaq paketləri də
    gone = [r[0] for r in conn.execute(sa.text(
        "SELECT id FROM online_tasks WHERE kind = 'sinaq' AND archived_at IS NOT NULL")).all()]
    if gone:
        p = {'ids': gone}
        exp = lambda q: sa.text(q).bindparams(sa.bindparam('ids', expanding=True))   # noqa: E731
        conn.execute(exp('DELETE FROM task_attempts WHERE task_id IN :ids'), p)
        conn.execute(exp('UPDATE marks SET task_id = NULL WHERE task_id IN :ids'), p)
        conn.execute(exp('DELETE FROM online_tasks WHERE id IN :ids'), p)
    conn.execute(sa.text("DELETE FROM test_batches WHERE kind = 'sinaq' AND NOT EXISTS "
                         '(SELECT 1 FROM online_tasks t WHERE t.batch_id = test_batches.id) AND NOT EXISTS '
                         '(SELECT 1 FROM extra_sessions e WHERE e.batch_id = test_batches.id)'))


def downgrade() -> None:
    pass                                           # silinən geri gəlmir; köçürülən sınaqlar sınaq olaraq qalır
