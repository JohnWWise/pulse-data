# pylint: skip-file
"""add_is_drug

Revision ID: fd946cbe3966
Revises: 366599c208e9
Create Date: 2022-10-04 11:31:02.070415

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "fd946cbe3966"
down_revision = "366599c208e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "state_charge",
        sa.Column(
            "is_drug",
            sa.Boolean(),
            nullable=True,
            comment="Whether this charge was for a drug-related crime or not.",
        ),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("state_charge", "is_drug")
    # ### end Alembic commands ###
