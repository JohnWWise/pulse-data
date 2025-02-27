# Recidiviz - a data platform for criminal justice reform
# Copyright (C) 2023 Recidiviz, Inc.
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
"""Queries information needed to fill out the SLD form in CA
"""
from recidiviz.big_query.big_query_view import SimpleBigQueryViewBuilder
from recidiviz.calculator.query.state import dataset_config
from recidiviz.calculator.query.state.dataset_config import NORMALIZED_STATE_DATASET
from recidiviz.calculator.query.state.views.workflows.firestore.opportunity_record_query_fragments import (
    join_current_task_eligibility_spans_with_external_id,
)
from recidiviz.common.constants.states import StateCode
from recidiviz.ingest.direct.dataset_config import raw_latest_views_dataset_for_region
from recidiviz.ingest.direct.types.direct_ingest_instance import DirectIngestInstance
from recidiviz.task_eligibility.dataset_config import (
    task_eligibility_spans_state_specific_dataset,
)
from recidiviz.utils.environment import GCP_PROJECT_STAGING
from recidiviz.utils.metadata import local_project_id_override

US_CA_SUPERVISION_LEVEL_DOWNGRADE_VIEW_NAME = (
    "us_ca_supervision_level_downgrade_form_record"
)

US_CA_SUPERVISION_LEVEL_DOWNGRADE_DESCRIPTION = """
    Queries information needed to fill out the SLD form in CA
    """

US_CA_SUPERVISION_LEVEL_DOWNGRADE_QUERY_TEMPLATE = f"""
WITH current_parole_pop_cte AS (
    -- Keep only people in Parole
    {join_current_task_eligibility_spans_with_external_id(
        state_code= "'US_CA'", 
        tes_task_query_view = 'supervision_level_downgrade_materialized',
        id_type = "'US_CA_DOC'")})

SELECT 
    external_id,
    state_code,
    reasons,
    ineligible_criteria,
    pp.Cdcno as form_information_cdcno
FROM current_parole_pop_cte
LEFT JOIN `{{project_id}}.{{us_ca_raw_data_up_to_date_dataset}}.PersonParole_latest` pp
    ON external_id=pp.OffenderId
WHERE is_eligible
"""

US_CA_SUPERVISION_LEVEL_DOWNGRADE_VIEW_BUILDER = SimpleBigQueryViewBuilder(
    dataset_id=dataset_config.WORKFLOWS_VIEWS_DATASET,
    view_id=US_CA_SUPERVISION_LEVEL_DOWNGRADE_VIEW_NAME,
    view_query_template=US_CA_SUPERVISION_LEVEL_DOWNGRADE_QUERY_TEMPLATE,
    description=US_CA_SUPERVISION_LEVEL_DOWNGRADE_DESCRIPTION,
    normalized_state_dataset=NORMALIZED_STATE_DATASET,
    task_eligibility_dataset=task_eligibility_spans_state_specific_dataset(
        StateCode.US_CA
    ),
    us_ca_raw_data_up_to_date_dataset=raw_latest_views_dataset_for_region(
        state_code=StateCode.US_CA, instance=DirectIngestInstance.PRIMARY
    ),
    should_materialize=True,
)

if __name__ == "__main__":
    with local_project_id_override(GCP_PROJECT_STAGING):
        US_CA_SUPERVISION_LEVEL_DOWNGRADE_VIEW_BUILDER.build_and_print()
