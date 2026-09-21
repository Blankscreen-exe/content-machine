"""brand: voice and profile move into the database

A brand's voice and profile used to be files, `brands/<slug>/voice.md` and `brand.md`, in
the workspace. They are now edited in the app and handed to sessions in brief.md, so the
database holds the only copy. This copies each existing file in, once. The files are left
where they are, to delete by hand once the import has been checked.

The brands folder is found next to the database being migrated, not through the app's
settings, so migrating a copy of a database never reads another workspace's files.

Revision ID: 6ae01126d04c
Revises: 09bbd02b27bf
Create Date: 2026-09-21 23:37:10.410470

"""
from pathlib import Path
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # autogenerate emits sqlmodel.sql.sqltypes.* for SQLModel columns


# revision identifiers, used by Alembic.
revision: str = '6ae01126d04c'
down_revision: Union[str, Sequence[str], None] = '09bbd02b27bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TEXT = sqlmodel.sql.sqltypes.AutoString()
FILES = {"voice": "voice.md", "profile": "brand.md"}


def _brands_folder(connection) -> Path | None:
    database = connection.engine.url.database
    if not database or database == ":memory:":
        return None
    return Path(database).resolve().parent / "brands"


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()

    # server_default fills the rows that already exist; it is dropped again in a second
    # block (SQLite rebuilds the table per block) so the columns match the model.
    with op.batch_alter_table('brand', schema=None) as batch_op:
        batch_op.add_column(sa.Column('voice', TEXT, nullable=False, server_default=''))
        batch_op.add_column(sa.Column('profile', TEXT, nullable=False, server_default=''))
    with op.batch_alter_table('brand', schema=None) as batch_op:
        batch_op.alter_column('voice', existing_type=TEXT, server_default=None, existing_nullable=False)
        batch_op.alter_column('profile', existing_type=TEXT, server_default=None,
                              existing_nullable=False)

    brands = _brands_folder(connection)
    if brands is None or not brands.is_dir():
        return
    for brand_id, slug in connection.execute(sa.text("SELECT id, slug FROM brand")).fetchall():
        for column, file_name in FILES.items():
            path = brands / slug / file_name
            if path.is_file():
                connection.execute(sa.text(f"UPDATE brand SET {column} = :text WHERE id = :id"),
                                   {"text": path.read_text(encoding="utf-8"), "id": brand_id})


def downgrade() -> None:
    """Downgrade schema. The files this imported from were never removed."""
    with op.batch_alter_table('brand', schema=None) as batch_op:
        batch_op.drop_column('profile')
        batch_op.drop_column('voice')
