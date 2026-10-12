"""100 ballıq sistem: cəhdin balı (task_attempts.points), bank sualının statistikası və avtomatik çətinliyi.

Revision ID: c6e8a0b2d4f7
Revises: b3c5d7e9f1a2
Create Date: 2026-10-12 20:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c6e8a0b2d4f7'
down_revision: Union[str, Sequence[str], None] = 'b3c5d7e9f1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('task_attempts', schema=None) as b:
        b.add_column(sa.Column('points', sa.Float(), nullable=True))      # köhnə cəhd – boş (düz ÷ ümumi)
    with op.batch_alter_table('bank_questions', schema=None) as b:
        b.add_column(sa.Column('diff_auto', sa.String(length=6), nullable=True))
        b.add_column(sa.Column('stat_n', sa.Integer(), nullable=True))
        b.add_column(sa.Column('stat_ok', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('bank_questions', schema=None) as b:
        b.drop_column('stat_ok')
        b.drop_column('stat_n')
        b.drop_column('diff_auto')
    with op.batch_alter_table('task_attempts', schema=None) as b:
        b.drop_column('points')
