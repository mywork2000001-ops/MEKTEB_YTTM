"""sonradan yazdi

Revision ID: 5b1c0e7a9d21
Revises: 26daf263d49f
Create Date: 2026-09-29 20:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5b1c0e7a9d21'
down_revision: Union[str, Sequence[str], None] = '26daf263d49f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('exam_scores', schema=None) as batch_op:
        batch_op.add_column(sa.Column('taken_on', sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('exam_scores', schema=None) as batch_op:
        batch_op.drop_column('taken_on')
