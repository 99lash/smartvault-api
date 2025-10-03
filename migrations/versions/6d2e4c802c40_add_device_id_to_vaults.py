"""add_device_id_to_vaults

Revision ID: 6d2e4c802c40
Revises: 3f96fcafa8c9
Create Date: 2025-10-03 06:56:13.223662

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6d2e4c802c40'
down_revision: Union[str, Sequence[str], None] = '3f96fcafa8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### Add device_id column to vaults table ###
    # Add as nullable - application logic will ensure it's provided for new vaults
    op.add_column('vaults', sa.Column('device_id', sa.String(), nullable=True))

    # Create unique constraint (only for non-null values)
    op.create_unique_constraint(None, 'vaults', ['device_id'])

    # Note: Existing vaults will have NULL device_id until they are properly configured
    # The application should handle this by requiring device_id for new vault creation
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### Remove device_id column from vaults table ###
    op.drop_constraint(None, 'vaults', type_='unique')
    op.drop_column('vaults', 'device_id')
    # ### end Alembic commands ###
