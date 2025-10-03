"""drop_non_admin_users_table

Revision ID: f95c3012f5db
Revises: 43d83a0ddf6e
Create Date: 2025-10-03 01:02:53.432867

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f95c3012f5db'
down_revision: Union[str, Sequence[str], None] = '43d83a0ddf6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### Drop only the non_admin_users table ###
    op.drop_table('non_admin_users')
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### Recreate only the non_admin_users table ###
    op.create_table('non_admin_users',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('created_at', sa.DATETIME(), nullable=False),
    sa.Column('updated_at', sa.DATETIME(), nullable=True),
    sa.Column('deleted_at', sa.DATETIME(), nullable=True),
    sa.Column('name', sa.VARCHAR(), nullable=False),
    sa.Column('nfc_card_id', sa.INTEGER(), nullable=True),
    sa.Column('keypad_pin_id', sa.INTEGER(), nullable=True),
    sa.Column('user_id', sa.INTEGER(), nullable=True),
    sa.ForeignKeyConstraint(['keypad_pin_id'], ['keypad_pins.id'], ),
    sa.ForeignKeyConstraint(['nfc_card_id'], ['nfc_cards.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###
