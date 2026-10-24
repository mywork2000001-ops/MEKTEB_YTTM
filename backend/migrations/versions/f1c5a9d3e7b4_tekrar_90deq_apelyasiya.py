"""Sınaqda imtahandan çıxma sayğacı (task_attempts.focus_log) və sınaq apelyasiyaları (task_appeals).

Revision ID: f1c5a9d3e7b4
Revises: f7c1e5a9b3d2
Create Date: 2026-10-24 16:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f1c5a9d3e7b4'
down_revision: Union[str, Sequence[str], None] = 'f7c1e5a9b3d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('task_attempts', sa.Column('focus_log', sa.JSON(), nullable=True))
    op.create_table(
        'task_appeals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('online_tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id', ondelete='CASCADE'), nullable=False),
        sa.Column('q_index', sa.Integer(), nullable=False),
        sa.Column('bank_id', sa.Integer(), nullable=True),
        sa.Column('q', sa.JSON(), nullable=True),
        sa.Column('my_answer', sa.Text(), nullable=True),
        sa.Column('correct_at_time', sa.Text(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('teacher_reply', sa.Text(), nullable=True),
        sa.Column('apply_all', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('decided_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('task_id', 'student_id', 'q_index'),
    )
    op.create_index('ix_task_appeals_task_id', 'task_appeals', ['task_id'])


def downgrade() -> None:
    op.drop_index('ix_task_appeals_task_id', table_name='task_appeals')
    op.drop_table('task_appeals')
    with op.batch_alter_table('task_attempts') as b:
        b.drop_column('focus_log')
