"""event: who made the change

Once a Claude session writes to the database through its own tools, the history has to say
whether a change was yours or Claude's. Everything recorded before this was yours.

Revision ID: 7e3a91c4d2b6
Revises: 5c1d8e2a9f47
Create Date: 2026-10-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7e3a91c4d2b6'
down_revision: Union[str, Sequence[str], None] = '5c1d8e2a9f47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.add_column(sa.Column('actor', sa.Enum('me', 'claude', name='actor'), nullable=False,
                                      server_default='me'))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.drop_column('actor')
