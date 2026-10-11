"""Test bazası faylının (sınağın) keçirilmə tarixi: held_on + dəqiqlik (day | month | year) – etiketdən çıxarılır.

Revision ID: d4f6a8c0e2b4
Revises: c3e5a7b9d1f2
Create Date: 2026-10-12 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd4f6a8c0e2b4'
down_revision: Union[str, Sequence[str], None] = 'c3e5a7b9d1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('bank_files', schema=None) as batch_op:
        batch_op.add_column(sa.Column('held_on', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('held_prec', sa.String(length=5), nullable=True))
    # mövcud fayllar – etiketdən (sonrakı sinxronizasiya da yeniləyir)
    from app.bank.classify import held_from_label
    bind = op.get_bind()
    for fid, label in bind.execute(sa.text('SELECT id, label FROM bank_files')).fetchall():
        d, p = held_from_label(label or '')
        if d:
            bind.execute(sa.text('UPDATE bank_files SET held_on = :d, held_prec = :p WHERE id = :i'), {'d': d, 'p': p, 'i': fid})


def downgrade() -> None:
    with op.batch_alter_table('bank_files', schema=None) as batch_op:
        batch_op.drop_column('held_prec')
        batch_op.drop_column('held_on')
