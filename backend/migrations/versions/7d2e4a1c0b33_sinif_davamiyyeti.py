"""sinif rehberi davamiyyeti

Revision ID: 7d2e4a1c0b33
Revises: 5b1c0e7a9d21
Create Date: 2026-09-29 21:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '7d2e4a1c0b33'
down_revision: Union[str, Sequence[str], None] = '5b1c0e7a9d21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('class_lessons',
                    sa.Column('class_id', sa.Integer(), nullable=False),
                    sa.Column('weekday', sa.Integer(), nullable=False),
                    sa.Column('period', sa.Integer(), nullable=False),
                    sa.Column('subject', sa.String(length=80), nullable=False),
                    sa.Column('teacher', sa.String(length=120), nullable=True),
                    sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('class_id', 'weekday', 'period'))
    op.create_table('homeroom_attendance',
                    sa.Column('class_id', sa.Integer(), nullable=False),
                    sa.Column('date', sa.Date(), nullable=False),
                    sa.Column('period', sa.Integer(), nullable=False),
                    sa.Column('student_id', sa.Integer(), nullable=False),
                    sa.Column('status', sa.String(length=10), nullable=False),
                    sa.Column('reason', sa.String(length=120), nullable=True),
                    sa.Column('marked_by', sa.Integer(), nullable=True),
                    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
                    sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ondelete='CASCADE'),
                    sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
                    sa.ForeignKeyConstraint(['marked_by'], ['users.id']),
                    sa.PrimaryKeyConstraint('class_id', 'date', 'period', 'student_id'))


def downgrade() -> None:
    op.drop_table('homeroom_attendance')
    op.drop_table('class_lessons')
