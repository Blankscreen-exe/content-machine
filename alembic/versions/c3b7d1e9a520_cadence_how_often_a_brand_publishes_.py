"""cadence: how often a brand publishes each piece type

One rule per brand and piece type (weekdays, every N days, or weekly on a day), which a
batch picks its due dates by. Nothing has one yet, so the table starts empty.

Revision ID: c3b7d1e9a520
Revises: a4f2c8e61b03
Create Date: 2026-10-25 12:49:47.202570

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3b7d1e9a520'
down_revision: Union[str, Sequence[str], None] = 'a4f2c8e61b03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('cadence',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('brand_id', sa.Integer(), nullable=False),
    sa.Column('type_id', sa.Integer(), nullable=False),
    sa.Column('rule', sa.Enum('weekdays', 'every_n_days', 'weekly', name='cadencerule'), nullable=False),
    sa.Column('every_days', sa.Integer(), nullable=True),
    sa.Column('weekday', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['brand_id'], ['brand.id'], ),
    sa.ForeignKeyConstraint(['type_id'], ['piece_type.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('brand_id', 'type_id')
    )
    with op.batch_alter_table('cadence', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_cadence_brand_id'), ['brand_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_cadence_type_id'), ['type_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('cadence', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_cadence_type_id'))
        batch_op.drop_index(batch_op.f('ix_cadence_brand_id'))

    op.drop_table('cadence')
