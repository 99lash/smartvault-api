"""add_vault_invitations_table

Revision ID: 3f96fcafa8c9
Revises: f95c3012f5db
Create Date: 2025-10-03 01:15:13.987037

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f96fcafa8c9'
down_revision: Union[str, Sequence[str], None] = 'f95c3012f5db'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### Add vault_invitations table ###
    op.create_table('vault_invitations',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('vault_id', sa.INTEGER(), nullable=False),
    sa.Column('invited_by', sa.INTEGER(), nullable=False),
    sa.Column('invite_code', sa.VARCHAR(), nullable=False),
    sa.Column('role', sa.VARCHAR(), nullable=False),
    sa.Column('expires_at', sa.DATETIME(), nullable=False),
    sa.Column('accepted', sa.BOOLEAN(), nullable=False),
    sa.Column('created_at', sa.DATETIME(), nullable=False),
    sa.Column('updated_at', sa.DATETIME(), nullable=True),
    sa.Column('deleted_at', sa.DATETIME(), nullable=True),
    sa.ForeignKeyConstraint(['invited_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['vault_id'], ['vaults.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('invite_code', name='uq_vault_invitation_code')
    )
    op.create_index(op.f('ix_vault_invitations_invite_code'), 'vault_invitations', ['invite_code'], unique=True)
    op.create_index(op.f('ix_vault_invitations_vault_id'), 'vault_invitations', ['vault_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### Drop only the vault_invitations table ###
    op.drop_index(op.f('ix_vault_invitations_vault_id'), table_name='vault_invitations')
    op.drop_index(op.f('ix_vault_invitations_invite_code'), table_name='vault_invitations')
    op.drop_table('vault_invitations')
    # ### end Alembic commands ###
