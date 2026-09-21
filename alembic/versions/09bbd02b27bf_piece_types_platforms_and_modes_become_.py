"""piece types, platforms and modes become managed lists

Until now these were a list in the code (types), free text (platforms) and a hardcoded
pair of words (modes). Each gets a table, and the rows that used them point at it:

- piece_type is seeded with the types the code had, with the main draft file each used,
  so every piece keeps its type and opens on the same file.
- platform gets one row per platform already written on a publish record.
- mode gets one row per brand for each mode its ideas already used.

The lists below are frozen copies of what the code held at this revision; a migration
must not import app code that will keep changing.

Revision ID: 09bbd02b27bf
Revises: 474b296587a9
Create Date: 2026-09-21 23:37:08.213330

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # autogenerate emits sqlmodel.sql.sqltypes.* for SQLModel columns


# revision identifiers, used by Alembic.
revision: str = '09bbd02b27bf'
down_revision: Union[str, Sequence[str], None] = '474b296587a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (name stored by the old enum, name shown, main draft file), as the code had them
PIECE_TYPES = [
    ("blog", "blog", "blog.md"),
    ("linkedin", "linkedin post", "linkedin.md"),
    ("x", "x post", "x.md"),
    ("infographic", "infographic", "spec.md"),
    ("carousel", "carousel", "spec.md"),
    ("quote", "quote", "quotes.md"),
    ("other", "other", "draft.md"),
]
OLD_TYPE_NAMES = [stored for stored, _, _ in PIECE_TYPES]

TEXT = sqlmodel.sql.sqltypes.AutoString()


def _one_space(text: str) -> str:
    return " ".join(text.split())


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()

    op.create_table(
        'piece_type',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', TEXT, nullable=False),
        sa.Column('main_file', TEXT, nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_table(
        'platform',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', TEXT, nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_table(
        'mode',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('brand_id', sa.Integer(), nullable=False),
        sa.Column('name', TEXT, nullable=False),
        sa.Column('description', TEXT, nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['brand_id'], ['brand.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('brand_id', 'name'),
    )
    with op.batch_alter_table('mode', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_mode_brand_id'), ['brand_id'], unique=False)

    # --- piece types -------------------------------------------------------------------
    with op.batch_alter_table('piece', schema=None) as batch_op:
        batch_op.add_column(sa.Column('type_id', sa.Integer(), nullable=True))
    for stored, name, main_file in PIECE_TYPES:
        type_id = connection.execute(
            sa.text("INSERT INTO piece_type (name, main_file, active) VALUES (:name, :main_file, 1)"),
            {"name": name, "main_file": main_file}).lastrowid
        connection.execute(sa.text("UPDATE piece SET type_id = :type_id WHERE type = :stored"),
                           {"type_id": type_id, "stored": stored})
    with op.batch_alter_table('piece', schema=None) as batch_op:
        batch_op.alter_column('type_id', existing_type=sa.Integer(), nullable=False)
        batch_op.create_index(batch_op.f('ix_piece_type_id'), ['type_id'], unique=False)
        batch_op.create_foreign_key('fk_piece_type_id_piece_type', 'piece_type', ['type_id'], ['id'])
        batch_op.drop_column('type')

    # --- platforms: one per spelling already used, ignoring case and spacing -------------
    with op.batch_alter_table('publication', schema=None) as batch_op:
        batch_op.add_column(sa.Column('platform_id', sa.Integer(), nullable=True))
    platform_ids: dict[str, int] = {}
    for publication_id, written in connection.execute(
            sa.text("SELECT id, platform FROM publication ORDER BY id")).fetchall():
        name = _one_space(written) or "unknown"
        if name.lower() not in platform_ids:
            platform_ids[name.lower()] = connection.execute(
                sa.text("INSERT INTO platform (name, active) VALUES (:name, 1)"),
                {"name": name}).lastrowid
        connection.execute(sa.text("UPDATE publication SET platform_id = :platform_id WHERE id = :id"),
                           {"platform_id": platform_ids[name.lower()], "id": publication_id})
    with op.batch_alter_table('publication', schema=None) as batch_op:
        batch_op.alter_column('platform_id', existing_type=sa.Integer(), nullable=False)
        batch_op.create_index(batch_op.f('ix_publication_platform_id'), ['platform_id'], unique=False)
        batch_op.create_foreign_key('fk_publication_platform_id_platform', 'platform',
                                    ['platform_id'], ['id'])
        batch_op.drop_column('platform')

    # --- modes: one per brand for each mode its ideas used -------------------------------
    with op.batch_alter_table('idea', schema=None) as batch_op:
        batch_op.add_column(sa.Column('mode_id', sa.Integer(), nullable=True))
    mode_ids: dict[tuple[int, str], int] = {}
    for idea_id, brand_id, written in connection.execute(
            sa.text("SELECT id, brand_id, mode FROM idea WHERE trim(mode) != ''")).fetchall():
        name = _one_space(written)
        key = (brand_id, name.lower())
        if key not in mode_ids:
            mode_ids[key] = connection.execute(
                sa.text("INSERT INTO mode (brand_id, name, description, active) "
                        "VALUES (:brand_id, :name, '', 1)"),
                {"brand_id": brand_id, "name": name}).lastrowid
        connection.execute(sa.text("UPDATE idea SET mode_id = :mode_id WHERE id = :id"),
                           {"mode_id": mode_ids[key], "id": idea_id})
    with op.batch_alter_table('idea', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_idea_mode_id'), ['mode_id'], unique=False)
        batch_op.create_foreign_key('fk_idea_mode_id_mode', 'mode', ['mode_id'], ['id'])
        batch_op.drop_column('mode')


def downgrade() -> None:
    """Downgrade schema.

    Types added after this revision come back as "other", the old catch-all, and mode
    descriptions are lost: the old columns only held a name.
    """
    connection = op.get_bind()

    with op.batch_alter_table('idea', schema=None) as batch_op:
        batch_op.add_column(sa.Column('mode', TEXT, nullable=False, server_default=''))
    connection.execute(sa.text(
        "UPDATE idea SET mode = (SELECT name FROM mode WHERE mode.id = idea.mode_id) "
        "WHERE mode_id IS NOT NULL"))
    with op.batch_alter_table('idea', schema=None) as batch_op:
        batch_op.alter_column('mode', existing_type=TEXT, server_default=None, existing_nullable=False)
        batch_op.drop_constraint('fk_idea_mode_id_mode', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_idea_mode_id'))
        batch_op.drop_column('mode_id')

    with op.batch_alter_table('publication', schema=None) as batch_op:
        batch_op.add_column(sa.Column('platform', TEXT, nullable=False, server_default=''))
    connection.execute(sa.text(
        "UPDATE publication SET platform = "
        "(SELECT name FROM platform WHERE platform.id = publication.platform_id)"))
    with op.batch_alter_table('publication', schema=None) as batch_op:
        batch_op.alter_column('platform', existing_type=TEXT, server_default=None,
                              existing_nullable=False)
        batch_op.drop_constraint('fk_publication_platform_id_platform', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_publication_platform_id'))
        batch_op.drop_column('platform_id')

    old_type = sa.Enum(*OLD_TYPE_NAMES, name='piecetype')
    with op.batch_alter_table('piece', schema=None) as batch_op:
        batch_op.add_column(sa.Column('type', old_type, nullable=False, server_default='other'))
    for stored, name, _ in PIECE_TYPES:
        connection.execute(sa.text(
            "UPDATE piece SET type = :stored "
            "WHERE type_id = (SELECT id FROM piece_type WHERE name = :name)"),
            {"stored": stored, "name": name})
    with op.batch_alter_table('piece', schema=None) as batch_op:
        batch_op.alter_column('type', existing_type=old_type, server_default=None,
                              existing_nullable=False)
        batch_op.drop_constraint('fk_piece_type_id_piece_type', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_piece_type_id'))
        batch_op.drop_column('type_id')

    with op.batch_alter_table('mode', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_mode_brand_id'))
    op.drop_table('mode')
    op.drop_table('platform')
    op.drop_table('piece_type')
