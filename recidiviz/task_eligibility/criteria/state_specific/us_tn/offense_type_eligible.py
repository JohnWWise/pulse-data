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
# ============================================================================
"""Describes the spans of time when a TN client is not eligible due to serving time for certain offenses"""

from recidiviz.common.constants.states import StateCode
from recidiviz.task_eligibility.task_criteria_big_query_view_builder import (
    StateSpecificTaskCriteriaBigQueryViewBuilder,
)
from recidiviz.task_eligibility.utils.placeholder_criteria_builders import (
    state_specific_placeholder_criteria_view_builder,
)
from recidiviz.utils.environment import GCP_PROJECT_STAGING
from recidiviz.utils.metadata import local_project_id_override

_CRITERIA_NAME = "US_TN_OFFENSE_TYPE_ELIGIBLE"

_DESCRIPTION = """Describes the spans of time when a TN client is not eligible due to serving time for certain offenses.
Specifically:
- Periods of time when someone is not serving a sentence for domestic abuse/assault, DUI within past 5 years, 
assaultive offense, or a crime where victim was under the age of 18
- Additionally, periods of time when someone may have had these sentences but they are over 10 years expired
"""

_REASON_QUERY = """TO_JSON(STRUCT(['9999-99-99','9999-99-99'] AS ineligible_offenses,
                                  ['9999-99-99','9999-99-99'] AS ineligible_sentences_expiration_dates
                            ))"""

VIEW_BUILDER: StateSpecificTaskCriteriaBigQueryViewBuilder = (
    state_specific_placeholder_criteria_view_builder(
        criteria_name=_CRITERIA_NAME,
        description=_DESCRIPTION,
        reason_query=_REASON_QUERY,
        state_code=StateCode.US_TN,
    )
)

if __name__ == "__main__":
    with local_project_id_override(GCP_PROJECT_STAGING):
        VIEW_BUILDER.build_and_print()
