"""şagirdin öz telefonu

Revision ID: c9d3e4f5a6b7
Revises: b7c1d2e3f4a5
Create Date: 2026-10-01 14:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c9d3e4f5a6b7'
down_revision: Union[str, Sequence[str], None] = 'b7c1d2e3f4a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('students') as b:
        b.add_column(sa.Column('phone', sa.String(length=30), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('students') as b:
        b.drop_column('phone')
