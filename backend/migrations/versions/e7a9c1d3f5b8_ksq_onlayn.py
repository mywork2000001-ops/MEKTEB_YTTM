"""online_tasks.exam_id – KSQ/BSQ onlayn: şagirdin öz variantı onlayn test kimi (13.10.2026).

Revision ID: e7a9c1d3f5b8
Revises: b2d4f6a8c0e1
Create Date: 2026-10-13 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e7a9c1d3f5b8'
down_revision: Union[str, Sequence[str], None] = 'b2d4f6a8c0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('online_tasks') as b:
        b.add_column(sa.Column('exam_id', sa.Integer(), nullable=True))
        b.create_foreign_key('fk_online_tasks_exam_id', 'exams', ['exam_id'], ['id'], ondelete='CASCADE')
        b.create_index('ix_online_tasks_exam_id', ['exam_id'])


def downgrade() -> None:
    with op.batch_alter_table('online_tasks') as b:
        b.drop_index('ix_online_tasks_exam_id')
        b.drop_constraint('fk_online_tasks_exam_id', type_='foreignkey')
        b.drop_column('exam_id')
