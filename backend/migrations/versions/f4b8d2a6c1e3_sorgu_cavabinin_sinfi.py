"""sorğu cavabının sinfi (sinif üzrə nəticə və təlim strategiyası)

Revision ID: f4b8d2a6c1e3
Revises: d7f3a1c5e9b2
Create Date: 2026-10-05 00:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f4b8d2a6c1e3'
down_revision: Union[str, Sequence[str], None] = 'd7f3a1c5e9b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    cols = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('survey_responses')}
    if 'class_id' not in cols:
        with op.batch_alter_table('survey_responses') as b:
            b.add_column(sa.Column('class_id', sa.Integer(), nullable=True))
            b.create_foreign_key('fk_survey_responses_class', 'classes', ['class_id'], ['id'], ondelete='SET NULL')
            b.create_index('ix_survey_responses_class_id', ['class_id'])
    # köhnə cavablar: sinif linkindən gələnlərə sinif yazılır (ümumi linkdəkilər – «sinif göstərilməyib»)
    op.execute('UPDATE survey_responses SET class_id = (SELECT survey_links.class_id FROM survey_links '
               'WHERE survey_links.id = survey_responses.link_id) WHERE class_id IS NULL')


def downgrade() -> None:
    with op.batch_alter_table('survey_responses') as b:
        b.drop_index('ix_survey_responses_class_id')
        b.drop_constraint('fk_survey_responses_class', type_='foreignkey')
        b.drop_column('class_id')
