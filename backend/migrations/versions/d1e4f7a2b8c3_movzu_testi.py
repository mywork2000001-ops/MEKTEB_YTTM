"""mövzu testi: sinif rəqəmi, test paketi, tapşırığın plan mövzusu və jurnala yazılışı

Revision ID: d1e4f7a2b8c3
Revises: c9d3e4f5a6b7
Create Date: 2026-10-04 21:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd1e4f7a2b8c3'
down_revision: Union[str, Sequence[str], None] = 'c9d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.domain.classes import grade_of
    with op.batch_alter_table('classes') as b:
        b.add_column(sa.Column('grade', sa.Integer(), nullable=True))
    conn = op.get_bind()
    for cid, name, utis in conn.execute(sa.text('SELECT id, name, utis_class FROM classes')).all():
        g = grade_of(name, utis)
        if g:
            conn.execute(sa.text('UPDATE classes SET grade = :g WHERE id = :i'), {'g': g, 'i': cid})

    op.create_table(
        'test_batches',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('kind', sa.String(length=10), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('subject', sa.String(length=60), nullable=True),
        sa.Column('grade', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    with op.batch_alter_table('online_tasks') as b:
        b.add_column(sa.Column('kind', sa.String(length=10), nullable=True))
        b.add_column(sa.Column('batch_id', sa.Integer(), nullable=True))
        b.add_column(sa.Column('plan_lesson_id', sa.Integer(), nullable=True))
        b.add_column(sa.Column('journal_auto', sa.Boolean(), nullable=False, server_default=sa.false()))
        b.add_column(sa.Column('journal_done_at', sa.DateTime(timezone=True), nullable=True))
        b.create_foreign_key('fk_online_tasks_batch', 'test_batches', ['batch_id'], ['id'], ondelete='SET NULL')
        b.create_foreign_key('fk_online_tasks_plan_lesson', 'plan_lessons', ['plan_lesson_id'], ['id'], ondelete='SET NULL')
    with op.batch_alter_table('marks') as b:
        b.add_column(sa.Column('task_id', sa.Integer(), nullable=True))
        b.create_foreign_key('fk_marks_task', 'online_tasks', ['task_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    with op.batch_alter_table('marks') as b:
        b.drop_constraint('fk_marks_task', type_='foreignkey')
        b.drop_column('task_id')
    with op.batch_alter_table('online_tasks') as b:
        b.drop_constraint('fk_online_tasks_plan_lesson', type_='foreignkey')
        b.drop_constraint('fk_online_tasks_batch', type_='foreignkey')
        for c in ('journal_done_at', 'journal_auto', 'plan_lesson_id', 'batch_id', 'kind'):
            b.drop_column(c)
    op.drop_table('test_batches')
    with op.batch_alter_table('classes') as b:
        b.drop_column('grade')
