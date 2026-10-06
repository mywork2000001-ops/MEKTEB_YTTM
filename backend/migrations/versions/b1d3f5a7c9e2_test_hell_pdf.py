"""testdə şagirdin həll şəkilləri – bir PDF

Revision ID: b1d3f5a7c9e2
Revises: a9c3e5f7b1d2
Create Date: 2026-10-06 16:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b1d3f5a7c9e2'
down_revision: Union[str, Sequence[str], None] = 'a9c3e5f7b1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    cols = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('task_attempts')}
    with op.batch_alter_table('task_attempts') as b:
        if 'solution_key' not in cols:
            b.add_column(sa.Column('solution_key', sa.String(200), nullable=True))
        if 'solution_size' not in cols:
            b.add_column(sa.Column('solution_size', sa.Integer(), nullable=True))
        if 'solution_at' not in cols:
            b.add_column(sa.Column('solution_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('task_attempts') as b:
        b.drop_column('solution_at')
        b.drop_column('solution_size')
        b.drop_column('solution_key')
