"""add_vault_id_to_nfc_cards

Revision ID: 3ad2df5a50f8
Revises: 10ce4f72617b
Create Date: 2025-10-20 01:15:36.591804

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3ad2df5a50f8'
down_revision: Union[str, Sequence[str], None] = '10ce4f72617b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create nfc_cards table with vault_id
    op.create_table('nfc_cards',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('uid', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('vault_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['vault_id'], ['vaults.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_nfc_cards_uid'), 'nfc_cards', ['uid'], unique=True)
    op.create_index(op.f('ix_nfc_cards_vault_id'), 'nfc_cards', ['vault_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop nfc_cards table
    op.drop_index(op.f('ix_nfc_cards_vault_id'), table_name='nfc_cards')
    op.drop_index(op.f('ix_nfc_cards_uid'), table_name='nfc_cards')
    op.drop_table('nfc_cards')