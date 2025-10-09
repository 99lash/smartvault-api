"""empty message

Revision ID: 24b745eb1597
Revises: 86eea0cb5deb, add_vault_id_to_logs
Create Date: 2025-10-09 02:42:37.952341

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '24b745eb1597'
down_revision: Union[str, Sequence[str], None] = ('86eea0cb5deb', 'add_vault_id_to_logs')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add device_id column to logs table (vault_id already exists)
    op.add_column('logs', sa.Column('device_id', sa.String(), nullable=False, server_default=''))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove device_id column from logs table
    op.drop_column('logs', 'device_id')
