"""şagird məktəbdən gedib: səbəb və tarix (passiv)

Revision ID: f2a9c4e6b8d1
Revises: e7f1b3c5d9a2
Create Date: 2026-09-30 13:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f2a9c4e6b8d1'
down_revision: Union[str, Sequence[str], None] = 'e7f1b3c5d9a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('students') as b:
        b.add_column(sa.Column('left_reason', sa.String(length=300), nullable=True))
        b.add_column(sa.Column('left_on', sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('students') as b:
        b.drop_column('left_on')
        b.drop_column('left_reason')
