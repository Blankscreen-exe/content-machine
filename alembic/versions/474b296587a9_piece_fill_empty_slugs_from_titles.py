"""piece: fill empty slugs from titles

Pieces created before the slug column had it set to ''. Their folders were named from the
title instead, so filling the slug in with exactly that value keeps every folder where it
already is — and lets the folder rule drop its fallback for empty slugs.

Revision ID: 474b296587a9
Revises: f8dfd0156432
Create Date: 2026-09-21 11:01:32.768450

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from cm.text import slugify

# revision identifiers, used by Alembic.
revision: str = '474b296587a9'
down_revision: Union[str, Sequence[str], None] = 'f8dfd0156432'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    empty = connection.execute(sa.text("SELECT id, title FROM piece WHERE slug = ''")).fetchall()
    for piece_id, title in empty:
        connection.execute(sa.text("UPDATE piece SET slug = :slug WHERE id = :id"),
                           {"slug": slugify(title), "id": piece_id})


def downgrade() -> None:
    # Nothing to undo: an empty slug and its title-derived value name the same folder.
    pass
