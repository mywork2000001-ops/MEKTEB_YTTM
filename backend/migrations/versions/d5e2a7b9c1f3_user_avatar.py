"""istifadəçinin çat şəkli (avatar)

Revision ID: d5e2a7b9c1f3
Revises: c3d8e1f2a4b6
Create Date: 2026-09-30 11:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd5e2a7b9c1f3'
down_revision: Union[str, Sequence[str], None] = 'c3d8e1f2a4b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users') as b:
        b.add_column(sa.Column('avatar', sa.LargeBinary(), nullable=True))
        b.add_column(sa.Column('avatar_type', sa.String(length=20), nullable=True))
        b.add_column(sa.Column('avatar_v', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('users') as b:
        b.drop_column('avatar_v')
        b.drop_column('avatar_type')
        b.drop_column('avatar')
