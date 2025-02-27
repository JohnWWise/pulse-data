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
"""
Shows the spans of time during which someone in ME is eligible
for an Early Termination from Probation
"""

from recidiviz.common.constants.states import StateCode
from recidiviz.task_eligibility.candidate_populations.general import (
    probation_active_supervision_and_supervision_out_of_state_population,
)
from recidiviz.task_eligibility.completion_events.general import early_discharge
from recidiviz.task_eligibility.criteria.general import (
    no_conviction_within_6_months,
    supervision_level_is_medium_or_lower,
)
from recidiviz.task_eligibility.criteria.state_specific.us_me import (
    no_pending_violations_while_supervised,
    paid_all_owed_restitution,
    supervision_is_not_ic_in,
    supervision_past_half_full_term_release_date_from_probation_start,
)
from recidiviz.task_eligibility.single_task_eligiblity_spans_view_builder import (
    SingleTaskEligibilitySpansBigQueryViewBuilder,
)
from recidiviz.utils.environment import GCP_PROJECT_STAGING
from recidiviz.utils.metadata import local_project_id_override

_DESCRIPTION = """Shows the spans of time during which someone in ME is eligible
for an Early Termination from Probation
"""

VIEW_BUILDER = SingleTaskEligibilitySpansBigQueryViewBuilder(
    state_code=StateCode.US_ME,
    task_name="EARLY_TERMINATION_FROM_PROBATION_REQUEST",
    description=_DESCRIPTION,
    candidate_population_view_builder=probation_active_supervision_and_supervision_out_of_state_population.VIEW_BUILDER,
    criteria_spans_view_builders=[
        supervision_past_half_full_term_release_date_from_probation_start.VIEW_BUILDER,
        no_conviction_within_6_months.VIEW_BUILDER,
        supervision_level_is_medium_or_lower.VIEW_BUILDER,
        paid_all_owed_restitution.VIEW_BUILDER,
        supervision_is_not_ic_in.VIEW_BUILDER,
        no_pending_violations_while_supervised.VIEW_BUILDER,
    ],
    completion_event_builder=early_discharge.VIEW_BUILDER,
)

if __name__ == "__main__":
    with local_project_id_override(GCP_PROJECT_STAGING):
        VIEW_BUILDER.build_and_print()
