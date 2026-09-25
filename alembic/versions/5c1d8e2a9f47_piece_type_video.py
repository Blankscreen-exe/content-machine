"""piece_type: video

A video type's pieces are made of frames and rendered into a video, rather than written as
text to paste onto a platform. Existing types are text. A "youtube short" type is added,
opening on frames.md, unless a type of that name already exists.

Revision ID: 5c1d8e2a9f47
Revises: d0e86772b04c
Create Date: 2026-09-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c1d8e2a9f47'
down_revision: Union[str, Sequence[str], None] = 'd0e86772b04c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SHORT = {"name": "youtube short", "main_file": "frames.md"}


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('piece_type', schema=None) as batch_op:
        # The default fills the existing rows; the model supplies it from then on.
        batch_op.add_column(sa.Column('video', sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table('piece_type', schema=None) as batch_op:
        batch_op.alter_column('video', existing_type=sa.Boolean(), server_default=None,
                              existing_nullable=False)
    op.get_bind().execute(
        sa.text("INSERT INTO piece_type (name, main_file, video, active) "
                "SELECT :name, :main_file, 1, 1 "
                "WHERE NOT EXISTS (SELECT 1 FROM piece_type WHERE lower(name) = :name)"),
        SHORT)


def downgrade() -> None:
    """Downgrade schema.

    The added type stays: pieces may already use it, and it reads as a text type once the
    column is gone.
    """
    with op.batch_alter_table('piece_type', schema=None) as batch_op:
        batch_op.drop_column('video')
