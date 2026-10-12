"""KSQ/BSQ bazası: ksq_bases (gələcək illər üçün) + exam_variants.printed_at (çap olunmuş variantlara avtomatik toxunulmur).

Revision ID: f9b1d3e5a7c2
Revises: e8a0c2d4f6b9
Create Date: 2026-10-13 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f9b1d3e5a7c2'
down_revision: Union[str, Sequence[str], None] = 'e8a0c2d4f6b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ksq_bases',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('key', sa.String(length=120), nullable=False, unique=True),
        sa.Column('topics', sa.JSON(), nullable=True),
        sa.Column('files', sa.JSON(), nullable=True),
        sa.Column('excluded', sa.JSON(), nullable=True),
        sa.Column('edits', sa.JSON(), nullable=True),
        sa.Column('updated_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column('exam_variants', sa.Column('printed_at', sa.DateTime(timezone=True), nullable=True))
    # 13.10.2026: müəllim bütün mövcud variantları artıq çap edib – onlara heç bir avtomatik iş toxunmasın
    op.execute("UPDATE exam_variants SET printed_at = CURRENT_TIMESTAMP WHERE printed_at IS NULL")


def downgrade() -> None:
    op.drop_column('exam_variants', 'printed_at')
    op.drop_table('ksq_bases')
