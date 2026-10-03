"""perspektiv plan proqramları: kitabxana (plan_programs), sinif/qrupun əsas proqramı (teaching_assignments.program_id)
və əlavə proqramları (assignment_programs – səviyyə qrupu üçün də)

Revision ID: c4e9a2d7f1b3
Revises: b8d3f1a6c2e4
Create Date: 2026-10-03 23:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c4e9a2d7f1b3'
down_revision: Union[str, Sequence[str], None] = 'b8d3f1a6c2e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'plan_programs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('key', sa.String(60), unique=True, nullable=True),
        sa.Column('school_id', sa.Integer(), sa.ForeignKey('schools.id'), nullable=True),
        sa.Column('owner_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('subject', sa.String(60), nullable=False),
        sa.Column('grade', sa.Integer(), nullable=True),
        sa.Column('kind', sa.String(10), nullable=False),
        sa.Column('source', sa.String(300), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('weekly_hours', sa.Integer(), nullable=True),
        sa.Column('level', sa.String(10), nullable=True),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
    )
    with op.batch_alter_table('teaching_assignments') as b:
        b.add_column(sa.Column('program_id', sa.Integer(), nullable=True))
        b.create_foreign_key('fk_ta_program', 'plan_programs', ['program_id'], ['id'], ondelete='SET NULL')
    op.create_table(
        'assignment_programs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('assignment_id', sa.Integer(), sa.ForeignKey('teaching_assignments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('program_id', sa.Integer(), sa.ForeignKey('plan_programs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('level', sa.String(10), nullable=True),
        sa.Column('note', sa.String(300), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('assignment_id', 'program_id', 'level'),
    )


def downgrade() -> None:
    op.drop_table('assignment_programs')
    with op.batch_alter_table('teaching_assignments') as b:
        b.drop_constraint('fk_ta_program', type_='foreignkey')
        b.drop_column('program_id')
    op.drop_table('plan_programs')
