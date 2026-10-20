"""users.guide_seen_version – şagird giriş videosunu hansı versiyada görüb (yalnız ADD COLUMN)

Revision ID: a1c5e9b3d7f2
Revises: 6c3e8a1d5f92
Create Date: 2026-10-20 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1c5e9b3d7f2'
down_revision: Union[str, Sequence[str], None] = '6c3e8a1d5f92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    cols = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('users')}
    if 'guide_seen_version' not in cols:
        with op.batch_alter_table('users') as b:
            b.add_column(sa.Column('guide_seen_version', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('users') as b:
        b.drop_column('guide_seen_version')
