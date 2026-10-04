"""fərdi (repetitor) məkan: schools.kind/owner_id, users.active_school_id, audit_log.school_id

Revision ID: e1f5b8c3a9d2
Revises: c4e9a2d7f1b3
Create Date: 2026-10-04 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e1f5b8c3a9d2'
down_revision: Union[str, Sequence[str], None] = 'c4e9a2d7f1b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('schools') as b:
        b.add_column(sa.Column('kind', sa.String(10), nullable=False, server_default='school'))
        b.add_column(sa.Column('owner_id', sa.Integer(), nullable=True))
        b.create_foreign_key('fk_school_owner', 'users', ['owner_id'], ['id'])
    with op.batch_alter_table('users') as b:
        b.add_column(sa.Column('active_school_id', sa.Integer(), nullable=True))
        b.create_foreign_key('fk_user_active_school', 'schools', ['active_school_id'], ['id'])
    with op.batch_alter_table('audit_log') as b:
        b.add_column(sa.Column('school_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('audit_log') as b:
        b.drop_column('school_id')
    with op.batch_alter_table('users') as b:
        b.drop_constraint('fk_user_active_school', type_='foreignkey')
        b.drop_column('active_school_id')
    with op.batch_alter_table('schools') as b:
        b.drop_constraint('fk_school_owner', type_='foreignkey')
        b.drop_column('owner_id')
        b.drop_column('kind')
