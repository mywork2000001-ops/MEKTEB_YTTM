"""Sınaq seriyası: başqa sinfin / sinifsiz sınaqlar yalnız müəllimin təsdiqi ilə (other_ok – təsdiqlənmiş fayllar).

Revision ID: c3e5a7b9d1f2
Revises: b8d2f4a6c9e1
Create Date: 2026-10-06 21:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c3e5a7b9d1f2'
down_revision: Union[str, Sequence[str], None] = 'b8d2f4a6c9e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('exam_series', schema=None) as batch_op:
        batch_op.add_column(sa.Column('other_ok', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('exam_series', schema=None) as batch_op:
        batch_op.drop_column('other_ok')
