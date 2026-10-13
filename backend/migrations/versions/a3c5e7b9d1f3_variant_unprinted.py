"""exam_variants.unprinted – köhnə çapda kağıza düşməyən suallar (təxmin), təzə skanlarda avtomatik ⊘
(docs/kagiza-dusmeyen-avtomatik-promtu.md).

Revision ID: a3c5e7b9d1f3
Revises: f9b1d3e5a7c9
Create Date: 2026-10-13 22:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a3c5e7b9d1f3'
down_revision: Union[str, Sequence[str], None] = 'f9b1d3e5a7c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('exam_variants') as b:
        b.add_column(sa.Column('unprinted', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('exam_variants') as b:
        b.drop_column('unprinted')
