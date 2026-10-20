"""missing_notes, missing_requests – işlənməyənlər hesabatı (yalnız YENİ cədvəllər)

Revision ID: b2d6f0a4c8e1
Revises: a1c5e9b3d7f2
Create Date: 2026-10-20 21:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b2d6f0a4c8e1'
down_revision: Union[str, Sequence[str], None] = 'a1c5e9b3d7f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    have = set(sa.inspect(op.get_bind()).get_table_names())
    if 'missing_notes' not in have:
        op.create_table(
            'missing_notes',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('ta_id', sa.Integer(), sa.ForeignKey('teaching_assignments.id', ondelete='CASCADE'), nullable=False),
            sa.Column('task_key', sa.String(40), nullable=False),
            sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id', ondelete='CASCADE'), nullable=False),
            sa.Column('reason', sa.String(12), nullable=False),
            sa.Column('note', sa.Text(), nullable=True),
            sa.Column('teacher_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint('ta_id', 'task_key', 'student_id', name='uq_missing_note'))
        op.create_index('ix_missing_notes_ta_id', 'missing_notes', ['ta_id'])
    if 'missing_requests' not in have:
        op.create_table(
            'missing_requests',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('ta_id', sa.Integer(), sa.ForeignKey('teaching_assignments.id', ondelete='CASCADE'), nullable=False),
            sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id', ondelete='CASCADE'), nullable=False),
            sa.Column('task_keys', sa.JSON(), nullable=True),
            sa.Column('message', sa.Text(), nullable=True),
            sa.Column('new_deadline', sa.DateTime(timezone=True), nullable=True),
            sa.Column('reopened', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('message_id', sa.Integer(), nullable=True),
            sa.Column('teacher_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
        op.create_index('ix_missing_requests_ta_id', 'missing_requests', ['ta_id'])


def downgrade() -> None:
    op.drop_table('missing_requests')
    op.drop_table('missing_notes')
