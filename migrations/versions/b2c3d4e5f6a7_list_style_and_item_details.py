"""user.estilo_lista + product_items descripcion/tamaños

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'users',
        sa.Column(
            'estilo_lista',
            sa.String(),
            nullable=False,
            server_default='estilo_1',
        ),
    )
    op.add_column('product_items', sa.Column('descripcion', sa.String(), nullable=True))
    op.add_column('product_items', sa.Column('precio_peq', sa.String(), nullable=True))
    op.add_column('product_items', sa.Column('precio_med', sa.String(), nullable=True))
    op.add_column('product_items', sa.Column('precio_gran', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('product_items', 'precio_gran')
    op.drop_column('product_items', 'precio_med')
    op.drop_column('product_items', 'precio_peq')
    op.drop_column('product_items', 'descripcion')
    op.drop_column('users', 'estilo_lista')
