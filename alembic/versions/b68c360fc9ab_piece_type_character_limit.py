"""piece_type: character limit

The most characters a piece of this type should run to once pasted, shown against the
draft as it is written. Empty means no limit. The two types with a hard platform limit are
filled in; renamed types keep whatever they have.

Revision ID: b68c360fc9ab
Revises: 6ae01126d04c
Create Date: 2026-09-22 01:23:55.755972

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b68c360fc9ab'
down_revision: Union[str, Sequence[str], None] = '6ae01126d04c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Platform limits for the types seeded by 09bbd02b27bf, as they stood at this revision.
KNOWN_LIMITS = {"linkedin post": 3000, "x post": 280}


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('piece_type', schema=None) as batch_op:
        batch_op.add_column(sa.Column('char_limit', sa.Integer(), nullable=True))
    for name, limit in KNOWN_LIMITS.items():
        op.get_bind().execute(sa.text("UPDATE piece_type SET char_limit = :limit WHERE name = :name"),
                              {"limit": limit, "name": name})


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('piece_type', schema=None) as batch_op:
        batch_op.drop_column('char_limit')
