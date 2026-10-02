"""sınaq imtahanı: bank faylının növü/sinfi, cərimə, açıq sual düzəlişi

Revision ID: e2f6a8b1c4d7
Revises: d1e4f7a2b8c3
Create Date: 2026-10-04 23:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e2f6a8b1c4d7'
down_revision: Union[str, Sequence[str], None] = 'd1e4f7a2b8c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.bank.classify import classify
    with op.batch_alter_table('bank_files') as b:
        b.add_column(sa.Column('kind', sa.String(length=12), nullable=False, server_default='movzu'))
        b.add_column(sa.Column('grades', sa.JSON(), nullable=True))
        b.add_column(sa.Column('subject', sa.String(length=60), nullable=True))
        b.add_column(sa.Column('meta_locked', sa.Boolean(), nullable=False, server_default=sa.false()))
    conn = op.get_bind()
    upd = sa.text('UPDATE bank_files SET kind = :k, grades = :g, subject = :s WHERE id = :i').bindparams(
        sa.bindparam('g', type_=sa.JSON()))                                   # Postgres: json tipi ilə
    for fid, src, label in conn.execute(sa.text('SELECT id, source_key, label FROM bank_files')).all():
        c = classify(src, label or '')
        conn.execute(upd, {'k': c['kind'], 'g': c['grades'], 's': c['subject'], 'i': fid})
    with op.batch_alter_table('test_batches') as b:
        b.add_column(sa.Column('penalty', sa.Integer(), nullable=False, server_default='0'))
    with op.batch_alter_table('task_attempts') as b:
        b.add_column(sa.Column('manual', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('task_attempts') as b:
        b.drop_column('manual')
    with op.batch_alter_table('test_batches') as b:
        b.drop_column('penalty')
    with op.batch_alter_table('bank_files') as b:
        for c in ('meta_locked', 'subject', 'grades', 'kind'):
            b.drop_column(c)
