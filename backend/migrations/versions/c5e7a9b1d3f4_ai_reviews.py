"""süni intellektin pedaqoji rəyi (Test nəticələri)

Revision ID: c5e7a9b1d3f4
Revises: b4d6f8a0c2e3
Create Date: 2026-10-04 23:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c5e7a9b1d3f4'
down_revision: Union[str, Sequence[str], None] = 'b4d6f8a0c2e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table('ai_reviews'):
        return
    op.create_table(
        'ai_reviews',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('school_id', sa.Integer(), sa.ForeignKey('schools.id', ondelete='CASCADE'), nullable=True),
        sa.Column('scope', sa.String(10), nullable=False),
        sa.Column('key', sa.String(80), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('model', sa.String(120), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_ai_reviews_user_key', 'ai_reviews', ['user_id', 'key'])


def downgrade() -> None:
    op.drop_index('ix_ai_reviews_user_key', table_name='ai_reviews')
    op.drop_table('ai_reviews')
