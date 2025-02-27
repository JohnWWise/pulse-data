# pylint: skip-file
"""move_violations_to_person

Revision ID: 0d7e6c52f938
Revises: 564eb3671e93
Create Date: 2021-10-13 16:28:24.509250

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0d7e6c52f938"
down_revision = "6d971f41c21c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(
        "ix_state_supervision_period_supervision_violation_assoc_3df4",
        table_name="state_supervision_period_supervision_violation_association",
    )
    op.drop_index(
        "ix_state_supervision_period_supervision_violation_assoc_8a5a",
        table_name="state_supervision_period_supervision_violation_association",
    )
    op.drop_table("state_supervision_period_supervision_violation_association")
    op.drop_index(
        "ix_state_supervision_violation_supervision_period_id",
        table_name="state_supervision_violation",
    )
    op.drop_constraint(
        "state_supervision_violation_supervision_period_id_fkey",
        "state_supervision_violation",
        type_="foreignkey",
    )
    op.drop_column("state_supervision_violation", "supervision_period_id")
    op.drop_index(
        "ix_state_supervision_violation_history_supervision_period_id",
        table_name="state_supervision_violation_history",
    )
    op.drop_constraint(
        "state_supervision_violation_history_supervision_period_id_fkey",
        "state_supervision_violation_history",
        type_="foreignkey",
    )
    op.drop_column("state_supervision_violation_history", "supervision_period_id")
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "state_supervision_violation_history",
        sa.Column(
            "supervision_period_id",
            sa.INTEGER(),
            autoincrement=False,
            nullable=True,
            comment="Unique identifier for a(n) supervision period, generated automatically by the Recidiviz system. This identifier is not stable over time (it may change if historical data is re-ingested), but should be used within the context of a given dataset to connect this object to relevant supervision period information.",
        ),
    )
    op.create_foreign_key(
        "state_supervision_violation_history_supervision_period_id_fkey",
        "state_supervision_violation_history",
        "state_supervision_period",
        ["supervision_period_id"],
        ["supervision_period_id"],
    )
    op.create_index(
        "ix_state_supervision_violation_history_supervision_period_id",
        "state_supervision_violation_history",
        ["supervision_period_id"],
        unique=False,
    )
    op.add_column(
        "state_supervision_violation",
        sa.Column(
            "supervision_period_id",
            sa.INTEGER(),
            autoincrement=False,
            nullable=True,
            comment="Unique identifier for a(n) supervision period, generated automatically by the Recidiviz system. This identifier is not stable over time (it may change if historical data is re-ingested), but should be used within the context of a given dataset to connect this object to relevant supervision period information.",
        ),
    )
    op.create_foreign_key(
        "state_supervision_violation_supervision_period_id_fkey",
        "state_supervision_violation",
        "state_supervision_period",
        ["supervision_period_id"],
        ["supervision_period_id"],
    )
    op.create_index(
        "ix_state_supervision_violation_supervision_period_id",
        "state_supervision_violation",
        ["supervision_period_id"],
        unique=False,
    )
    op.create_table(
        "state_supervision_period_supervision_violation_association",
        sa.Column(
            "supervision_period_id",
            sa.INTEGER(),
            autoincrement=False,
            nullable=True,
            comment="Unique identifier for a(n) supervision period, generated automatically by the Recidiviz system. This identifier is not stable over time (it may change if historical data is re-ingested), but should be used within the context of a given dataset to connect this object to relevant supervision period information.",
        ),
        sa.Column(
            "supervision_violation_id",
            sa.INTEGER(),
            autoincrement=False,
            nullable=True,
            comment="Unique identifier for a(n) supervision violation, generated automatically by the Recidiviz system. This identifier is not stable over time (it may change if historical data is re-ingested), but should be used within the context of a given dataset to connect this object to relevant supervision violation information.",
        ),
        sa.ForeignKeyConstraint(
            ["supervision_period_id"],
            ["state_supervision_period.supervision_period_id"],
            name="state_supervision_period_supervision_supervision_period_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["supervision_violation_id"],
            ["state_supervision_violation.supervision_violation_id"],
            name="state_supervision_period_supervis_supervision_violation_id_fkey",
        ),
    )
    op.create_index(
        "ix_state_supervision_period_supervision_violation_assoc_8a5a",
        "state_supervision_period_supervision_violation_association",
        ["supervision_violation_id"],
        unique=False,
    )
    op.create_index(
        "ix_state_supervision_period_supervision_violation_assoc_3df4",
        "state_supervision_period_supervision_violation_association",
        ["supervision_period_id"],
        unique=False,
    )
    # ### end Alembic commands ###
