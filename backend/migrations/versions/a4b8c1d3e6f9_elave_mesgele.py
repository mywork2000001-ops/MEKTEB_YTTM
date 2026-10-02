"""əlavə məşğələ: kurs, məşğələlər (perspektiv plan), davamiyyət

Revision ID: a4b8c1d3e6f9
Revises: f3a7b9c2d5e8
Create Date: 2026-10-05 01:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a4b8c1d3e6f9'
down_revision: Union[str, Sequence[str], None] = 'f3a7b9c2d5e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'extra_courses',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('owner_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('school_id', sa.Integer(), sa.ForeignKey('schools.id'), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('subject', sa.String(length=60), nullable=False),
        sa.Column('format', sa.String(length=10), nullable=False),
        sa.Column('audience', sa.JSON(), nullable=False),
        sa.Column('schedule', sa.JSON(), nullable=False),
        sa.Column('starts_on', sa.Date(), nullable=False),
        sa.Column('ends_on', sa.Date(), nullable=False),
        sa.Column('goal', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        'extra_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('extra_courses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('start', sa.String(length=5), nullable=False),
        sa.Column('end', sa.String(length=5), nullable=False),
        sa.Column('format', sa.String(length=10), nullable=False),
        sa.Column('room', sa.String(length=60), nullable=True),
        sa.Column('link', sa.String(length=500), nullable=True),
        sa.Column('topics', sa.JSON(), nullable=True),
        sa.Column('goals', sa.Text(), nullable=True),
        sa.Column('resources', sa.Text(), nullable=True),
        sa.Column('homework', sa.Text(), nullable=True),
        sa.Column('batch_id', sa.Integer(), sa.ForeignKey('test_batches.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', sa.String(length=10), nullable=False, server_default='planned'),
        sa.Column('note', sa.String(length=300), nullable=True),
        sa.Column('recording_url', sa.String(length=500), nullable=True),
    )
    op.create_index('ix_extra_sessions_course', 'extra_sessions', ['course_id', 'date'])
    op.create_table(
        'extra_attendance',
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('extra_sessions.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('status', sa.String(length=10), nullable=True),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('extra_attendance')
    op.drop_index('ix_extra_sessions_course', 'extra_sessions')
    op.drop_table('extra_sessions')
    op.drop_table('extra_courses')
