"""sınaq seriyası – sınaqların dövrə görə avtomatik göndərilməsi

Revision ID: d3f5b7c9e1a2
Revises: c2e4a6b8d0f1
Create Date: 2026-10-06 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd3f5b7c9e1a2'
down_revision: Union[str, Sequence[str], None] = 'c2e4a6b8d0f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if 'exam_series' in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        'exam_series',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('subject', sa.String(60), nullable=False),
        sa.Column('targets', sa.JSON(), nullable=False),
        sa.Column('sources', sa.JSON(), nullable=False),
        sa.Column('grade', sa.Integer(), nullable=True),
        sa.Column('period', sa.String(8), nullable=False),
        sa.Column('every', sa.Integer(), nullable=False),
        sa.Column('weekday', sa.Integer(), nullable=True),
        sa.Column('month_day', sa.Integer(), nullable=True),
        sa.Column('open_time', sa.String(5), nullable=False),
        sa.Column('window_hours', sa.Integer(), nullable=False),
        sa.Column('duration_min', sa.Integer(), nullable=False),
        sa.Column('penalty', sa.Integer(), nullable=False),
        sa.Column('show_answers', sa.String(12), nullable=False),
        sa.Column('shuffle', sa.Boolean(), nullable=False),
        sa.Column('auto_new', sa.Boolean(), nullable=False),
        sa.Column('queue', sa.JSON(), nullable=False),
        sa.Column('done', sa.JSON(), nullable=False),
        sa.Column('since_file_id', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('next_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('exam_series')
