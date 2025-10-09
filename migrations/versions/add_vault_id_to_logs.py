"""add_vault_id_to_logs

Revision ID: add_vault_id_to_logs
Revises: 86eea0cb5deb
Create Date: 2025-10-06 21:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_vault_id_to_logs'
down_revision: Union[str, Sequence[str], None] = '6d2e4c802c40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add vault_id column to logs table
    op.add_column('logs', sa.Column('vault_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'logs', 'vaults', ['vault_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    # Remove vault_id column from logs table
    op.drop_constraint(None, 'logs', type_='foreignkey')
    op.drop_column('logs', 'vault_id')