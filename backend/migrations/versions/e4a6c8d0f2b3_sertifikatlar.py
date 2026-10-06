"""sertifikatlar və sinif üzrə sertifikat hədləri

Revision ID: e4a6c8d0f2b3
Revises: d3f5b7c9e1a2
Create Date: 2026-10-06 19:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e4a6c8d0f2b3'
down_revision: Union[str, Sequence[str], None] = 'd3f5b7c9e1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if 'cert_rules' not in {c['name'] for c in insp.get_columns('teaching_assignments')}:
        with op.batch_alter_table('teaching_assignments') as b:
            b.add_column(sa.Column('cert_rules', sa.JSON(), nullable=True))
    if 'certificates' not in insp.get_table_names():
        op.create_table(
            'certificates',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('code', sa.String(20), nullable=False, unique=True),
            sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id', ondelete='CASCADE'), nullable=False),
            sa.Column('assignment_id', sa.Integer(), sa.ForeignKey('teaching_assignments.id', ondelete='SET NULL'), nullable=True),
            sa.Column('kind', sa.String(12), nullable=False),
            sa.Column('source', sa.String(40), nullable=False),
            sa.Column('title', sa.String(300), nullable=False),
            sa.Column('details', sa.JSON(), nullable=False),
            sa.Column('issued_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('issued_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('seen_at', sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint('student_id', 'kind', 'source', name='uq_certificate_source'),
        )
        op.create_index('ix_certificates_student_id', 'certificates', ['student_id'])


def downgrade() -> None:
    op.drop_index('ix_certificates_student_id', 'certificates')
    op.drop_table('certificates')
    with op.batch_alter_table('teaching_assignments') as b:
        b.drop_column('cert_rules')
