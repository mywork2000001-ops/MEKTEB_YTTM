"""mövzu icrası: keçilən mövzuların əl ilə qeydi (irəliləyiş / geriləmə)

Revision ID: b7c1d2e3f4a5
Revises: f2a9c4e6b8d1
Create Date: 2026-10-01 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b7c1d2e3f4a5'
down_revision: Union[str, Sequence[str], None] = 'f2a9c4e6b8d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'topic_progress',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('assignment_id', sa.Integer(), sa.ForeignKey('teaching_assignments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('plan_lesson_id', sa.Integer(), sa.ForeignKey('plan_lessons.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('done_on', sa.Date(), nullable=False),
        sa.Column('note', sa.String(length=300), nullable=True),
        sa.Column('updated_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('assignment_id', 'plan_lesson_id', name='uq_topic_progress'),
    )


def downgrade() -> None:
    op.drop_table('topic_progress')
