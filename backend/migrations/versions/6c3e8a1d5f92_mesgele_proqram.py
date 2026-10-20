"""Məşğələ qruplarına proqram (docs/meshgele-proqram-ve-video-beledci-promtu.md §A).

- extra_courses.kind, program_id (FK plan_programs), program_sections (JSON) – hamısı nullable;
- extra_sessions.topic_ref – proqramdan gələn mövzunun işarəsi (nullable).
Yalnız ADD COLUMN; mövcud sətirlərə toxunulmur.

Revision ID: 6c3e8a1d5f92
Revises: 5b2d7e9f1a64
Create Date: 2026-10-20 10:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '6c3e8a1d5f92'
down_revision: Union[str, Sequence[str], None] = '5b2d7e9f1a64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('extra_courses') as b:
        b.add_column(sa.Column('kind', sa.String(length=10), nullable=True))
        b.add_column(sa.Column('program_id', sa.Integer(), sa.ForeignKey('plan_programs.id', ondelete='SET NULL', name='fk_extra_courses_program_id'), nullable=True))
        b.add_column(sa.Column('program_sections', sa.JSON(), nullable=True))
    with op.batch_alter_table('extra_sessions') as b:
        b.add_column(sa.Column('topic_ref', sa.String(length=80), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('extra_sessions') as b:
        b.drop_column('topic_ref')
    with op.batch_alter_table('extra_courses') as b:
        b.drop_column('program_sections')
        b.drop_column('program_id')
        b.drop_column('kind')
