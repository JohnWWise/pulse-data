# pylint: skip-file
"""update_transfer_oos_release_reason

Revision ID: 0aeeb9565367
Revises: 5d0aa76119c5
Create Date: 2020-07-23 23:05:57.383679

"""
import sqlalchemy as sa
from alembic import op

from recidiviz.utils.string import StrictStringFormatter

# revision identifiers, used by Alembic.
revision = "0aeeb9565367"
down_revision = "5d0aa76119c5"
branch_labels = None
depends_on = None


RELEASE_REASON_QUERY = (
    "SELECT incarceration_period_id FROM"
    " state_incarceration_period"
    " WHERE state_code = 'US_ND' AND release_reason_raw_text = 'TRN'"
)


UPDATE_QUERY = (
    "UPDATE state_incarceration_period SET release_reason = '{new_value}'"
    " WHERE incarceration_period_id IN ({ids_query});"
)


def upgrade() -> None:
    connection = op.get_bind()

    updated_release_reason = "TRANSFERRED_OUT_OF_STATE"

    connection.execute(
        StrictStringFormatter().format(
            UPDATE_QUERY,
            new_value=updated_release_reason,
            ids_query=RELEASE_REASON_QUERY,
        )
    )


def downgrade() -> None:
    connection = op.get_bind()

    updated_release_reason = "TRANSFER"

    connection.execute(
        StrictStringFormatter().format(
            UPDATE_QUERY,
            new_value=updated_release_reason,
            ids_query=RELEASE_REASON_QUERY,
        )
    )
