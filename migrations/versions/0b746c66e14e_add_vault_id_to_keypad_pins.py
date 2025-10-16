"""add_vault_id_to_keypad_pins

Revision ID: 0b746c66e14e
Revises: 24b745eb1597
Create Date: 2025-10-15 03:09:07.928624

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0b746c66e14e'
down_revision: Union[str, Sequence[str], None] = '24b745eb1597'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### Focus only on keypad_pins changes ###

    # For SQLite, we need to recreate the table with the new structure
    # Step 1: Create new table with vault_id
    op.execute("""
        CREATE TABLE keypad_pins_new (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            vault_id INTEGER NOT NULL,
            pin_code VARCHAR NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME,
            deleted_at DATETIME,
            FOREIGN KEY (vault_id) REFERENCES vaults (id),
            UNIQUE(user_id, vault_id, pin_code)
        )
    """)

    # Step 2: Copy existing data with default vault_id = 1
    op.execute("""
        INSERT INTO keypad_pins_new (id, user_id, vault_id, pin_code, created_at, updated_at, deleted_at)
        SELECT id, user_id, 1, pin_code, created_at, updated_at, deleted_at
        FROM keypad_pins
    """)

    # Step 3: Drop old table and rename new one
    op.drop_table('keypad_pins')
    op.rename_table('keypad_pins_new', 'keypad_pins')

    # Step 4: Create index on vault_id
    op.create_index(op.f('ix_keypad_pins_vault_id'), 'keypad_pins', ['vault_id'], unique=False)

    # ### end commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### Focus only on keypad_pins changes ###
    # For SQLite, we need to recreate the table without vault_id
    op.execute("""
        CREATE TABLE keypad_pins_old (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            pin_code VARCHAR NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME,
            deleted_at DATETIME
        )
    """)

    # Copy existing data without vault_id
    op.execute("""
        INSERT INTO keypad_pins_old (id, user_id, pin_code, created_at, updated_at, deleted_at)
        SELECT id, user_id, pin_code, created_at, updated_at, deleted_at
        FROM keypad_pins
    """)

    # Drop new table and rename old one
    op.drop_table('keypad_pins')
    op.rename_table('keypad_pins_old', 'keypad_pins')

    # Recreate the old unique constraint
    op.create_unique_constraint(op.f('uq_user_pin'), 'keypad_pins', ['user_id', 'pin_code'])
    op.create_table('vault_invitations',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('vault_id', sa.INTEGER(), nullable=False),
    sa.Column('invited_by', sa.INTEGER(), nullable=False),
    sa.Column('invite_code', sa.VARCHAR(), nullable=False),
    sa.Column('role', sa.VARCHAR(length=6), nullable=False),
    sa.Column('expires_at', sa.DATETIME(), nullable=False),
    sa.Column('accepted', sa.BOOLEAN(), nullable=False),
    sa.Column('created_at', sa.DATETIME(), nullable=False),
    sa.ForeignKeyConstraint(['invited_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['vault_id'], ['vaults.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('invite_code', name=op.f('uq_vault_invitation_code'))
    )
    op.create_index(op.f('ix_vault_invitations_invite_code'), 'vault_invitations', ['invite_code'], unique=1)
    op.create_table('nfc_cards',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('created_at', sa.DATETIME(), nullable=False),
    sa.Column('updated_at', sa.DATETIME(), nullable=True),
    sa.Column('deleted_at', sa.DATETIME(), nullable=True),
    sa.Column('uid', sa.VARCHAR(), nullable=False),
    sa.Column('user_id', sa.INTEGER(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_nfc_cards_uid'), 'nfc_cards', ['uid'], unique=1)
    op.create_table('vault_memberships',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('user_id', sa.INTEGER(), nullable=False),
    sa.Column('vault_id', sa.INTEGER(), nullable=False),
    sa.Column('role', sa.VARCHAR(length=6), nullable=False),
    sa.Column('created_at', sa.DATETIME(), nullable=False),
    sa.Column('updated_at', sa.DATETIME(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['vault_id'], ['vaults.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'vault_id', name=op.f('uq_vault_membership_user_vault'))
    )
    op.create_index(op.f('ix_vault_memberships_vault_id'), 'vault_memberships', ['vault_id'], unique=False)
    op.create_index(op.f('ix_vault_memberships_user_id'), 'vault_memberships', ['user_id'], unique=False)
    # ### end Alembic commands ###
