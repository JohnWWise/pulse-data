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
"""Spans when someone is in Restrictive Housing and hasn't had a hearing,
or had a hearing scheduled, since their placement in Restrictive Housing.
"""
from recidiviz.common.constants.states import StateCode
from recidiviz.task_eligibility.task_criteria_big_query_view_builder import (
    StateSpecificTaskCriteriaBigQueryViewBuilder,
)
from recidiviz.task_eligibility.utils.placeholder_criteria_builders import (
    state_specific_placeholder_criteria_view_builder,
)
from recidiviz.utils.environment import GCP_PROJECT_STAGING
from recidiviz.utils.metadata import local_project_id_override

_CRITERIA_NAME = "US_MO_NO_HEARING_OR_NEXT_REVIEW_SINCE_RESTRICTIVE_HOUSING_START"

_DESCRIPTION = """Spans when someone is in Restrictive Housing and hasn't had a hearing,
or had a hearing scheduled, since their placement in Restrictive Housing.
"""
_REASON_QUERY = """TO_JSON(
    STRUCT(
        "9999-12-31" AS restrictive_housing_start_date,
        "9999-12-31" AS latest_hearing_date,
        "9999-12-31" AS latest_scheduled_review_date
    ))"""

VIEW_BUILDER: StateSpecificTaskCriteriaBigQueryViewBuilder = (
    state_specific_placeholder_criteria_view_builder(
        criteria_name=_CRITERIA_NAME,
        description=_DESCRIPTION,
        reason_query=_REASON_QUERY,
        state_code=StateCode.US_MO,
    )
)

if __name__ == "__main__":
    with local_project_id_override(GCP_PROJECT_STAGING):
        VIEW_BUILDER.build_and_print()
