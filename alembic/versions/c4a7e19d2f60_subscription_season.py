"""subscription_season

Revision ID: c4a7e19d2f60
Revises: b3610d4bf24a
Create Date: 2026-10-06 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c4a7e19d2f60'
down_revision: Union[str, Sequence[str], None] = 'b3610d4bf24a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Adds subscriptions.season (NULL = active, "2026-spring" = archived for
    that season) and narrows the (user_id, team_key) uniqueness to active
    rows, so an archived row cannot block following the same key again.

    Idempotent in the same way as the initial migration: each step is
    skipped if the database already has it.
    """
    bind = op.get_bind()
    insp = sa.inspect(bind)
    columns = {c['name'] for c in insp.get_columns('subscriptions')}
    uniques = {u['name'] for u in insp.get_unique_constraints('subscriptions')}
    indexes = {i['name'] for i in insp.get_indexes('subscriptions')}

    if 'season' not in columns or 'uq_user_team' in uniques:
        with op.batch_alter_table('subscriptions', schema=None) as batch_op:
            if 'season' not in columns:
                batch_op.add_column(sa.Column('season', sa.String(), nullable=True))
            if 'uq_user_team' in uniques:
                batch_op.drop_constraint('uq_user_team', type_='unique')

    if 'uq_user_team_active' not in indexes:
        op.create_index(
            'uq_user_team_active', 'subscriptions', ['user_id', 'team_key'],
            unique=True,
            sqlite_where=sa.text('season IS NULL'),
            postgresql_where=sa.text('season IS NULL'),
        )


def downgrade() -> None:
    """Downgrade schema.

    Archived rows have no place in the old schema, so they are removed
    before the plain unique constraint is restored.
    """
    op.drop_index('uq_user_team_active', table_name='subscriptions')
    op.execute("DELETE FROM subscriptions WHERE season IS NOT NULL")
    with op.batch_alter_table('subscriptions', schema=None) as batch_op:
        batch_op.drop_column('season')
        batch_op.create_unique_constraint('uq_user_team', ['user_id', 'team_key'])
