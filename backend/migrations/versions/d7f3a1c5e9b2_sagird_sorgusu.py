"""şagird sorğusu (müəllim haqqında, anonim; həftəlik və tətbiqdə)

Revision ID: d7f3a1c5e9b2
Revises: c5e7a9b1d3f4
Create Date: 2026-10-04 23:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd7f3a1c5e9b2'
down_revision: Union[str, Sequence[str], None] = 'c5e7a9b1d3f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table('surveys'):
        return
    op.create_table(
        'surveys',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('owner_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('school_id', sa.Integer(), sa.ForeignKey('schools.id', ondelete='CASCADE'), nullable=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('template_key', sa.String(40), nullable=True),
        sa.Column('sections', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(10), nullable=False),
        sa.Column('opens_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closes_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('min_group', sa.Integer(), nullable=False),
        sa.Column('repeat', sa.String(10), nullable=False, server_default='once'),
        sa.Column('in_app', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('pulse', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('root_id', sa.Integer(), nullable=True),
        sa.Column('wave', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        'survey_questions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('survey_id', sa.Integer(), sa.ForeignKey('surveys.id', ondelete='CASCADE'), nullable=False),
        sa.Column('key', sa.String(20), nullable=True),
        sa.Column('section', sa.String(4), nullable=False),
        sa.Column('order', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(10), nullable=False),
        sa.Column('text', sa.String(500), nullable=False),
        sa.Column('options', sa.JSON(), nullable=True),
        sa.Column('required', sa.Boolean(), nullable=False),
        sa.Column('reverse', sa.Boolean(), nullable=False),
    )
    op.create_index('ix_survey_questions_survey_id', 'survey_questions', ['survey_id'])
    op.create_table(
        'survey_links',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('survey_id', sa.Integer(), sa.ForeignKey('surveys.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token', sa.String(64), nullable=False, unique=True),
        sa.Column('class_id', sa.Integer(), sa.ForeignKey('classes.id', ondelete='SET NULL'), nullable=True),
        sa.Column('label', sa.String(120), nullable=False),
        sa.Column('mode', sa.String(10), nullable=False, server_default='auto'),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_survey_links_survey_id', 'survey_links', ['survey_id'])
    op.create_table(
        'survey_responses',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('survey_id', sa.Integer(), sa.ForeignKey('surveys.id', ondelete='CASCADE'), nullable=False),
        sa.Column('link_id', sa.Integer(), sa.ForeignKey('survey_links.id', ondelete='SET NULL'), nullable=True),
        sa.Column('period', sa.String(10), nullable=False),
        sa.Column('submitted_on', sa.Date(), nullable=False),
        sa.Column('answers', sa.JSON(), nullable=False),
        sa.Column('hidden', sa.JSON(), nullable=True),
    )
    op.create_index('ix_survey_responses_survey_id', 'survey_responses', ['survey_id'])
    op.create_table(
        'survey_dedup',
        sa.Column('survey_id', sa.Integer(), sa.ForeignKey('surveys.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('hash', sa.String(64), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table('survey_dedup')
    op.drop_index('ix_survey_responses_survey_id', table_name='survey_responses')
    op.drop_table('survey_responses')
    op.drop_index('ix_survey_links_survey_id', table_name='survey_links')
    op.drop_table('survey_links')
    op.drop_index('ix_survey_questions_survey_id', table_name='survey_questions')
    op.drop_table('survey_questions')
    op.drop_table('surveys')
