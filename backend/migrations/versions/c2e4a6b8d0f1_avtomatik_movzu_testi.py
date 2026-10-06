"""sinif/qrup: hər plan dərsinə avtomatik mövzu testi

Revision ID: c2e4a6b8d0f1
Revises: b1d3f5a7c9e2
Create Date: 2026-10-06 17:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c2e4a6b8d0f1'
down_revision: Union[str, Sequence[str], None] = 'b1d3f5a7c9e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    cols = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('teaching_assignments')}
    if 'auto_tests' not in cols:
        with op.batch_alter_table('teaching_assignments') as b:
            b.add_column(sa.Column('auto_tests', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table('teaching_assignments') as b:
        b.drop_column('auto_tests')
