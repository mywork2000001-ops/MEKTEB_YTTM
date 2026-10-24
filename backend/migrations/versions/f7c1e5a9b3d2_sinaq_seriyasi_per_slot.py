"""Sınaq seriyası: exam_series.per_slot (yuvada sınaq sayı) və newest_first (yenidən köhnəyə) – yalnız nullable sütunlar.

Revision ID: f7c1e5a9b3d2
Revises: e6b0d4f8a2c5
Create Date: 2026-10-24 18:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f7c1e5a9b3d2'
down_revision: Union[str, Sequence[str], None] = 'e6b0d4f8a2c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('exam_series', sa.Column('per_slot', sa.Integer(), nullable=True))
    op.add_column('exam_series', sa.Column('newest_first', sa.Boolean(), nullable=True))
    op.add_column('task_attempts', sa.Column('answers_released_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('task_attempts') as b:
        b.drop_column('answers_released_at')
    with op.batch_alter_table('exam_series') as b:
        b.drop_column('newest_first')
        b.drop_column('per_slot')
