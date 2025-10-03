"""update_keypad_pins_unique_constraint

Revision ID: f790dc8dfa1c
Revises: 30e23962be15
Create Date: 2025-10-02 22:11:59.758864

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f790dc8dfa1c'
down_revision: Union[str, Sequence[str], None] = '30e23962be15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Use batch operations for SQLite constraint changes on keypad_pins table
    with op.batch_alter_table('keypad_pins') as batch_op:
        # Drop the existing unique index on pin_code
        batch_op.drop_index(op.f('ix_keypad_pins_pin_code'))
        # Create a non-unique index on pin_code
        batch_op.create_index(op.f('ix_keypad_pins_pin_code'), ['pin_code'], unique=False)
        # Create composite unique constraint on (user_id, pin_code)
        batch_op.create_unique_constraint('uq_user_pin', ['user_id', 'pin_code'])


def downgrade() -> None:
    """Downgrade schema."""
    # Use batch operations for SQLite constraint changes
    with op.batch_alter_table('keypad_pins') as batch_op:
        # Drop the composite unique constraint
        batch_op.drop_constraint('uq_user_pin', type_='unique')
        # Drop the non-unique index
        batch_op.drop_index(op.f('ix_keypad_pins_pin_code'))
        # Recreate the unique index on pin_code
        batch_op.create_index(op.f('ix_keypad_pins_pin_code'), ['pin_code'], unique=True)
