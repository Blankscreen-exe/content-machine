"""piece: the piece it was made from

A LinkedIn post made from a blog post points back at it, so its brief can tell a session
which draft to work from. Empty for pieces made from scratch or from an idea.

Revision ID: d0e86772b04c
Revises: b68c360fc9ab
Create Date: 2026-09-22 01:31:47.855042

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0e86772b04c'
down_revision: Union[str, Sequence[str], None] = 'b68c360fc9ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('piece', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source_piece_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_piece_source_piece_id'), ['source_piece_id'], unique=False)
        batch_op.create_foreign_key('fk_piece_source_piece_id_piece', 'piece', ['source_piece_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('piece', schema=None) as batch_op:
        batch_op.drop_constraint('fk_piece_source_piece_id_piece', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_piece_source_piece_id'))
        batch_op.drop_column('source_piece_id')
