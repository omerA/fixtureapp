"""initial_schema

Revision ID: b3610d4bf24a
Revises:
Create Date: 2026-05-16 14:49:17.672201

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b3610d4bf24a'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Idempotent: if the tables already exist (created by the old create_all()
    call before Alembic was introduced) we skip creation so that re-running
    this migration against an existing Railway Postgres DB doesn't fail with
    DuplicateTable errors.
    """
    bind = op.get_bind()
    existing = sa.inspect(bind).get_table_names()

    if 'users' not in existing:
        op.create_table(
            'users',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('email', sa.String(), nullable=False),
            sa.Column('password_hash', sa.String(), nullable=True),
            sa.Column('google_id', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)
            batch_op.create_index(batch_op.f('ix_users_google_id'), ['google_id'], unique=True)

    if 'subscriptions' not in existing:
        op.create_table(
            'subscriptions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('team_key', sa.String(), nullable=False),
            sa.Column('division', sa.String(), nullable=False),
            sa.Column('club', sa.String(), nullable=False),
            sa.Column('coach', sa.String(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'team_key', name='uq_user_team'),
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('subscriptions')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_google_id'))
        batch_op.drop_index(batch_op.f('ix_users_email'))
    op.drop_table('users')
