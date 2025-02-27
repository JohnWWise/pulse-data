# Recidiviz - a data platform for criminal justice reform
# Copyright (C) 2020 Recidiviz, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# =============================================================================
"""Metric capturing successful supervision terminations"""

from recidiviz.big_query.big_query_view import SimpleBigQueryViewBuilder
from recidiviz.calculator.query.state.dataset_config import (
    ANALYST_VIEWS_DATASET,
    SESSIONS_DATASET,
)
from recidiviz.utils.environment import GCP_PROJECT_STAGING
from recidiviz.utils.metadata import local_project_id_override

US_ID_PPO_METRICS_SUCCESSFUL_SUPERVISION_TERMINATIONS_VIEW_NAME = (
    "us_id_ppo_metrics_successful_supervision_terminations"
)

US_ID_PPO_METRICS_SUCCESSFUL_SUPERVISION_TERMINATIONS_VIEW_DESCRIPTION = """View capturing successful supervision terminations, captured by transition from SUPERVISION compartment to
    LIBERTY outflow and with DISCHARGED/EXPIRATION/COMMUTED/PARDONED end reason."""

US_ID_PPO_METRICS_SUCCESSFUL_SUPERVISION_TERMINATIONS_QUERY_TEMPLATE = """

    SELECT 
        state_code, 
        person_id, 
        compartment_level_2, 
        outflow_to_level_1, 
        start_date, 
        end_date, 
        session_id, 
        session_length_days,  
        compartment_level_2 as supervision_type,
    FROM `{project_id}.{sessions_dataset}.compartment_sessions_materialized`
    WHERE compartment_level_1 = 'SUPERVISION'
        AND outflow_to_level_1 = 'LIBERTY'
        AND end_reason in ('DISCHARGE', 'EXPIRATION', 'COMMUTED', 'PARDONED')  
    """

US_ID_PPO_METRICS_SUCCESSFUL_SUPERVISION_TERMINATIONS_VIEW_BUILDER = SimpleBigQueryViewBuilder(
    dataset_id=ANALYST_VIEWS_DATASET,
    view_id=US_ID_PPO_METRICS_SUCCESSFUL_SUPERVISION_TERMINATIONS_VIEW_NAME,
    view_query_template=US_ID_PPO_METRICS_SUCCESSFUL_SUPERVISION_TERMINATIONS_QUERY_TEMPLATE,
    description=US_ID_PPO_METRICS_SUCCESSFUL_SUPERVISION_TERMINATIONS_VIEW_DESCRIPTION,
    sessions_dataset=SESSIONS_DATASET,
    should_materialize=False,
)

if __name__ == "__main__":
    with local_project_id_override(GCP_PROJECT_STAGING):
        US_ID_PPO_METRICS_SUCCESSFUL_SUPERVISION_TERMINATIONS_VIEW_BUILDER.build_and_print()
