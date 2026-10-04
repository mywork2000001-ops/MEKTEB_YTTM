"""qrupun kurs müddəti: teaching_assignments.starts_on / ends_on

Revision ID: a3c5e7f9b1d2
Revises: e1f5b8c3a9d2
Create Date: 2026-10-04 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a3c5e7f9b1d2'
down_revision: Union[str, Sequence[str], None] = 'e1f5b8c3a9d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('teaching_assignments') as b:
        b.add_column(sa.Column('starts_on', sa.Date(), nullable=True))
        b.add_column(sa.Column('ends_on', sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('teaching_assignments') as b:
        b.drop_column('ends_on')
        b.drop_column('starts_on')
