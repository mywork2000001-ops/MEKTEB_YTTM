"""Sinfin test mənbəyi: teaching_assignments.bank_source (plan linkləri) və ksq_source (KSQ layihəsi).
XI peşə: plan linkləri yoxdur ('none'), KSQ – P013 «Sinif testləri» (istifadəçi 14.10.2026).

Revision ID: a1c3e5f7b9d2
Revises: f9b1d3e5a7c2
Create Date: 2026-10-14 10:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1c3e5f7b9d2'
down_revision: Union[str, Sequence[str], None] = 'f9b1d3e5a7c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('teaching_assignments', sa.Column('bank_source', sa.String(length=32), nullable=True))
    op.add_column('teaching_assignments', sa.Column('ksq_source', sa.String(length=32), nullable=True))
    op.execute("UPDATE teaching_assignments SET bank_source = 'none', ksq_source = 'p013' "
               "WHERE class_id IN (SELECT id FROM classes WHERE name LIKE 'XI pe%')")
    # artıq saxlanmış əl ilə seçilmiş P0010 linkləri də XI peşə üçün götürülür
    op.execute("DELETE FROM lesson_bank_links WHERE plan_lesson_id IN (SELECT pl.id FROM plan_lessons pl "
               "JOIN teaching_assignments ta ON ta.id = pl.assignment_id JOIN classes c ON c.id = ta.class_id WHERE c.name LIKE 'XI pe%')")


def downgrade() -> None:
    op.drop_column('teaching_assignments', 'ksq_source')
    op.drop_column('teaching_assignments', 'bank_source')
