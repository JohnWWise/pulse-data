# pylint: skip-file
"""supervision_type_internal_unknown

Revision ID: d0aedd5b308d
Revises: 055777a0433a
Create Date: 2020-02-21 22:27:34.545609

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d0aedd5b308d"
down_revision = "055777a0433a"
branch_labels = None
depends_on = None

# Without new value
old_values = [
    "CIVIL_COMMITMENT",
    "EXTERNAL_UNKNOWN",
    "HALFWAY_HOUSE",
    "PAROLE",
    "POST_CONFINEMENT",
    "PRE_CONFINEMENT",
    "PROBATION",
]

# With new value
new_values = [
    "CIVIL_COMMITMENT",
    "EXTERNAL_UNKNOWN",
    "INTERNAL_UNKNOWN",
    "HALFWAY_HOUSE",
    "PAROLE",
    "POST_CONFINEMENT",
    "PRE_CONFINEMENT",
    "PROBATION",
]


def upgrade() -> None:
    op.execute(
        "ALTER TYPE state_supervision_type RENAME TO state_supervision_type_old;"
    )
    sa.Enum(*new_values, name="state_supervision_type").create(bind=op.get_bind())

    op.alter_column(
        "state_supervision_sentence",
        column_name="supervision_type",
        type_=sa.Enum(*new_values, name="state_supervision_type"),
        postgresql_using="supervision_type::text::state_supervision_type",
    )
    op.alter_column(
        "state_supervision_sentence_history",
        column_name="supervision_type",
        type_=sa.Enum(*new_values, name="state_supervision_type"),
        postgresql_using="supervision_type::text::state_supervision_type",
    )

    op.alter_column(
        "state_supervision_period",
        column_name="supervision_type",
        type_=sa.Enum(*new_values, name="state_supervision_type"),
        postgresql_using="supervision_type::text::state_supervision_type",
    )
    op.alter_column(
        "state_supervision_period_history",
        column_name="supervision_type",
        type_=sa.Enum(*new_values, name="state_supervision_type"),
        postgresql_using="supervision_type::text::state_supervision_type",
    )

    op.execute("DROP TYPE state_supervision_type_old;")


def downgrade() -> None:
    op.execute(
        "ALTER TYPE state_supervision_type RENAME TO state_supervision_type_old;"
    )
    sa.Enum(*old_values, name="state_supervision_type").create(bind=op.get_bind())

    op.alter_column(
        "state_supervision_period",
        column_name="supervision_type",
        type_=sa.Enum(*old_values, name="state_supervision_type"),
        postgresql_using="supervision_type::text::state_supervision_type",
    )
    op.alter_column(
        "state_supervision_period_history",
        column_name="supervision_type",
        type_=sa.Enum(*old_values, name="state_supervision_type"),
        postgresql_using="supervision_type::text::state_supervision_type",
    )

    op.alter_column(
        "state_supervision_sentence",
        column_name="supervision_type",
        type_=sa.Enum(*old_values, name="state_supervision_type"),
        postgresql_using="supervision_type::text::state_supervision_type",
    )
    op.alter_column(
        "state_supervision_sentence_history",
        column_name="supervision_type",
        type_=sa.Enum(*old_values, name="state_supervision_type"),
        postgresql_using="supervision_type::text::state_supervision_type",
    )

    op.execute("DROP TYPE state_supervision_type_old;")
