# pylint: skip-file
"""add_agent_types

Revision ID: 67a131650dc6
Revises: 698e38521722
Create Date: 2022-08-23 11:11:36.649483

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "67a131650dc6"
down_revision = "698e38521722"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    agent_subtype = postgresql.ENUM(
        "SUPERVISION_OFFICER",
        "SUPERVISION_OFFICER_SUPERVISOR",
        "SUPERVISION_REGIONAL_MANAGER",
        "INTERNAL_UNKNOWN",
        "EXTERNAL_UNKNOWN",
        name="state_agent_subtype",
    )
    agent_subtype.create(op.get_bind())
    op.add_column(
        "state_agent",
        sa.Column(
            "agent_subtype",
            sa.Enum(
                "SUPERVISION_OFFICER",
                "SUPERVISION_OFFICER_SUPERVISOR",
                "SUPERVISION_REGIONAL_MANAGER",
                "INTERNAL_UNKNOWN",
                "EXTERNAL_UNKNOWN",
                name="state_agent_subtype",
            ),
            nullable=True,
            comment="The subtype of the position of the agent.",
        ),
    )
    op.add_column(
        "state_agent",
        sa.Column(
            "agent_subtype_raw_text",
            sa.String(length=255),
            nullable=True,
            comment="The raw text of the agent subtype.",
        ),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("state_agent", "agent_subtype_raw_text")
    op.drop_column("state_agent", "agent_subtype")
    agent_subtype = postgresql.ENUM(
        "SUPERVISION_OFFICER",
        "SUPERVISION_OFFICER_SUPERVISOR",
        "SUPERVISION_REGIONAL_MANAGER",
        "INTERNAL_UNKNOWN",
        "EXTERNAL_UNKNOWN",
        name="state_agent_subtype",
    )
    agent_subtype.drop(op.get_bind())
    # ### end Alembic commands ###
