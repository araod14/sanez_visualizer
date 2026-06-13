"""category.precio_modo

Revision ID: a1b2c3d4e5f6
Revises: ffe850e05b77
Create Date: 2026-06-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'ffe850e05b77'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'categories',
        sa.Column(
            'precio_modo',
            sa.String(),
            nullable=False,
            server_default='usd_fijo',
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('categories', 'precio_modo')
