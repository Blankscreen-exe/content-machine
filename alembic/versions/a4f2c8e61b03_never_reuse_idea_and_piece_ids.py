"""idea, piece: an id is never handed out twice

Plain SQLite gives a new row the highest id plus one, so deleting the newest piece and
making another hands out its id again: the new piece would inherit the deleted one's
history in `event`, and a session still holding the old id would reach the new piece.
AUTOINCREMENT keeps a counter that only goes up. SQLite can only set it when a table is
made, so both tables are rebuilt.

The counter starts above every id the history mentions, not just the ones still here: the
newest piece may already have been deleted.

Revision ID: a4f2c8e61b03
Revises: 7e3a91c4d2b6
Create Date: 2026-10-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a4f2c8e61b03'
down_revision: Union[str, Sequence[str], None] = '7e3a91c4d2b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("idea", "piece")


def upgrade() -> None:
    """Upgrade schema."""
    for table in TABLES:
        with op.batch_alter_table(table, recreate="always", table_kwargs={"sqlite_autoincrement": True}):
            pass
        op.execute(f"DELETE FROM sqlite_sequence WHERE name = '{table}'")
        op.execute(f"""
            INSERT INTO sqlite_sequence (name, seq) VALUES ('{table}', max(
                (SELECT coalesce(max(id), 0) FROM {table}),
                (SELECT coalesce(max(entity_id), 0) FROM event WHERE entity = '{table}')))
        """)


def downgrade() -> None:
    """Downgrade schema."""
    for table in TABLES:
        with op.batch_alter_table(table, recreate="always", table_kwargs={"sqlite_autoincrement": False}):
            pass
