"""gundelik plan (ARTİ) və müəllimin AI açarı

Revision ID: 9a4f6c2e1d55
Revises: 7d2e4a1c0b33
Create Date: 2026-09-29 23:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '9a4f6c2e1d55'
down_revision: Union[str, Sequence[str], None] = '7d2e4a1c0b33'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users') as b:
        b.add_column(sa.Column('ai_settings', sa.JSON(), nullable=True))
    op.create_table('daily_plans',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('assignment_id', sa.Integer(), nullable=False),
                    sa.Column('date', sa.Date(), nullable=False),
                    sa.Column('period', sa.Integer(), nullable=False),
                    sa.Column('plan_lesson_id', sa.Integer(), nullable=True),
                    sa.Column('topic', sa.Text(), nullable=False),
                    sa.Column('content', sa.JSON(), nullable=False),
                    sa.Column('notes', sa.Text(), nullable=True),
                    sa.Column('provider', sa.String(length=30), nullable=True),
                    sa.Column('model', sa.String(length=120), nullable=True),
                    sa.Column('edited', sa.Boolean(), nullable=False, server_default=sa.false()),
                    sa.Column('created_by', sa.Integer(), nullable=True),
                    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
                    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
                    sa.ForeignKeyConstraint(['assignment_id'], ['teaching_assignments.id'], name='fk_daily_plans_ta',
                                            ondelete='CASCADE'),
                    sa.ForeignKeyConstraint(['plan_lesson_id'], ['plan_lessons.id'], name='fk_daily_plans_pl',
                                            ondelete='SET NULL'),
                    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='fk_daily_plans_user'),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('assignment_id', 'date', 'period', name='uq_daily_plan_slot'))


def downgrade() -> None:
    op.drop_table('daily_plans')
    with op.batch_alter_table('users') as b:
        b.drop_column('ai_settings')
